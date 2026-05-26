"""报告 Agent：根据子任务数据与归因事实生成 Markdown 分析报告。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from chatbi.domain.models import AttributionFacts, AnalysisPlan
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message


class ReporterAgent:
    """报告 Agent：基于查询结果与 facts 生成 Markdown 报告。"""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def build_report(
        self,
        *,
        question: str,
        plan: AnalysisPlan,
        facts: AttributionFacts,
        task_results: List[Dict[str, Any]],
        conversation_context: str = "",
    ) -> str:
        """调用 LLM 写报告；失败时用模板 fallback。"""
        data_section = self._format_task_data(task_results)
        facts_text = (
            f"摘要：{facts.summary}\n"
            f"对比条目：{facts.comparisons[:30]}\n"
            f"备注：{facts.raw_notes}"
        )
        context_block = ""
        if conversation_context.strip():
            context_block = f"\n对话上文：\n{conversation_context.strip()}\n"

        if plan.report_mode:
            system = (
                "你是教育数据分析报告撰写助手。用户需要「报告式」分析，不是简单列表。\n"
                "规则：\n"
                "1. 只能使用下方「查询结果数据」中的数字，禁止编造\n"
                "2. 结构：## 分析结论（2-4句）→ ## 数据概览（用 Markdown 表格复述关键指标）"
                "→ ## 对比分析 → ## 建议（3条以内）\n"
                "3. 不要写「以下为通用知识」「非数据库查询」等套话\n"
                "4. 若某子查询失败，在报告中说明哪一步无数据"
            )
        else:
            system = (
                "你是商业数据分析报告撰写助手。\n"
                "只能使用分析依据中的数字；结构：结论摘要、原因分析、数据依据、建议。"
            )

        messages = [
            system_message(system),
            user_message(
                f"用户问题：{question}\n"
                f"{context_block}"
                f"分析对象：{plan.subject}\n"
                f"分析依据：\n{facts_text}\n\n"
                f"查询结果数据：\n{data_section}"
            ),
        ]
        try:
            return self._llm.complete(messages)
        except Exception:
            return self._fallback_report(question, plan, facts, task_results)

    def _format_task_data(self, task_results: List[Dict[str, Any]]) -> str:
        blocks: List[str] = []
        for r in task_results:
            title = r.get("description") or r.get("task_id")
            task_id = r.get("task_id", "")
            err = r.get("error")
            if err:
                blocks.append(f"### [{task_id}] {title}\n执行失败：{err}")
                continue
            df = r.get("dataframe")
            if isinstance(df, pd.DataFrame) and not df.empty:
                summary = self._dataframe_summary(df)
                sample = df.head(5).to_string(index=False)
                blocks.append(
                    f"### [{task_id}] {title}\n"
                    f"行数={len(df)}；{summary}\n样本：\n{sample}"
                )
            else:
                blocks.append(f"### [{task_id}] {title}\n（无数据）")
        return "\n\n".join(blocks) or "（无查询结果）"

    @staticmethod
    def _dataframe_summary(df: pd.DataFrame) -> str:
        parts: List[str] = []
        for col in df.columns[:6]:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                parts.append(
                    f"{col}: min={series.min()}, max={series.max()}, mean={series.mean():.4g}"
                )
            else:
                parts.append(f"{col}: {series.nunique()} 个取值")
        return "；".join(parts)

    def _fallback_report(
        self,
        question: str,
        plan: AnalysisPlan,
        facts: AttributionFacts,
        task_results: List[Dict[str, Any]],
    ) -> str:
        title = "## 数据分析报告" if plan.report_mode else "## 归因分析结论"
        lines = [title, "", facts.summary, "", "### 数据依据", ""]
        lines.append(self._format_task_data(task_results))
        lines.extend(["", "### 说明"] + ["- " + n for n in facts.raw_notes[:6]])
        return "\n".join(lines)
