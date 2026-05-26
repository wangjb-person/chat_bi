"""
多 Agent 分析工作流：Planner → QueryAgent（并行子任务）→ Attribution → Reporter。

由 AnalysisPipeline 封装，经 AskOrchestrator 在 intent=analysis 时调用。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Generator, List, Optional

from chatbi.core.conversation_context import build_analysis_context, trim_messages
from chatbi.agents.attribution_agent import AttributionAgent
from chatbi.agents.planner_agent import PlannerAgent
from chatbi.agents.query_agent import QueryAgent
from chatbi.agents.reporter_agent import ReporterAgent
from chatbi.domain.models import AnalysisPlan, AttributionFacts


class AgentWorkflow:
    """多 Agent 协同：规划 → 并行查数 → 归因 → 报告。"""

    def __init__(
        self,
        planner: PlannerAgent,
        query: QueryAgent,
        attribution: AttributionAgent,
        reporter: ReporterAgent,
    ) -> None:
        """注入规划、查数、归因、报告四个 Agent。"""
        self._planner = planner
        self._query = query
        self._attribution = attribution
        self._reporter = reporter

    def stream(
        self,
        question: str,
        *,
        table_name: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
        routing_question: str = "",
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """流式执行分析；generator 的 return 值为最终结果 dict。"""
        msgs = trim_messages(messages)
        context = build_analysis_context(msgs, question)
        plan_q = (routing_question or question).strip()

        yield {"phase": "planning"}
        plan = self._planner.plan(plan_q, context=context)
        yield {"phase": "plan", "plan": self._plan_to_dict(plan)}

        yield {"phase": "querying"}
        results = self._query.run_parallel(
            plan.sub_tasks,
            table_name=table_name,
            base_match=plan.metric_match,
        )
        yield {
            "phase": "query_done",
            "sub_results": self._public_results(results),
        }

        if self._should_fallback_to_knowledge(results):
            return {
                "fallback_knowledge": True,
                "fallback_reason": "分析子任务均未得到有效业务数据",
                "sub_results": self._public_results(results),
                "plan": self._plan_to_dict(plan),
            }

        yield {"phase": "attributing"}
        facts = self._attribution.run(
            plan=plan,
            task_results=results,
            question=question,
        )
        yield {"phase": "attribution_done", "facts": self._facts_to_dict(facts)}

        yield {"phase": "reporting"}
        report_md = self._reporter.build_report(
            question=question,
            plan=plan,
            facts=facts,
            task_results=results,
            conversation_context=context,
        )

        return {
            "plan": self._plan_to_dict(plan),
            "sub_results": self._public_results(results),
            "facts": self._facts_to_dict(facts),
            "report_md": report_md,
        }

    def run(
        self,
        question: str,
        *,
        table_name: str = "",
        on_phase: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """同步跑完工作流，可选 on_phase 回调。"""
        gen = self.stream(question, table_name=table_name)
        result: Dict[str, Any] = {}
        try:
            while True:
                event = next(gen)
                if on_phase:
                    on_phase(event.get("phase", ""), event)
        except StopIteration as stop:
            result = stop.value or {}
        return result

    def _plan_to_dict(self, plan: AnalysisPlan) -> Dict[str, Any]:
        """将 AnalysisPlan 转为可 JSON 序列化的 dict（供 SSE）。"""
        return {
            "metric_code": plan.metric_code,
            "metric_name": plan.metric_name,
            "report_mode": plan.report_mode,
            "subject": plan.subject,
            "sub_tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "question": t.question,
                    "execution": t.execution,
                }
                for t in plan.sub_tasks
            ],
        }

    @staticmethod
    def _should_fallback_to_knowledge(results: List[Dict[str, Any]]) -> bool:
        """所有子任务均无有效 DataFrame 时，改走知识问答而非空报告。"""
        if not results:
            return True
        for r in results:
            df = r.get("dataframe")
            err = r.get("error")
            if err:
                continue
            if df is not None and hasattr(df, "empty") and not df.empty:
                return False
        return True

    def _public_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """子任务结果脱敏（去掉 dataframe，仅保留 sql/错误/行数）。"""
        out = []
        for r in results:
            out.append(
                {
                    "task_id": r.get("task_id"),
                    "description": r.get("description"),
                    "sql": r.get("sql"),
                    "error": r.get("error"),
                    "row_count": r.get("row_count"),
                }
            )
        return out

    def _facts_to_dict(self, facts: AttributionFacts) -> Dict[str, Any]:
        """归因事实转 dict，供前端与 Reporter 使用。"""
        return {
            "summary": facts.summary,
            "top_dimensions": facts.top_dimensions,
            "comparisons": facts.comparisons,
            "raw_notes": facts.raw_notes,
        }
