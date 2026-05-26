"""
意图路由入口：将用户自然语言问题分到 query / analysis / chat / knowledge / clarify。

流程：规则打分 → 指标/语义能力门控 →（可选）LLM 仲裁 → 返回 IntentResult。
多轮场景下调用方应传入 LLM 改写后的 score_question。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from chatbi.application.llm_intent_classifier import LlmIntentClassifier
from chatbi.core.conversation_context import format_history_for_llm_classifier
from chatbi.domain.intent_scoring import IntentScorer, ScoredIntent
from chatbi.domain.metric_resolver import MetricResolver
from chatbi.domain.models import Intent, IntentResult
from chatbi.domain.question_scope import resolve_metric_match
from chatbi.domain.schema_scope import SchemaScopeChecker
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.vector.schema_cache import SchemaContextCache

_LLM_BAND_LOW = 0.55
_LLM_BAND_HIGH = 0.85
_LLM_MARGIN_TRIGGER = 0.10

_HIGH_CONF_FLOOR: dict[Intent, float] = {
    Intent.CHAT: 0.9,
    Intent.KNOWLEDGE: 0.82,
    Intent.ANALYSIS: 0.88,
}


class IntentRouter:
    """混合意图识别：规则打分为主，灰区可选 LLM 仲裁。"""

    def __init__(
        self,
        *,
        llm: Optional[LlmClient] = None,
        schema_cache: Optional[SchemaContextCache] = None,
        metric_resolver: Optional[MetricResolver] = None,
        enable_llm: bool = False,
    ) -> None:
        self._schema_cache = schema_cache
        self._scope = SchemaScopeChecker()
        self._scorer = IntentScorer(metric_resolver=metric_resolver)
        self._llm_classifier: Optional[LlmIntentClassifier] = (
            LlmIntentClassifier(llm) if enable_llm and llm is not None else None
        )

    def route(
        self,
        question: str,
        *,
        table_name: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
        score_question: Optional[str] = None,
    ) -> IntentResult:
        """question 为当前原句；score_question 为改写后用于打分的问句（默认同 question）。"""
        del table_name
        original = question.strip()
        score_q = (score_question or original).strip()
        if not score_q:
            return IntentResult(intent=Intent.CLARIFY, confidence=1.0, reason="问题为空")

        if self._scorer.needs_clarify(score_q):
            _, ambiguous = resolve_metric_match(score_q, self._scorer._metric_resolver)
            return self._clarify_result(score_q, ambiguous)

        hint, _, scope = self._cached_scope()
        scored = self._scorer.score(score_q)
        scored = self._scorer.apply_capability_gate(
            score_q, scored, scope=scope, schema_hint=hint
        )
        result = self._scored_to_result(scored)
        result = self._apply_warehouse_gate(score_q, result, scope_ctx=(hint, scope))

        if (
            result.intent == Intent.KNOWLEDGE
            and self._scope.is_out_of_business_schema(score_q, schema_hint="")
        ):
            label = self._scope.out_of_domain_label(score_q) or "库外"
            result = IntentResult(
                intent=Intent.KNOWLEDGE,
                confidence=0.88,
                entities=result.entities,
                reason=f"库外域({label})：{result.reason}",
            )

        floor = _HIGH_CONF_FLOOR.get(result.intent)
        if floor is not None and result.confidence >= floor:
            return result
        if result.intent == Intent.CLARIFY:
            return result

        margin = float(scored.entities.get("_margin", scored.margin))
        in_llm_band = _LLM_BAND_LOW <= result.confidence < _LLM_BAND_HIGH
        use_llm = self._llm_classifier and (
            in_llm_band or margin < _LLM_MARGIN_TRIGGER
        )
        if not use_llm:
            return result

        history_block = format_history_for_llm_classifier(messages, original)
        llm_result = self._llm_classifier.classify(
            original,
            schema_hint=hint,
            rule_hint=result,
            conversation_history=history_block,
        )
        merged = self._merge(result, llm_result, score_q, scope, hint)
        return self._apply_warehouse_gate(score_q, merged, scope_ctx=(hint, scope))

    def _clarify_result(self, score_q: str, ambiguous: bool) -> IntentResult:
        slots, reason = (
            (["metric"], "匹配到多个相近指标，请说明要查哪一项")
            if ambiguous
            else (
                self._scorer.infer_missing_slots(score_q),
                "业务查数缺指标/时间/对象",
            )
        )
        return IntentResult(
            intent=Intent.CLARIFY, confidence=0.85, missing_slots=slots, reason=reason
        )

    def _scored_to_result(self, scored: ScoredIntent) -> IntentResult:
        entities = dict(scored.entities)
        entities["_margin"] = scored.margin
        return IntentResult(
            intent=scored.intent,
            confidence=scored.confidence,
            entities=entities,
            reason=scored.reason,
        )

    def _apply_warehouse_gate(
        self,
        q: str,
        rule: IntentResult,
        *,
        scope_ctx: Optional[Tuple[str, SchemaScopeChecker]] = None,
    ) -> IntentResult:
        if scope_ctx is None:
            hint, _, scope = self._cached_scope()
        else:
            hint, scope = scope_ctx[0], scope_ctx[1]
        gate = self._scorer.warehouse_gate(
            q, rule.intent, scope=scope, schema_hint=hint, entities=rule.entities
        )
        if gate.redirect_intent is not None:
            ent = {**rule.entities, **({"product_meta": True} if gate.reason.startswith("产品") else {})}
            return IntentResult(
                intent=gate.redirect_intent,
                confidence=max(rule.confidence, 0.86),
                entities=ent,
                reason=f"库范围：{gate.reason}",
            )
        if rule.intent == Intent.ANALYSIS and rule.entities.get("report_mode"):
            rule.entities["report_mode"] = True
        return rule

    def _cached_scope(self) -> Tuple[str, List[str], SchemaScopeChecker]:
        if self._schema_cache:
            return self._schema_cache.get()
        return "", [], self._scope

    def _merge(
        self,
        rule: IntentResult,
        llm: IntentResult,
        q: str,
        scope: SchemaScopeChecker,
        schema_hint: str,
    ) -> IntentResult:
        if scope.is_out_of_business_schema(q, schema_hint=schema_hint):
            if llm.intent == Intent.QUERY:
                return IntentResult(
                    intent=Intent.KNOWLEDGE,
                    confidence=max(llm.confidence, 0.85),
                    entities=rule.entities,
                    reason="LLM+库表范围：库外问题",
                )

        if llm.confidence >= rule.confidence:
            if llm.missing_slots:
                return llm
            if llm.intent == Intent.CLARIFY or (
                llm.intent == Intent.QUERY and self._scorer.needs_clarify(q)
            ):
                return IntentResult(
                    intent=Intent.CLARIFY,
                    confidence=llm.confidence,
                    missing_slots=llm.missing_slots or self._scorer.infer_missing_slots(q),
                    reason=llm.reason,
                    entities=rule.entities,
                )
            merged = llm
            merged.entities = {**rule.entities, **(llm.entities or {})}
            return merged

        return rule
