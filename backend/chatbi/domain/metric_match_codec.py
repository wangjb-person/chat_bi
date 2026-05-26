"""MetricMatch 与意图 entities 之间的序列化（避免重复 resolve）。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from chatbi.domain.models import MetricMatch
from chatbi.infrastructure.metrics.metric_store import MetricStore


def metric_match_to_entity(match: MetricMatch) -> Dict[str, Any]:
    return {
        "metric_code": match.metric.code,
        "score": match.score,
        "filters": dict(match.filters),
        "dimensions": list(match.dimensions),
        "time_filter": match.time_filter,
    }


def metric_match_from_entity(
    data: Any, store: MetricStore
) -> Optional[MetricMatch]:
    if not data or not isinstance(data, dict):
        return None
    code = data.get("metric_code")
    if not code:
        return None
    metric = store.get_metric(str(code))
    if metric is None:
        return None
    return MetricMatch(
        metric=metric,
        score=float(data.get("score", 1.0)),
        filters=dict(data.get("filters") or {}),
        dimensions=list(data.get("dimensions") or []),
        time_filter=data.get("time_filter"),
    )
