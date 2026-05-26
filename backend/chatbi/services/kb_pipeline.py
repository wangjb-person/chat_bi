"""
知识库问答管道：检索 kb_chunks → 拼装 Prompt → LLM 流式回答（不访问 MySQL）。
"""

from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional

from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import (
    assistant_message,
    system_message,
    user_message,
)
from chatbi.services.kb_service import KbService

_KB_SYSTEM = (
    "你是企业知识库问答助手。必须仅根据用户提供的「参考材料」回答问题。\n"
    "规则：\n"
    "1. 材料中没有的信息，明确说明「当前知识库未找到相关内容」，不要编造。\n"
    "2. 回答使用简洁中文，可分点说明。\n"
    "3. 不要生成 SQL，不要假装查询了业务数据库。\n"
    "4. 可在文末简要列出依据的材料标题（若有）。"
)

_EMPTY_KB_REPLY = "知识库暂无文档，请先在「知识库管理」中上传制度、FAQ 等文本。"
_NO_CONTEXT = "（未检索到相关片段，请结合已有材料谨慎回答）"


class KbPipeline:
    """知识库 RAG 问答：检索 + 生成。"""

    def __init__(self, kb_service: KbService, llm: LlmClient) -> None:
        self._kb = kb_service
        self._llm = llm

    def retrieve(self, question: str) -> List[Dict[str, object]]:
        """按问题检索 TopK 切片。"""
        return self._kb.retrieve(question)

    def build_context(self, chunks: List[Dict[str, object]]) -> str:
        """将检索切片格式化为 Prompt 中的参考材料。"""
        if not chunks:
            return _NO_CONTEXT
        lines = [
            (
                f"【片段{i}】来源：{c.get('doc_title') or '文档'}"
                f"（段 {c.get('chunk_index', 0)}）\n"
                f"{str(c.get('text', '')).strip()}"
            )
            for i, c in enumerate(chunks, 1)
        ]
        return "\n\n".join(lines)

    def stream_llm(
        self,
        question: str,
        chunks: List[Dict[str, object]],
        *,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[str, None, None]:
        """流式生成回答；无文档时返回引导文案。"""
        if not self._kb.list_documents():
            yield _EMPTY_KB_REPLY
            return

        user_content = (
            f"参考材料：\n{self.build_context(chunks)}\n\n"
            f"用户问题：{question.strip()}\n\n"
            "请根据参考材料回答。"
        )
        messages: List[Dict] = [system_message(_KB_SYSTEM)]
        if history:
            for item in history:
                role = item.get("role")
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                if role == "user":
                    messages.append(user_message(content))
                elif role == "assistant":
                    messages.append(assistant_message(content))
        messages.append(user_message(user_content))
        yield from self._llm.complete_stream(messages)
