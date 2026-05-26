"""归因 Agent：汇总子任务 DataFrame，产出 AttributionFacts。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from chatbi.domain.attribution_engine import AttributionEngine
from chatbi.domain.models import AnalysisPlan, AttributionFacts


class AttributionAgent:
    """封装 AttributionEngine，区分报告模式与指标归因模式。"""

    def __init__(self, engine: AttributionEngine) -> None:
        self._engine = engine

    def run(
        self,
        *,
        plan: AnalysisPlan,
        task_results: List[Dict[str, Any]],
        question: str = "",
    ) -> AttributionFacts:
        """从各子任务结果提取 DataFrame，调用引擎生成摘要与对比要点。"""
        frames: Dict[str, pd.DataFrame] = {}
        for r in task_results:
            df = r.get("dataframe")
            if isinstance(df, pd.DataFrame) and not df.empty:
                frames[r["task_id"]] = df

        if plan.report_mode:
            return self._engine.analyze_report(
                question=question,
                frames=frames,
                subject=plan.subject,
            )

        return self._engine.analyze(
            metric_name=plan.metric_name,
            frames=frames,
            subject=plan.subject,
        )
