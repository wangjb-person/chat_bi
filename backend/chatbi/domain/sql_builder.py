from __future__ import annotations

from typing import Dict, List, Optional

from chatbi.domain.models import MetricDefinition, MetricMatch
from chatbi.infrastructure.metrics.metric_store import MetricStore


class MetricSqlBuilder:
    """由指标定义生成受控 SQL（口径由配置决定，不由 LLM 改写公式）。"""

    def __init__(self, store: MetricStore) -> None:
        self._store = store

    def build(
        self,
        match: MetricMatch,
        *,
        group_by: Optional[List[str]] = None,
        time_filter: Optional[str] = None,
        limit: int = 200,
    ) -> str:
        metric = match.metric
        table = metric.base_table
        expr = metric.expression
        selects = [f"{expr} AS `{metric.name}`"]
        if group_by is not None:
            group_cols = group_by
        else:
            group_cols = list(match.dimensions or [])

        dim_defs = self._store.get_dimensions(metric.code)
        dim_expr_map = {d.code: d.column_expr for d in dim_defs}

        for col in group_cols:
            expr_col = dim_expr_map.get(col, col)
            selects.insert(0, f"{expr_col} AS `{col}`")

        where_parts: List[str] = []
        for key, val in match.filters.items():
            col = dim_expr_map.get(key, key)
            safe_val = str(val).replace("'", "''")
            where_parts.append(f"{col} = '{safe_val}'")

        if time_filter or match.time_filter:
            where_parts.append(time_filter or match.time_filter)

        table_sql = table if "`" in table else f"`{table}`"
        sql = f"SELECT {', '.join(selects)} FROM {table_sql}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if group_cols:
            sql += " GROUP BY " + ", ".join(
                dim_expr_map.get(c, c) for c in group_cols
            )
        sql += f" LIMIT {int(limit)}"
        return sql

    def build_comparison_tasks_sql(
        self, metric: MetricDefinition, *, product: Optional[str] = None
    ) -> Dict[str, str]:
        """为归因分析生成本期/上期按维度拆解 SQL。"""
        match = MetricMatch(metric=metric, score=1.0, filters={})
        if product:
            match.filters["product_name"] = product
        by_region = self.build(
            match,
            group_by=["region"] if "region" in metric.dimensions else metric.dimensions[:1],
        )
        current = self.build(match, group_by=[])
        return {"by_dimension": by_region, "aggregate": current}
