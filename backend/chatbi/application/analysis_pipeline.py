"""分析通道门面：薄封装 AgentWorkflow，供 AskOrchestrator 调用。"""

from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional

from chatbi.workflow.agent_workflow import AgentWorkflow


class AnalysisPipeline:
    """分析通道门面。"""

    def __init__(self, workflow: AgentWorkflow) -> None:
        """注入已组装好的 AgentWorkflow。"""
        self._workflow = workflow

    def stream(
        self,
        question: str,
        *,
        table_name: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
        routing_question: str = "",
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """流式产出 phase 事件；StopIteration.value 为最终 report_md 等。"""
        return self._workflow.stream(
            question,
            table_name=table_name,
            messages=messages,
            routing_question=routing_question,
        )

    def run(
        self,
        question: str,
        *,
        table_name: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
        routing_question: str = "",
    ) -> Dict[str, Any]:
        """消费完整 generator，仅返回最终结果 dict。"""
        gen = self.stream(
            question,
            table_name=table_name,
            messages=messages,
            routing_question=routing_question,
        )
        try:
            while True:
                next(gen)
        except StopIteration as stop:
            return stop.value or {}
        return {}
