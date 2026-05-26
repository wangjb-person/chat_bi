from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from chatbi.domain.models import Intent, IntentResult
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message

log = logging.getLogger("chatbi")

_VALID_INTENTS = {i.value for i in Intent}


class LlmIntentClassifier:
    """
    市面 ChatBI 常用的 LLM 意图分类（结构化 JSON）。
    在规则不确定或「像查数但不在库内」时调用。
    """

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def classify(
        self,
        question: str,
        *,
        schema_hint: str = "",
        rule_hint: Optional[IntentResult] = None,
        conversation_history: str = "",
    ) -> IntentResult:
        rule_json = ""
        if rule_hint:
            rule_json = json.dumps(
                {
                    "intent": rule_hint.intent.value,
                    "confidence": rule_hint.confidence,
                    "reason": rule_hint.reason,
                },
                ensure_ascii=False,
            )

        messages = [
            system_message(
                "你是 ChatBI 意图分类器。根据用户问题与数据库能力范围，输出唯一 JSON，不要其它文字。\n"
                "字段：\n"
                '- intent: "query"|"analysis"|"chat"|"knowledge"|"clarify"\n'
                "- confidence: 0~1\n"
                '- in_schema: true/false（问题能否用给定表结构查询）\n'
                '- missing_slots: 数组，缺槽位如 metric, time_range, filter, threshold\n'
                '- reason: 简短中文\n'
                "分类标准：\n"
                "- query: 明确要查库内指标/列表/排名/统计\n"
                "- analysis: 为什么、原因、归因、异常分析\n"
                "- knowledge: 地理常识、行业科普、公司介绍等库外知识\n"
                "- chat: 笑话、闲聊、问候\n"
                "- clarify: 想查业务数据但缺指标定义/时间/对象/达标线\n"
                "若问题含「多少」但主题与表结构无关（如省份、车企），intent=knowledge，in_schema=false。"
            ),
            user_message(
                f"用户问题：{question}\n\n"
                f"当前库表能力（DDL 摘要）：\n{schema_hint or '未知'}\n\n"
                f"规则引擎初判：{rule_json or '无'}"
                + (
                    f"\n\n近期对话上文：\n{conversation_history}"
                    if conversation_history
                    else ""
                )
            ),
        ]

        try:
            raw = self._llm.complete(messages)
            data = self._parse_json(raw)
            return self._to_result(data)
        except Exception as e:
            log.warning("[intent] LLM 分类失败，回退规则: %s", e)
            if rule_hint:
                return rule_hint
            return IntentResult(
                intent=Intent.CHAT,
                confidence=0.5,
                reason="LLM 分类失败，默认对话",
            )

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        text = raw.strip()
        block = re.search(r"\{[\s\S]*\}", text)
        if block:
            text = block.group(0)
        return json.loads(text)

    def _to_result(self, data: Dict[str, Any]) -> IntentResult:
        intent_str = str(data.get("intent", "chat")).lower()
        if intent_str not in _VALID_INTENTS:
            intent_str = "chat"

        in_schema = data.get("in_schema", data.get("in_business_schema", True))
        if isinstance(in_schema, str):
            in_schema = in_schema.lower() in ("true", "1", "yes")

        intent = Intent(intent_str)
        if not in_schema and intent == Intent.QUERY:
            intent = Intent.KNOWLEDGE

        missing = data.get("missing_slots") or []
        if isinstance(missing, str):
            missing = [missing]

        return IntentResult(
            intent=intent,
            confidence=float(data.get("confidence", 0.75)),
            missing_slots=list(missing),
            reason=str(data.get("reason", "LLM 分类")),
            entities={"in_schema": in_schema},
        )
