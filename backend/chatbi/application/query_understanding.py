"""多轮问句理解：有会话历史时用 LLM 将当前问句改写为可独立打分/检索的完整问题。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from chatbi.core.conversation_context import format_dialogue_block, prior_history, truncate_text
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message

log = logging.getLogger("chatbi")

_SYSTEM = (
    "你是 ChatBI 问数助手。根据对话历史，把用户「当前这一句」改写成可独立理解的一句中文问题。\n"
    "规则：\n"
    "1. 若承接上文（追问、指代、省略），补全指标、时间范围、分析对象等，合成完整业务问题\n"
    "2. 若用户明显切换为闲聊/笑话/问候等新话题，只保留当前句含义，不要硬拼上文查数内容\n"
    "3. 只输出一行问题文本，不要 SQL、不要 JSON、不要解释"
)


@dataclass(frozen=True)
class ResolvedQuestion:
    """问句理解结果。"""

    original: str
    text: str
    rewritten: bool


class QueryUnderstandingService:
    """有 prior 对话时调用 LLM 补全问句，供意图规则与 RAG 使用。"""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def resolve(
        self, question: str, messages: list[dict[str, str]] | None
    ) -> ResolvedQuestion:
        original = question.strip()
        prior = prior_history(messages, original)
        if not original or not prior:
            return ResolvedQuestion(
                original=original, text=original, rewritten=False
            )

        dialogue = format_dialogue_block(prior)
        prompt = [
            system_message(_SYSTEM),
            user_message(
                f"对话历史：\n{dialogue}\n\n"
                f"当前用户原句：{original}\n\n"
                "请输出改写后的完整问题（一行）："
            ),
        ]
        try:
            raw = self._llm.complete(prompt).strip()
            text = _extract_line(raw) or original
            text = truncate_text(text, max_len=800)
            rewritten = text != original
            if rewritten:
                log.info(
                    "[query_understanding] %r -> %r", original[:40], text[:80]
                )
            return ResolvedQuestion(original=original, text=text, rewritten=rewritten)
        except Exception as e:
            log.warning("[query_understanding] LLM 改写失败，使用原句: %s", e)
            return ResolvedQuestion(original=original, text=original, rewritten=False)


def _extract_line(raw: str) -> str:
    line = raw.strip().strip('"').strip("'")
    line = re.sub(r"^改写后[：:]\s*", "", line)
    return line.split("\n")[0].strip()
