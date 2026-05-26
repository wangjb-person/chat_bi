"""分析通道内的查数 Agent：并行执行 Planner 下发的子任务。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import pandas as pd

from chatbi.domain.models import AnalysisSubTask, MetricMatch
from chatbi.services.query_pipeline import QueryPipeline


class QueryAgent:
    """查数 Agent：复用 QueryPipeline，供分析通道并行调用。"""

    def __init__(self, pipeline: QueryPipeline, *, max_workers: int = 4) -> None:
        self._pipeline = pipeline
        self._max_workers = max_workers

    def run_task(
        self,
        task: AnalysisSubTask,
        *,
        table_name: str = "",
        base_match: Optional[MetricMatch] = None,
    ) -> Dict[str, Any]:
        """执行单个子任务，返回 sql、dataframe、error 等。"""
        sql, df, err = self._pipeline.run_analysis_task(
            task, table_name=table_name, base_match=base_match
        )
        return {
            "task_id": task.id,
            "description": task.description,
            "sql": sql,
            "error": err,
            "row_count": len(df) if df is not None else 0,
            "dataframe": df,
        }

    def run_parallel(
        self,
        tasks: List[AnalysisSubTask],
        *,
        table_name: str = "",
        base_match: Optional[MetricMatch] = None,
    ) -> List[Dict[str, Any]]:
        """多子任务线程池并行查数，结果按 task_id 排序。"""
        if not tasks:
            return []
        if len(tasks) == 1:
            return [
                self.run_task(tasks[0], table_name=table_name, base_match=base_match)
            ]

        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(
                    self.run_task, t, table_name=table_name, base_match=base_match
                ): t
                for t in tasks
            }
            for fut in as_completed(futures):
                results.append(fut.result())
        results.sort(key=lambda r: r.get("task_id", ""))
        return results
