"""
问数编排器：统一 SSE 入口，按意图分发到对话 / 查数 / 分析三条通道。

对应 API：POST /api/ask/stream
"""

from __future__ import annotations

import json
from typing import Any, Dict, Generator, List, Optional

from chatbi.core.conversation_context import prior_history, trim_messages
from chatbi.application.analysis_pipeline import AnalysisPipeline
from chatbi.application.intent_router import IntentRouter
from chatbi.application.query_understanding import (
    QueryUnderstandingService,
    ResolvedQuestion,
)
from chatbi.core.ids import generate_turn_id
from chatbi.core.sql_error_message import format_sql_run_error_parts
from chatbi.core.json_util import dataframe_to_records
from chatbi.core.sql_guard import looks_like_executable_sql
from chatbi.domain.models import Intent, IntentResult, MetricMatch
from chatbi.services.chat_pipeline import ChatPipeline
from chatbi.services.enhancement_service import EnhancementService
from chatbi.services.kb_pipeline import KbPipeline
from chatbi.services.query_pipeline import QueryPipeline
from chatbi.services.session_store import InMemorySessionStore

_REPORT_CHUNK_SIZE = 800
_CHAT_INTENTS = frozenset({Intent.CLARIFY, Intent.CHAT, Intent.KNOWLEDGE})


