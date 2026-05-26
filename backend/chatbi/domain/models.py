from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Intent(str, Enum):
    """定义用户意图的分类 """
    QUERY = "query"
    ANALYSIS = "analysis"
    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    CLARIFY = "clarify"


@dataclass
class IntentResult:
    """意图识别的结果"""
    intent: Intent
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class MetricDefinition:
    """定义指标的元数据"""
    code: str
    name: str
    dataset_id: str
    base_table: str
    expression: str
    format: str
    description: str
    synonyms: List[str]
    dimensions: List[str]
    status: str = "published"


@dataclass
class DimensionDefinition:
    """定义维度的元数据"""
    code: str
    name: str
    column_expr: str


@dataclass
class MetricMatch:
    """指标匹配的结果"""
    metric: MetricDefinition
    score: float
    filters: Dict[str, str] = field(default_factory=dict)
    dimensions: List[str] = field(default_factory=list)
    time_filter: Optional[str] = None


@dataclass
class AnalysisSubTask:
    """定义分析计划中的子任务"""
    id: str
    description: str
    question: str
    execution: str = "nl2sql"  # nl2sql | metric | sql
    preset_sql: Optional[str] = None
    group_by: Optional[List[str]] = None


@dataclass
class AnalysisPlan:
    """分析计划（PlannerAgent 的输出）"""
    metric_code: Optional[str]
    metric_name: str
    subject: Dict[str, str]
    sub_tasks: List[AnalysisSubTask]
    report_mode: bool = False
    metric_match: Optional[MetricMatch] = None


@dataclass
class AttributionFacts:
    """归因分析的结果（AttributionAgent 的输出）"""
    summary: str
    top_dimensions: List[Dict[str, Any]]
    comparisons: List[Dict[str, Any]]
    raw_notes: List[str] = field(default_factory=list)
