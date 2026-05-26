from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from chatbi.domain.models import MetricDefinition, MetricMatch
from chatbi.infrastructure.metrics.metric_store import MetricStore

_AMBIGUOUS_SCORE_DELTA = 0.05

_TIME_SQL_FRAGMENTS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"本月"), "dt >= DATE_FORMAT(CURDATE(), '%Y-%m-01')"),
    (re.compile(r"上月|上个月"), "dt >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01') AND dt < DATE_FORMAT(CURDATE(), '%Y-%m-01')"),
    (re.compile(r"今年"), "dt >= DATE_FORMAT(CURDATE(), '%Y-01-01')"),
    (re.compile(r"上周"), "dt >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) + 7 DAY)"),
    (re.compile(r"最近\s*7\s*天|近7天"), "dt >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"),
    (re.compile(r"\d{4}年"), None),  # 由 _extract_time_filter 单独处理
]


class MetricResolver:
    """自然语言 → 指标匹配（规则 + 同义词，无额外 LLM 调用）。"""

    def __init__(self, store: MetricStore) -> None:
        self._store = store

    def resolve(self, question: str, *, min_score: float = 0.35) -> Optional[MetricMatch]:
        match, _ambiguous = self._resolve_scored(question, min_score=min_score)
        return match

    def resolve_with_ambiguity(
        self, question: str, *, min_score: float = 0.35
    ) -> Tuple[Optional[MetricMatch], bool]:
        return self._resolve_scored(question, min_score=min_score)

    def _resolve_scored(
        self, question: str, *, min_score: float
    ) -> Tuple[Optional[MetricMatch], bool]:
        q = question.strip().lower()
        ranked: List[Tuple[float, MetricDefinition]] = []
        for metric in self._store.list_metrics(status="published"):
            score = self._score_metric(q, metric)
            if score >= min_score:
                ranked.append((score, metric))
        if not ranked:
            return None, False

        ranked.sort(key=lambda x: x[0], reverse=True)
        top_score, top_metric = ranked[0]
        ambiguous = (
            len(ranked) > 1
            and (top_score - ranked[1][0]) < _AMBIGUOUS_SCORE_DELTA
        )
        match = self._build_match(question, top_metric, top_score)
        return match, ambiguous

    def _build_match(
        self, question: str, metric: MetricDefinition, score: float
    ) -> MetricMatch:
        time_filter = self._extract_time_filter(question, metric)
        return MetricMatch(
            metric=metric,
            score=score,
            filters=self._extract_filters(question, metric),
            dimensions=self._extract_dimensions(question, metric),
            time_filter=time_filter,
        )

    def _score_metric(self, q: str, metric: MetricDefinition) -> float:
        terms = [metric.name.lower(), metric.code.lower()]
        terms.extend(s.lower() for s in metric.synonyms)
        hit = sum(1 for t in terms if t and t in q)
        if hit == 0:
            return 0.0
        return min(1.0, 0.4 + 0.2 * hit)

    def _extract_filters(self, question: str, metric: MetricDefinition) -> Dict[str, str]:
        filters: Dict[str, str] = {}
        if "产品" in metric.dimensions or "product_name" in metric.dimensions:
            m = re.search(r"([A-Za-z0-9\u4e00-\u9fff]+)产品", question)
            if m:
                filters["product_name"] = m.group(1)
            m2 = re.search(r"产品([A-Za-z0-9\u4e00-\u9fff]+)", question)
            if m2:
                filters["product_name"] = m2.group(1)
        if "school_name" in metric.dimensions:
            m = re.search(
                r"([\u4e00-\u9fff]+(?:中学|学校|小学|大学))", question
            )
            if m:
                filters["school_name"] = m.group(1)
        return filters

    def _extract_dimensions(
        self, question: str, metric: MetricDefinition
    ) -> List[str]:
        dims: List[str] = []
        dim_defs = self._store.get_dimensions(metric.code)
        for d in dim_defs:
            if d.name and d.name in question:
                dims.append(d.code)
        hints = {
            "区域": "region",
            "渠道": "channel",
            "产品": "product_name",
            "学校": "school_name",
        }
        for zh, code in hints.items():
            if zh in question and code in metric.dimensions and code not in dims:
                dims.append(code)
        return dims

    def _extract_time_filter(
        self, question: str, metric: MetricDefinition
    ) -> Optional[str]:
        time_dims = {"dt", "date", "biz_date", "stat_date", "month"}
        if not time_dims.intersection(set(metric.dimensions)):
            dim_codes = {d.code for d in self._store.get_dimensions(metric.code)}
            if not time_dims.intersection(dim_codes):
                return None

        m_year = re.search(r"(\d{4})年", question)
        if m_year:
            y = m_year.group(1)
            return f"dt >= '{y}-01-01' AND dt < '{int(y) + 1}-01-01'"

        for pattern, fragment in _TIME_SQL_FRAGMENTS:
            if fragment and pattern.search(question):
                return fragment
        return None
