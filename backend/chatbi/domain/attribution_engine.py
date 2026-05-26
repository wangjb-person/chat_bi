from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from chatbi.domain.models import AttributionFacts


class AttributionEngine:
    """对多份查询结果做确定性归因（环比、Top 维度、贡献度简述）。"""

    def analyze(
        self,
        *,
        metric_name: str,
        frames: Dict[str, pd.DataFrame],
        subject: Dict[str, str],
    ) -> AttributionFacts:
        notes: List[str] = []
        top_dims: List[Dict[str, Any]] = []
        comparisons: List[Dict[str, Any]] = []

        primary = frames.get("by_dimension")
        if primary is not None and not primary.empty:
            value_col = self._value_column(primary)
            dim_col = self._dimension_column(primary)
            if value_col and dim_col:
                sorted_df = primary.sort_values(value_col, ascending=True)
                worst = sorted_df.iloc[0]
                top_dims.append(
                    {
                        "dimension": str(worst[dim_col]),
                        "value": self._safe_float(worst[value_col]),
                        "role": "lowest",
                    }
                )
                notes.append(
                    f"{dim_col}={worst[dim_col]} 的 {metric_name} 最低（{worst[value_col]}）"
                )

        agg = frames.get("aggregate")
        if agg is not None and not agg.empty:
            value_col = self._value_column(agg)
            if value_col:
                val = self._safe_float(agg.iloc[0][value_col])
                comparisons.append({"label": "当前汇总", "value": val})
                notes.append(f"当前汇总 {metric_name}={val}")

        for task_id, df in frames.items():
            if task_id in ("by_dimension", "aggregate") or df.empty:
                continue
            notes.append(f"子任务 {task_id} 返回 {len(df)} 行")

        summary = (
            f"针对「{metric_name}」的归因分析："
            + ("；".join(notes[:3]) if notes else "数据不足，请检查表结构与指标配置。")
        )
        if subject:
            summary += f" 分析对象：{subject}。"

        return AttributionFacts(
            summary=summary,
            top_dimensions=top_dims,
            comparisons=comparisons,
            raw_notes=notes,
        )

    def analyze_report(
        self,
        *,
        question: str,
        frames: Dict[str, pd.DataFrame],
        subject: Dict[str, str],
    ) -> AttributionFacts:
        """报告模式：汇总多步子查询结果为对比要点。"""
        notes: List[str] = []
        comparisons: List[Dict[str, Any]] = []
        top_dims: List[Dict[str, Any]] = []

        for task_id, df in frames.items():
            if df is None or df.empty:
                notes.append(f"{task_id}: 无数据")
                continue
            school_col = self._school_column(df)
            value_cols = [
                c for c in df.columns
                if c != school_col and self._safe_float(df.iloc[0][c]) is not None
            ]
            notes.append(
                f"{task_id}: {len(df)} 行，列={list(df.columns)}"
            )
            if school_col and value_cols:
                for _, row in df.iterrows():
                    school = str(row[school_col])
                    for vc in value_cols[:4]:
                        val = self._safe_float(row[vc])
                        if val is not None:
                            comparisons.append(
                                {
                                    "school": school,
                                    "metric": vc,
                                    "value": val,
                                    "task": task_id,
                                }
                            )
                if value_cols:
                    primary = value_cols[0]
                    ranked = df.sort_values(primary, ascending=False)
                    top_dims.append(
                        {
                            "dimension": str(ranked.iloc[0][school_col])
                            if school_col
                            else "—",
                            "value": self._safe_float(ranked.iloc[0][primary]),
                            "role": f"highest_{primary}",
                        }
                    )

        schools = subject.get("schools") or []
        school_txt = (
            "、".join(schools) if isinstance(schools, list) else str(schools)
        )
        summary = (
            f"已完成 {len(frames)} 项数据查询，用于回答：{question[:80]}。"
            f"对比对象：{school_txt or '见数据表'}。"
            f" 共整理 {len(comparisons)} 条可引用指标。"
        )

        return AttributionFacts(
            summary=summary,
            top_dimensions=top_dims,
            comparisons=comparisons,
            raw_notes=notes,
        )

    def _school_column(self, df: pd.DataFrame) -> Optional[str]:
        for c in ("school_name", "学校", "学校名称"):
            if c in df.columns:
                return c
        if len(df.columns) >= 1:
            first = str(df.columns[0])
            if "学校" in first:
                return first
        return self._dimension_column(df)

    def _value_column(self, df: pd.DataFrame) -> Optional[str]:
        for c in df.columns:
            if c not in ("region", "product_name", "channel", "school_name"):
                return str(c)
        return str(df.columns[-1]) if len(df.columns) else None

    def _dimension_column(self, df: pd.DataFrame) -> Optional[str]:
        for c in ("region", "product_name", "channel", "school_name"):
            if c in df.columns:
                return c
        if len(df.columns) >= 2:
            return str(df.columns[0])
        return None

    def _safe_float(self, val: Any) -> Optional[float]:
        try:
            if pd.isna(val):
                return None
            return float(val)
        except (TypeError, ValueError):
            return None
