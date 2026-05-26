"""
问题范围与「能否查库」判断（语义层 + 指标层门控）。

供 IntentScorer.apply_capability_gate / warehouse_gate 使用，避免误将通识、库外问题送入 SQL。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional

from chatbi.domain.analysis_intent import extract_school_names, is_report_style_question
from chatbi.domain.schema_scope import SchemaScopeChecker

_GENERAL_KNOWLEDGE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"清朝|明朝|唐朝|宋朝|元朝|民国|汉代|秦代|周朝",
        r"皇帝|太后|太子|大臣|登基|年号|驾崩",
        r"Python|Java|C\+\+|JavaScript|Go语言|Rust",
        r"编程语言|数据类型|语法|面向对象|函数式编程",
        r"物理定律|化学元素|生物分类|数学题",
    ]
]

_DATA_QUERY_SHAPE = re.compile(
    r"多少|有几个|有多少|排名|第几|统计|汇总|查[一下询]"
)

# 问系统能力、非 MySQL 业务字段
_PRODUCT_META_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in [
        r"MCP",
        r"skills?",
        r"\bCursor\b",
        r"Agent\s*工作流|多\s*Agent|意图识别|意图路由",
        r"NL2SQL|Text[- ]?to[- ]?SQL",
        r"Chroma|向量库|语料管理|语料训练",
        r"ChatBI\s*架构|ARCHITECTURE|AskOrchestrator",
        r"SSE|前端\s*Vue|pinia",
        r"MetricStore|指标层\s*JSON",
        r"PlannerAgent|ReporterAgent|QueryPipeline",
    ]
]

_IN_DOMAIN_SIGNAL = re.compile(
    r"学生|考生|成绩|总分|排名|标准差|方差|平均分|"
    r"学校|中学|小学|班级|年级|"
    r"销售|订单|营收|毛利|产品|区域|渠道|"
    r"完成率|达标|KPI|目标值|gy_[a-z_]+"
)

_EN_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9_]{1,}\b")
_ZH_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,8}")


def is_product_or_meta_question(question: str) -> bool:
    """是否为 ChatBI/MCP/Skills 等产品能力问题（非业务表字段）。"""
    q = question.strip()
    if not q:
        return False
    if any(p.search(q) for p in _PRODUCT_META_PATTERNS):
        return True
    # 「当前的 X 与 Y」且 X/Y 为纯英文技术词
    if re.search(r"分析|介绍|说明|对比", q):
        tech = re.findall(r"\b[A-Za-z]{2,}\b", q)
        if tech and len(tech) >= 2 and not _IN_DOMAIN_SIGNAL.search(q):
            lowered = {t.lower() for t in tech}
            if lowered <= {"mcp", "skill", "skills", "api", "llm", "rag", "agent"} or (
                "mcp" in lowered or "skill" in lowered
            ):
                return True
    return False


def has_business_domain_signals(question: str) -> bool:
    """是否包含学生/学校/成绩/销售等业务域关键词。"""
    return bool(_IN_DOMAIN_SIGNAL.search(question.strip()))


def is_general_knowledge_question(question: str) -> bool:
    """历史/编程等通识，非当前业务库可答。"""
    q = question.strip()
    if not q:
        return False
    if any(p.search(q) for p in _GENERAL_KNOWLEDGE_PATTERNS):
        return True
    if re.search(r"是什么|啥是|何为|介绍", q) and not has_business_domain_signals(q):
        if re.search(
            r"语言|编程|朝代|皇帝|帝国|定理|概念|原理", q
        ):
            return True
    return False


def is_list_entity_query(question: str) -> bool:
    """是否为「学生/人员有哪些」类列表查数（非行政区划等通识「有哪些」）。"""
    q = question.strip()
    return bool(
        re.search(r"有哪些|有什么|名单", q) and re.search(r"学生|人|考生", q)
    )


@dataclass
class WarehouseEligibility:
    """语义层 + 指标层对齐结果（助睿类「能否查库」前置判断）。"""

    can_query: bool
    can_analyze: bool
    reason: str
    metric_boost: float = 0.0
    source: str = ""


def resolve_metric_boost(question: str, metric_resolver: Any) -> float:
    """将指标匹配结果转为意图打分用的加权值（0~0.55）。"""
    match, _ = resolve_metric_match(question, metric_resolver)
    if match is None:
        return 0.0
    return min(0.55, 0.28 + match.score * 0.45)


def resolve_metric_match(
    question: str, metric_resolver: Any
) -> tuple[Any, bool]:
    """返回 (MetricMatch|None, 是否多指标歧义)。"""
    if metric_resolver is None:
        return None, False
    try:
        if hasattr(metric_resolver, "resolve_with_ambiguity"):
            return metric_resolver.resolve_with_ambiguity(question)
        match = metric_resolver.resolve(question)
        return match, False
    except Exception:
        return None, False


def evaluate_warehouse_eligibility(
    question: str,
    scope: SchemaScopeChecker,
    *,
    schema_hint: str = "",
    metric_resolver: Any = None,
) -> WarehouseEligibility:
    """
    指标层 + 语义层门控：未对齐业务库则不得走 query/analysis。
    """
    q = question.strip()
    metric_boost = resolve_metric_boost(q, metric_resolver)

    if is_product_or_meta_question(q):
        return WarehouseEligibility(
            False, False, "产品/系统问题", metric_boost, "product_meta"
        )
    if is_general_knowledge_question(q):
        return WarehouseEligibility(
            False, False, "通识/库外主题", metric_boost, "general_knowledge"
        )
    if scope.is_out_of_business_schema(q, schema_hint=schema_hint):
        label = scope.out_of_domain_label(q) or "库外"
        return WarehouseEligibility(
            False, False, f"与业务库无关（{label}）", metric_boost, "out_of_domain"
        )

    report_mode = is_report_style_question(q)
    can_analyze = analysis_is_grounded(
        q,
        report_mode=report_mode,
        scope=scope,
        schema_hint=schema_hint,
    )

    if metric_boost >= 0.28:
        return WarehouseEligibility(
            True, can_analyze, "命中指标层", metric_boost, "metric"
        )
    if has_business_domain_signals(q):
        return WarehouseEligibility(
            True, can_analyze, "业务域实体对齐", metric_boost, "business"
        )
    if extract_school_names(q):
        return WarehouseEligibility(
            True, True, "学校实体对齐", metric_boost, "school"
        )
    if is_list_entity_query(q):
        return WarehouseEligibility(
            True, True, "业务列表查数", metric_boost, "list_query"
        )
    if aligns_with_business_schema(q, scope, schema_hint=schema_hint):
        return WarehouseEligibility(
            True, can_analyze, "DDL/词表对齐", metric_boost, "schema"
        )
    if _DATA_QUERY_SHAPE.search(q):
        return WarehouseEligibility(
            False,
            False,
            "查数句式但未对齐指标/语义层",
            metric_boost,
            "ungrounded_query",
        )

    return WarehouseEligibility(
        False, False, "无法映射到业务库", metric_boost, "default"
    )


def aligns_with_business_schema(
    question: str,
    scope: SchemaScopeChecker,
    *,
    schema_hint: str = "",
) -> bool:
    """问题核心词与 DDL 词表 / 业务域信号有足够重叠。"""
    q = question.strip()
    if not q:
        return False
    if has_business_domain_signals(q):
        return True
    if extract_school_names(q):
        return True

    hint, vocab = schema_hint, []
    # scope 可能带 vocab，通过 is_out 的反向逻辑：若在 hint/vocab 有命中则对齐
    if scope.is_out_of_business_schema(q, schema_hint=hint):
        return False
    # is_out 返回 False 表示可能库内或未知；有 vocab/hint 时再验英文词
    q_lower = q.lower()
    for token in _EN_TOKEN.findall(q):
        tl = token.lower()
        if len(tl) >= 3 and tl in {v.lower() for v in getattr(scope, "_vocab", set())}:
            return True
    if hint:
        for t in _ZH_TOKEN.findall(q):
            if t in hint:
                return True
    return False


def analysis_is_grounded(
    question: str,
    *,
    report_mode: bool,
    scope: SchemaScopeChecker,
    schema_hint: str = "",
) -> bool:
    """是否具备走分析通道（多步查库+报告）的业务依据。"""
    q = question.strip()
    if is_product_or_meta_question(q):
        return False

    if report_mode or is_report_style_question(q):
        if extract_school_names(q) or has_business_domain_signals(q):
            return True
        return aligns_with_business_schema(q, scope, schema_hint=schema_hint)

    if re.search(r"为什么|原因|归因", q):
        return has_business_domain_signals(q) or aligns_with_business_schema(
            q, scope, schema_hint=schema_hint
        )

    if re.search(r"分析", q) and re.search(r"中学|学校|成绩|整体|销售|毛利|营收", q):
        return True

    return aligns_with_business_schema(q, scope, schema_hint=schema_hint)
