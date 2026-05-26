"""会话业务层：CRUD 与 LLM 上下文拼装。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from chatbi.infrastructure.db.conversation_repository import ConversationRepository

from chatbi.core.conversation_context import (
    MAX_MESSAGE_CHARS,
    MAX_CONTEXT_MESSAGES,
    truncate_text,
)

# 不参与 LLM 上下文的消息类型
_SKIP_LLM_KINDS = frozenset({"loading", "workflow", "executing"})

# 查数结果摘要最大行数（与 conversation_context 对齐）
_QUERY_PREVIEW_ROWS = 5


class ConversationService:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repo = repository

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        return self._repo.list_conversations(user_id)

    def create_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str,
        title: str = "新对话",
        mode: str = "chatbi",
        table_name: str = "",
    ) -> Dict[str, Any]:
        return self._repo.create_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            title=title,
            mode=mode,
            table_name=table_name,
        )

    def get_conversation(
        self, conversation_id: str, *, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return self._repo.get_conversation(conversation_id, user_id=user_id)

    def update_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str,
        title: Optional[str] = None,
        mode: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._repo.update_conversation(
            conversation_id,
            user_id=user_id,
            title=title,
            mode=mode,
            table_name=table_name,
        )

    def delete_conversation(self, conversation_id: str, *, user_id: str) -> bool:
        return self._repo.delete_conversation(conversation_id, user_id=user_id)

    def list_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        return self._repo.list_messages(conversation_id)

    def append_messages(
        self,
        conversation_id: str,
        messages: Sequence[Dict[str, Any]],
        *,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        return self._repo.append_messages(conversation_id, messages, user_id=user_id)

    def build_llm_messages(self, conversation_id: str) -> List[Dict[str, str]]:
        """将会话历史转为 OpenAI 风格 messages，供 ask/stream 使用。"""
        stored = self._repo.list_messages(conversation_id)
        llm: List[Dict[str, str]] = []
        for msg in stored:
            role = msg.get("role")
            kind = msg.get("kind") or ""
            if role not in ("user", "assistant") or kind in _SKIP_LLM_KINDS:
                continue
            content = truncate_text(self._message_to_llm_text(msg), max_len=MAX_MESSAGE_CHARS)
            if content.strip():
                llm.append({"role": role, "content": content})
        return llm[-MAX_CONTEXT_MESSAGES:]

    @staticmethod
    def title_from_question(question: str, *, max_len: int = 48) -> str:
        text = " ".join(question.strip().split())
        if not text:
            return "新对话"
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    @staticmethod
    def _message_to_llm_text(msg: Dict[str, Any]) -> str:
        kind = msg.get("kind") or ""
        content = msg.get("content") or {}
        if kind == "text" and msg.get("role") == "user":
            return str(content.get("text") or "")
        if kind == "text" and msg.get("role") == "assistant":
            return str(content.get("text") or "")
        if kind == "kb-answer":
            return str(content.get("text") or "")
        if kind == "error":
            return str(content.get("text") or content.get("error") or "")
        if kind == "analysis-report":
            report = str(content.get("reportMd") or content.get("text") or "")
            return truncate_text(report, max_len=MAX_MESSAGE_CHARS)
        if kind == "query-result":
            sql = content.get("sql") or ""
            qr = content.get("queryResult") or {}
            rows = qr.get("data") or []
            preview = rows[:_QUERY_PREVIEW_ROWS]
            parts = [f"查询结果（共 {qr.get('row_count', len(rows))} 行）"]
            if sql:
                parts.append(f"SQL: {sql}")
            if preview:
                parts.append(f"数据预览: {preview}")
            return "\n".join(parts)
        if kind == "followup":
            qs = content.get("followupQuestions") or []
            if qs:
                return "推荐追问: " + "；".join(str(q) for q in qs[:3])
        return str(content.get("text") or "")
