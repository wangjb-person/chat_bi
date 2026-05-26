"""分析规划 Agent：将用户问题拆成 AnalysisPlan 与若干 AnalysisSubTask。"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from chatbi.domain.analysis_intent import extract_school_names, is_report_style_question
from chatbi.domain.models import AnalysisPlan, AnalysisSubTask, MetricDefinition, MetricMatch
from chatbi.domain.metric_resolver import MetricResolver
from chatbi.domain.sql_builder import MetricSqlBuilder
from chatbi.infrastructure.metrics.metric_store import MetricStore


class PlannerAgent:
    """分析任务规划：报告式多校对比 / 归因 / 探索。"""

    def __init__(
        self,
        resolver: MetricResolver,
        sql_builder: MetricSqlBuilder,
        store: MetricStore,
    ) -> None:
        self._resolver = resolver
        self._sql_builder = sql_builder
        self._store = store

    def plan(self, question: str, *, context: str = "") -> AnalysisPlan:
        """生成分析计划：报告模式拆多校子查询，否则按指标/探索任务拆分。"""
        effective = question
        if context.strip():
            effective = f"{question.strip()}\n\n【对话上文】\n{context.strip()}"
        report_mode = is_report_style_question(effective)
        match = self._resolver.resolve(effective)
        metric_code = match.metric.code if match else None
        subject: Dict[str, str] = {}

        if m := re.search(r"([A-Za-z0-9\u4e00-\u9fff]+)产品", effective):
            subject["product"] = m.group(1)

        schools = extract_school_names(effective)
        if schools:
            subject["schools"] = schools

        if match and match.filters:
            subject.update({k: str(v) for k, v in match.filters.items()})

        sub_tasks: List[AnalysisSubTask] = []

        if report_mode:
            sub_tasks = self._plan_report_tasks(effective, schools)
            return AnalysisPlan(
                metric_code=metric_code,
                metric_name="学生成绩对比报告",
                subject=subject,
                sub_tasks=sub_tasks,
                report_mode=True,
                metric_match=match,
            )

        if match and metric_code:
            sub_tasks = self._plan_metric_analysis_tasks(match, subject)
        else:
            sub_tasks = [
                AnalysisSubTask(
                    id="explore_1",
                    description="主指标查询",
                    question=effective.replace("为什么", "查询").replace("原因", ""),
                ),
                AnalysisSubTask(
                    id="explore_2",
                    description="维度对比",
                    question=f"按学校对比：{effective}",
                ),
            ]

        metric_name = match.metric.name if match else "业务指标"
        return AnalysisPlan(
            metric_code=metric_code,
            metric_name=metric_name,
            subject=subject,
            sub_tasks=sub_tasks,
            report_mode=False,
            metric_match=match,
        )

    def _plan_metric_analysis_tasks(
        self, match: MetricMatch, subject: Dict[str, str]
    ) -> List[AnalysisSubTask]:
        metric = match.metric
        product = subject.get("product")
        sql_map = self._sql_builder.build_comparison_tasks_sql(
            metric, product=product
        )
        dim_col = (
            metric.dimensions[0]
            if metric.dimensions
            else None
        )
        tasks: List[AnalysisSubTask] = [
            AnalysisSubTask(
                id="by_dimension",
                description=f"按维度拆解 {metric.name}",
                question=self._metric_question(metric, subject, by_dim=True),
                execution="metric",
                preset_sql=sql_map.get("by_dimension"),
                group_by=[dim_col] if dim_col else None,
            ),
            AnalysisSubTask(
                id="aggregate",
                description=f"汇总 {metric.name}",
                question=self._metric_question(metric, subject, by_dim=False),
                execution="metric",
                preset_sql=sql_map.get("aggregate"),
                group_by=[],
            ),
        ]
        return tasks

    def _plan_report_tasks(
        self, question: str, schools: List[str]
    ) -> List[AnalysisSubTask]:
        school_hint = "、".join(schools) if schools else "相关学校"
        base = f"针对{school_hint}，使用数据库已有字段（如 school_name、student_name、total_score、rank_num 等）"
        return [
            AnalysisSubTask(
                id="school_overview",
                description="各校整体成绩指标",
                question=(
                    f"{base}，按学校分组统计：学生人数、总分平均分、总分中位数、"
                    f"总分标准差、优秀率（或等价指标），输出中文列名。"
                ),
            ),
            AnalysisSubTask(
                id="score_segments",
                description="各校分数段分布",
                question=(
                    f"{base}，按学校统计总分在 700 分以上、650-700 分、650 分以下的人数，"
                    f"用中文列名展示。"
                ),
            ),
            AnalysisSubTask(
                id="top_students",
                description="各校优秀学生样本",
                question=(
                    f"{base}，按学校分别查询总分排名前 5 名学生（姓名、总分、排名），"
                    f"用中文列名展示。"
                ),
            ),
        ]

    def _metric_question(
        self,
        metric: MetricDefinition,
        subject: Dict[str, str],
        *,
        by_dim: bool,
    ) -> str:
        parts = [f"查询{metric.name}"]
        if subject.get("product"):
            parts.append(f"产品{subject['product']}")
        if by_dim and metric.dimensions:
            parts.append(f"按{metric.dimensions[0]}分组")
        return "，".join(parts)
