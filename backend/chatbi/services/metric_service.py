from __future__ import annotations

from typing import Any, Dict, List, Optional

from chatbi.domain.metric_resolver import MetricResolver
from chatbi.domain.models import MetricDefinition
from chatbi.domain.sql_builder import MetricSqlBuilder
from chatbi.infrastructure.metrics.metric_store import MetricStore


class MetricService:
    def __init__(self, store: MetricStore, resolver: MetricResolver) -> None:
        self._store = store
        self._resolver = resolver
        self._sql_builder = MetricSqlBuilder(store)

    def list_metrics(self) -> List[MetricDefinition]:
        return self._store.list_metrics()

    def get_metric(self, code: str) -> Optional[MetricDefinition]:
        return self._store.get_metric(code)

    def upsert(self, payload: Dict[str, Any]) -> MetricDefinition:
        return self._store.upsert_metric(payload)

    def delete(self, code: str) -> bool:
        return self._store.delete_metric(code)

    def resolve_question(self, question: str) -> Dict[str, Any]:
        match = self._resolver.resolve(question)
        if not match:
            return {"matched": False}
        sql = self._sql_builder.build(match)
        return {
            "matched": True,
            "metric_code": match.metric.code,
            "metric_name": match.metric.name,
            "score": match.score,
            "sql": sql,
            "filters": match.filters,
            "dimensions": match.dimensions,
        }
