"""
意图打分模块：为 query / analysis / chat / knowledge / clarify 五类分别累加得分。

与 IntentRouter 配合：先 score，再 apply_capability_gate（指标+语义否决），最后 warehouse_gate。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from chatbi.domain.analysis_intent import extract_school_names, is_report_style_question
from chatbi.domain.models import Intent
from chatbi.domain.metric_match_codec import metric_match_to_entity
from chatbi.domain.question_scope import (
    evaluate_warehouse_eligibility,
    has_business_domain_signals,
    is_general_knowledge_question,
    is_list_entity_query,
    is_product_or_meta_question,
    resolve_metric_boost,
    resolve_metric_match,
)
from chatbi.domain.schema_scope import SchemaScopeChecker

_CHAT_PATTERNS = [
    re.compile(p)
    for p in [
        r"笑话|段子",
        r"讲个?故事|讲故事|说个?故事",
        r"逗我|猜谜|写诗",
        r"你好|您好|早上好|晚上好",
        r"谢谢|感谢",
        r"你是谁|你叫什么",
        r"聊天|闲聊",
    ]
]

_KNOWLEDGE_PATTERNS = [
    re.compile(p)
    for p in [
        r"(?:公司|企业|集团|股份).*介绍",
        r"介绍.*(?:公司|企业|集团)",
        r"简介|背景|发展历程",
        r"成立于哪|总部在哪|创始人",
        r"是什么|啥是|何为",
        r"行政区域|行政区|辖区|地级市|省份",
        r"有哪些|有什么|包括哪些|列举",
    ]
]

_DATA_QUERY_PATTERNS = [
    re.compile(p)
    for p in [
        r"多少",
        r"有几个|有多少",
        r"查[一下询]?",
        r"统计|汇总|合计",
        r"排名|第几|前几|top\s*\d",
        r"趋势|同比|环比",
        r"标准差|方差|中位数|平均(?:分|值)",
        r"销售额|营收|毛利|成本|订单",
        r"人数|学生|成绩|总分",
        r"(?:中学|学校).*(?:多少|排名|成绩|标准差)",
        r"低于|高于|大于|小于|不少于|不超过",
        r"语文|数学|英语|物理|化学|生物|政治|地理",
        r"历史成绩|历史分数|历史科目|历史课",
        r"(?:有哪些|有什么).*(?:学生|人|名单)",
        r"(?:学生|人).*(?:有哪些|有什么|名单)",
    ]
]

_ANALYSIS_PATTERNS = [
    re.compile(p)
    for p in [
        r"为什么",
        r"什么原因",
        r"归因",
        r"分析一下",
        r"分析.*主要",
        r"(?:数据|销售|业绩|毛利).*(?:下降|上升|异常)",
    ]
]

_BUSINESS_INCOMPLETE_PATTERNS = [
    re.compile(p)
    for p in [
        r"达标|达标了吗|是否达标",
        r"完成率|达成率|转化率",
        r"KPI|指标.*怎么样",
        r"业绩.*如何|表现.*如何",
    ]
]

_SCORE_FLOOR = 0.05


@dataclass
class ScoredIntent:
    """单轮意图打分的输出。"""

    intent: Intent
    confidence: float
    scores: Dict[str, float] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    margin: float = 0.0


@dataclass
class WarehouseGateResult:
    """统一判断问题是否应由业务库回答。"""
    can_query: bool
    can_analyze: bool
    redirect_intent: Optional[Intent] = None
    reason: str = ""


class IntentScorer:
    """基于正则与指标匹配的多通道意图打分器。"""

    def __init__(
        self,
        *,
        metric_resolver: Optional[Any] = None,
    ) -> None:
        """metric_resolver 用于指标层加权与能力门控。"""
        self._metric_resolver = metric_resolver

    def score(self, question: str) -> ScoredIntent:
        """对问题各通道打分并取最高分，写入 entities.scores 便于调试。"""
        q = question.strip()
        scores: Dict[str, float] = {i.value: _SCORE_FLOOR for i in Intent}
        entities: Dict[str, Any] = {}

        if m := re.search(r"([A-Za-z0-9\u4e00-\u9fff]+)产品", q):
            entities["product"] = m.group(1)

        chat_hits = self._count_hits(q, _CHAT_PATTERNS)
        knowledge_hits = self._count_hits(q, _KNOWLEDGE_PATTERNS)
        data_hits = self._count_hits(q, _DATA_QUERY_PATTERNS)
        analysis_hits = self._count_hits(q, _ANALYSIS_PATTERNS)
        business = has_business_domain_signals(q)
        list_entity_query = is_list_entity_query(q)

        # --- chat ---
        if chat_hits:
            scores[Intent.CHAT.value] += 0.45 + 0.12 * chat_hits

        # --- product / meta / 通识 ---
        if is_product_or_meta_question(q):
            scores[Intent.KNOWLEDGE.value] += 1.15
            entities["product_meta"] = True
        if is_general_knowledge_question(q):
            scores[Intent.KNOWLEDGE.value] += 0.95
            scores[Intent.QUERY.value] -= 0.35

        # --- metric-first ---
        metric_match, metric_ambiguous = resolve_metric_match(q, self._metric_resolver)
        metric_boost = (
            min(0.55, 0.28 + metric_match.score * 0.45) if metric_match else 0.0
        )
        if metric_ambiguous:
            entities["metric_ambiguous"] = True
        if metric_match:
            entities["metric_match"] = metric_match_to_entity(metric_match)
        if metric_boost > 0:
            scores[Intent.QUERY.value] += metric_boost
            entities["metric_boost"] = metric_boost
            if re.search(r"为什么|原因|归因|报告", q):
                scores[Intent.ANALYSIS.value] += 0.35 + metric_boost * 0.5

        # --- query ---
        if data_hits:
            scores[Intent.QUERY.value] += 0.28 + 0.1 * min(data_hits, 4)
        if business:
            scores[Intent.QUERY.value] += 0.32
        if list_entity_query:
            scores[Intent.QUERY.value] += 0.55
            scores[Intent.KNOWLEDGE.value] -= 0.35

        # --- knowledge（库外 / 介绍 / 纯「有哪些」）---
        if knowledge_hits:
            scores[Intent.KNOWLEDGE.value] += 0.18 * knowledge_hits
        if "介绍" in q and not business and data_hits == 0:
            scores[Intent.KNOWLEDGE.value] += 0.45
        if (
            re.search(r"有哪些|有什么|包括哪些", q)
            and data_hits == 0
            and not business
            and not list_entity_query
        ):
            scores[Intent.KNOWLEDGE.value] += 0.42
        if re.search(r"行政区域|行政区|省份|直辖市|自治区|地级市", q):
            scores[Intent.KNOWLEDGE.value] += 0.5
            scores[Intent.QUERY.value] -= 0.2

        # --- analysis ---
        report_mode = is_report_style_question(q)
        if report_mode:
            entities["report_mode"] = True
            scores[Intent.ANALYSIS.value] += 0.92
        if analysis_hits and re.search(r"为什么|原因|归因", q):
            scores[Intent.ANALYSIS.value] += 0.75 + 0.08 * analysis_hits
        if analysis_hits and re.search(r"分析", q) and re.search(
            r"中学|学校|成绩|整体|销售|毛利|营收", q
        ):
            entities["report_mode"] = entities.get("report_mode", True)
            scores[Intent.ANALYSIS.value] += 0.68
        if analysis_hits and not report_mode:
            scores[Intent.ANALYSIS.value] += 0.22 + 0.06 * analysis_hits

        if extract_school_names(q):
            scores[Intent.QUERY.value] += 0.15
            if report_mode or (analysis_hits and re.search(r"分析", q)):
                scores[Intent.ANALYSIS.value] += 0.2

        # 默认略偏向 knowledge，避免误 SQL（无其它信号时）
        if max(scores.values()) <= _SCORE_FLOOR + 0.02:
            scores[Intent.KNOWLEDGE.value] = 0.55

        intent, confidence, margin, reason = self._pick_winner(scores)
        entities["scores"] = {k: round(v, 3) for k, v in scores.items()}
        if metric_boost > 0:
            entities.setdefault("metric_boost", metric_boost)

        return ScoredIntent(
            intent=intent,
            confidence=confidence,
            scores=entities["scores"],
            entities=entities,
            reason=reason,
            margin=margin,
        )

    def apply_capability_gate(
        self,
        question: str,
        scored: ScoredIntent,
        *,
        scope: SchemaScopeChecker,
        schema_hint: str = "",
    ) -> ScoredIntent:
        """指标层 + 语义层一票否决：未对齐业务库不得 query/analysis。"""
        elig = evaluate_warehouse_eligibility(
            question,
            scope,
            schema_hint=schema_hint,
            metric_resolver=self._metric_resolver,
        )
        entities = dict(scored.entities)
        entities["warehouse_source"] = elig.source
        entities["warehouse_reason"] = elig.reason
        if elig.metric_boost > 0:
            entities["metric_boost"] = elig.metric_boost

        if scored.intent == Intent.QUERY and not elig.can_query:
            return ScoredIntent(
                intent=Intent.KNOWLEDGE,
                confidence=0.88,
                scores=entities.get("scores", {}),
                entities=entities,
                reason=f"能力门控→知识：{elig.reason}",
                margin=0.4,
            )
        if scored.intent == Intent.ANALYSIS and not elig.can_analyze:
            return ScoredIntent(
                intent=Intent.KNOWLEDGE,
                confidence=0.86,
                scores=entities.get("scores", {}),
                entities=entities,
                reason=f"能力门控→知识：{elig.reason}",
                margin=0.35,
            )
        scored.entities = entities
        return scored

    def warehouse_gate(
        self,
        question: str,
        intent: Intent,
        *,
        scope: SchemaScopeChecker,
        schema_hint: str = "",
        entities: Optional[Dict[str, Any]] = None,
    ) -> WarehouseGateResult:
        """根据最终意图判断能否查库/分析，必要时建议重定向到 knowledge。"""
        q = question.strip()

        elig = evaluate_warehouse_eligibility(
            q,
            scope,
            schema_hint=schema_hint,
            metric_resolver=self._metric_resolver,
        )

        if intent == Intent.QUERY and not elig.can_query:
            return WarehouseGateResult(
                can_query=False,
                can_analyze=False,
                redirect_intent=Intent.KNOWLEDGE,
                reason=elig.reason,
            )
        if intent == Intent.ANALYSIS and not elig.can_analyze:
            return WarehouseGateResult(
                can_query=False,
                can_analyze=False,
                redirect_intent=Intent.KNOWLEDGE,
                reason=elig.reason,
            )
        return WarehouseGateResult(
            can_query=elig.can_query,
            can_analyze=elig.can_analyze,
        )

    def needs_clarify(self, question: str) -> bool:
        """业务问法不完整（缺指标/时间/对象）或多指标歧义时需澄清。"""
        q = question.strip()
        if self._metric_resolver is not None:
            _, ambiguous = resolve_metric_match(q, self._metric_resolver)
            if ambiguous:
                return True
        if not any(p.search(q) for p in _BUSINESS_INCOMPLETE_PATTERNS):
            return False
        has_time = bool(re.search(r"\d{4}|今年|本月|上周|最近|Q[1-4]|季度|月份", q))
        has_object = bool(
            re.search(r"团队|部门|区域|产品|学校|班级|张三|李四|王", q)
        )
        return not (has_time and has_object)

    @staticmethod
    def infer_missing_slots(question: str) -> List[str]:
        """推断澄清模式下用户需补充的槽位名称列表。"""
        q = question.strip()
        slots: List[str] = []
        if not re.search(r"完成率|销售额|毛利|转化率|KPI|指标", q):
            slots.append("metric")
        if not re.search(r"\d{4}|今年|本月|上周|最近|季度", q):
            slots.append("time_range")
        if not re.search(r"团队|部门|谁|哪一|学校|产品", q):
            slots.append("filter_object")
        if "达标" in q and not re.search(r"\d+%|百分之|>[=]?|<[=]?", q):
            slots.append("threshold")
        return slots or ["metric", "time_range"]

    @staticmethod
    def _count_hits(q: str, patterns: List[re.Pattern[str]]) -> int:
        """统计问题命中某组正则的条数。"""
        return sum(1 for p in patterns if p.search(q))

    @staticmethod
    def _pick_winner(
        scores: Dict[str, float],
    ) -> Tuple[Intent, float, float, str]:
        """取得分最高通道；分差过小时压低 confidence 以触发 LLM 仲裁。"""
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_key, top_val = ordered[0]
        second_val = ordered[1][1] if len(ordered) > 1 else _SCORE_FLOOR
        margin = top_val - second_val
        intent = Intent(top_key)
        confidence = min(0.98, top_val / max(top_val + 0.15, 1.0))
        if margin < 0.08:
            confidence = min(confidence, 0.72)
        reason = f"打分：{top_key}={top_val:.2f}，次高差={margin:.2f}"
        return intent, confidence, margin, reason