def _analysis_sse_payload(session_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将分析工作流内部 phase 映射为 SSE payload；未知 phase 返回 None。"""
    phase = event.get("phase", "")
    sid = session_id
    match phase:
        case "planning":
            return {"phase": "planning", "id": sid}
        case "plan":
            return {"phase": "planning", "plan": event.get("plan"), "id": sid}
        case "querying":
            return {"phase": "querying", "id": sid}
        case "query_done":
            return {
                "phase": "querying",
                "sub_results": event.get("sub_results"),
                "id": sid,
            }
        case "attributing":
            return {"phase": "attributing", "id": sid}
        case "attribution_done":
            return {"phase": "attributing", "facts": event.get("facts"), "id": sid}
        case "reporting":
            return {"phase": "reporting", "id": sid}
        case _:
            return None


class AskOrchestrator:
    """统一问数入口：意图路由 → 对话 / 查数 / 分析。"""

    def __init__(
        self,
        intent_router: IntentRouter,
        query_pipeline: QueryPipeline,
        analysis_pipeline: AnalysisPipeline,
        chat_pipeline: ChatPipeline,
        *,
        kb_pipeline: Optional[KbPipeline] = None,
        session_store: InMemorySessionStore,
        enhancement: Optional[EnhancementService] = None,
        query_understanding: Optional[QueryUnderstandingService] = None,
    ) -> None:
        """组装意图路由、查数管道、分析工作流、对话管道与会话存储。"""
        self._router = intent_router
        self._understanding = query_understanding
        self._query = query_pipeline
        self._analysis = analysis_pipeline
        self._chat = chat_pipeline
        self._kb = kb_pipeline
        self._sessions = session_store
        self._enhancement = enhancement

    @property
    def sessions(self) -> InMemorySessionStore:
        """当前进程内会话存储，供 run_sql / 图表等后续接口使用。"""
        return self._sessions

    def _metric_match_from_intent(
        self, intent_result: IntentResult
    ) -> Optional[MetricMatch]:
        """从意图实体中恢复已解析的 MetricMatch（指标匹配），避免重复解析。"""
        return self._query.match_from_entity(
            intent_result.entities.get("metric_match")
        )

    def stream_ask(
        self,
        *,
        question: str,
        table_name: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
        mode: str = "chatbi",
    ) -> Generator[str, None, None]:
        """流式问数主流程：yield SSE 事件（intent / sql / done 等）。"""
        session_id = generate_turn_id()
        msgs = trim_messages(messages)
        resolved = self._resolve_question(question, msgs)

        if (mode or "chatbi").strip().lower() == "kb":
            yield from self._stream_kb(
                question=question,
                session_id=session_id,
                history=msgs,
                retrieval_question=resolved.text,
            )
            return

        intent_result = self._router.route(
            question,
            table_name=table_name,
            messages=msgs,
            score_question=resolved.text,
        )

        intent_payload: Dict[str, Any] = {
            "phase": "intent",
            "intent": intent_result.intent.value,
            "reason": intent_result.reason,
            "report_mode": bool(intent_result.entities.get("report_mode")),
            "id": session_id,
            **(
                {"resolved_question": resolved.text}
                if resolved.rewritten
                else {}
            ),
        }
        yield self._sse(intent_payload)

        intent = intent_result.intent
        if intent in _CHAT_INTENTS:
            yield from self._stream_chat(
                question=question,
                session_id=session_id,
                intent=intent,
                missing_slots=intent_result.missing_slots
                if intent == Intent.CLARIFY
                else None,
                history=msgs,
            )
            return

        yield from (
            self._stream_analysis(
                question=question,
                table_name=table_name,
                session_id=session_id,
                messages=msgs,
                routing_question=resolved.text,
            )
            if intent == Intent.ANALYSIS
            else self._stream_query(
                question=question,
                table_name=table_name,
                session_id=session_id,
                messages=msgs,
                intent_result=intent_result,
                routing_question=resolved.text,
            )
        )

    def _resolve_question(self, question: str, msgs: List[Dict[str, str]]) -> ResolvedQuestion:
        if self._understanding is not None:
            return self._understanding.resolve(question, msgs)
        q = question.strip()
        return ResolvedQuestion(original=q, text=q, rewritten=False)

    def _stream_kb(
        self,
        *,
        question: str,
        session_id: str,
        history: Optional[List[Dict[str, str]]] = None,
        retrieval_question: str = "",
    ) -> Generator[str, None, None]:
        """知识库模式：不经过意图路由，不访问 MySQL。"""
        if self._kb is None:
            yield from self._kb_disabled_sse(session_id)
            return

        yield self._sse(
            {
                "phase": "intent",
                "intent": "doc_qa",
                "reason": "用户选择知识库问答模式",
                "id": session_id,
            }
        )

        chunks = self._kb.retrieve(retrieval_question or question)
        yield self._sse({"phase": "retrieving", "kb_sources": chunks})

        prior = prior_history(history, question)
        answer_parts: List[str] = []
        for piece in self._kb.stream_llm(question, chunks, history=prior):
            answer_parts.append(piece)
            yield self._sse({"phase": "answer_chunk", "chunk": piece})

        full = "".join(answer_parts)
        self._sessions.set_fields(session_id, question=question, answer_text=full)
        yield self._sse(
            self._kb_done_payload(session_id, answer_text=full, kb_sources=chunks)
        )

    def _kb_disabled_sse(self, session_id: str) -> Generator[str, None, None]:
        """知识库管道未装配时的兜底回复。"""
        yield self._sse(
            self._kb_done_payload(
                session_id,
                answer_text="知识库服务未启用",
                kb_sources=[],
            )
        )

    def _kb_done_payload(
        self,
        session_id: str,
        *,
        answer_text: str,
        kb_sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """知识库通道 done 事件结构。"""
        return {
            "phase": "done",
            "done": True,
            "id": session_id,
            "intent": "doc_qa",
            "answer_text": answer_text,
            "kb_sources": kb_sources,
        }

    def _stream_chat(
        self,
        *,
        question: str,
        session_id: str,
        intent: Intent,
        missing_slots: Optional[List[str]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[str, None, None]:
        """对话/知识/澄清通道：仅 LLM 流式输出，不访问 MySQL。"""
        prior = prior_history(history, question)
        full = ""
        for chunk in self._chat.stream(
            question, intent=intent, missing_slots=missing_slots, history=prior
        ):
            full += chunk
            yield self._sse({"phase": "answer_chunk", "chunk": chunk})

        self._sessions.set_fields(session_id, question=question, answer_text=full)
        yield self._sse(
            {
                "phase": "done",
                "done": True,
                "id": session_id,
                "intent": intent.value,
                "answer_text": full,
            }
        )

    def _stream_query(
        self,
        *,
        question: str,
        table_name: str,
        session_id: str,
        messages: Optional[List[Dict[str, str]]],
        intent_result: IntentResult,
        routing_question: str = "",
    ) -> Generator[str, None, None]:
        """查数通道：指标 SQL 或 RAG 生成 SQL → 执行 → 返回 query_result 或 run_error。"""
        msgs = messages or [{"role": "user", "content": question}]
        metric_match = self._metric_match_from_intent(intent_result)
        metric_sql = self._query.try_metric_sql(routing_question, match=metric_match)

        full_response = ""
        rag = None
        if metric_sql:
            yield self._sse(
                {"phase": "sql", "sql": metric_sql, "sql_source": "metric"}
            )
            extracted, sql_source = metric_sql, "metric"
        else:
            rag = self._query._fetch_rag_bundle(routing_question, table_name)
            for chunk in self._query.generate_sql_stream(
                msgs, table_name, metric_match=metric_match
            ):
                full_response += chunk
                yield self._sse({"phase": "sql_chunk", "sql": chunk})
            extracted = self._query.extract_sql(full_response).replace("\\_", "_")
            extracted = extracted.strip() or full_response.strip()
            sql_source = "llm"

        self._sessions.set_fields(session_id, question=question, sql=extracted)

        if not looks_like_executable_sql(extracted):
            answer = (extracted or full_response).strip()
            self._sessions.set_fields(session_id, question=question, answer_text=answer)
            yield self._sse(
                {
                    "phase": "done",
                    "done": True,
                    "id": session_id,
                    "intent": Intent.KNOWLEDGE.value,
                    "answer_text": answer,
                }
            )
            return

        done: Dict[str, Any] = {
            "phase": "done",
            "done": True,
            "id": session_id,
            "intent": Intent.QUERY.value,
            "sql": extracted,
            "sql_source": sql_source,
        }

        try:
            df, final_sql, correction_count = self._query.run_sql_with_correction(
                messages=msgs,
                table_name=table_name,
                sql=extracted,
                llm_response=full_response,
                sql_source=sql_source,
                rag=rag,
            )
            if correction_count > 0:
                extracted = final_sql
                done["sql"] = final_sql
                done["sql_corrected"] = True
            self._sessions.set_fields(
                session_id, question=question, sql=extracted, df=df
            )
            done["query_result"] = {
                "data": dataframe_to_records(df),
                "columns": [str(c) for c in df.columns.tolist()],
                "row_count": len(df),
            }
        except Exception as e:
            parts = format_sql_run_error_parts(e, sql=extracted)
            done["run_error"] = parts["display"]
            done["run_error_raw"] = parts["raw"]
            done["run_error_hint"] = parts["hint_zh"]

        yield self._sse(done)

    def _stream_analysis(
        self,
        *,
        question: str,
        table_name: str,
        session_id: str,
        messages: Optional[List[Dict[str, str]]] = None,
        routing_question: str = "",
    ) -> Generator[str, None, None]:
        """分析通道：多 Agent 规划查数写报告；无数据时降级为知识问答。"""
        gen = self._analysis.stream(
            question,
            table_name=table_name,
            messages=messages,
            routing_question=routing_question or question,
        )
        result: Dict[str, Any] = {}
        try:
            while True:
                event = next(gen)
                payload = _analysis_sse_payload(session_id, event)
                if payload is not None:
                    yield self._sse(payload)
        except StopIteration as stop:
            result = stop.value or {}

        if result.get("fallback_knowledge"):
            yield from self._stream_chat(
                question=question,
                session_id=session_id,
                intent=Intent.KNOWLEDGE,
                history=messages,
            )
            return

        report_md = result.get("report_md", "")
        for i in range(0, len(report_md), _REPORT_CHUNK_SIZE):
            yield self._sse(
                {"phase": "report_chunk", "chunk": report_md[i : i + _REPORT_CHUNK_SIZE]}
            )

        self._sessions.set_fields(
            session_id,
            question=question,
            report_md=report_md,
            facts=result.get("facts"),
        )

        yield self._sse(
            {
                "phase": "done",
                "done": True,
                "id": session_id,
                "intent": Intent.ANALYSIS.value,
                "report_md": report_md,
                "facts": result.get("facts"),
                "sub_results": result.get("sub_results"),
                "plan": result.get("plan"),
            }
        )

    @staticmethod
    def _sse(payload: Dict[str, Any]) -> str:
        """封装为 SSE data 行。"""
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
