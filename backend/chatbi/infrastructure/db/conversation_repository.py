"""MySQL 会话与消息持久化。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from chatbi.infrastructure.db.mysql_client import MysqlClient

log = logging.getLogger("chatbi")


def _strip_sql_comments(block: str) -> str:
    lines = [ln for ln in block.splitlines() if not ln.strip().startswith("--")]
    return "\n".join(lines).strip()


_CONVERSATIONS_TABLE = "chat_bi_conversations_table"
_MESSAGES_TABLE = "chat_bi_messages_table"
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "sql" / "chat_bi_conversations_schema.sql"
)


class ConversationRepository:
    def __init__(self, mysql_client: MysqlClient) -> None:
        self._db = mysql_client
        self._tables_ready = False

    def ensure_tables(self) -> None:
        if self._tables_ready:
            return
        if not _SCHEMA_PATH.is_file():
            raise FileNotFoundError(f"缺少 DDL 文件: {_SCHEMA_PATH}")
        script = _SCHEMA_PATH.read_text(encoding="utf-8")
        statements = [s.strip() for s in script.split(";") if s.strip()]
        for stmt in statements:
            sql = _strip_sql_comments(stmt)
            if not sql:
                continue
            # 应用启动仅建表，不执行 DROP，避免重启清空历史会话
            if sql.lstrip().upper().startswith("DROP"):
                continue
            self._db.execute(sql)
        self._tables_ready = True
        log.info("[conversation] 已确保表 %s / %s 存在", _CONVERSATIONS_TABLE, _MESSAGES_TABLE)

    def list_conversations(self, user_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        self.ensure_tables()
        rows = self._db.fetch_all(
            f"""
            SELECT id, user_id, title, mode, table_name, created_at, updated_at
            FROM {_CONVERSATIONS_TABLE}
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        return [self._serialize_conversation(r) for r in rows]

    def get_conversation(
        self, conversation_id: str, *, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        if user_id:
            row = self._db.fetch_one(
                f"""
                SELECT id, user_id, title, mode, table_name, created_at, updated_at
                FROM {_CONVERSATIONS_TABLE}
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
        else:
            row = self._db.fetch_one(
                f"""
                SELECT id, user_id, title, mode, table_name, created_at, updated_at
                FROM {_CONVERSATIONS_TABLE}
                WHERE id = %s
                """,
                (conversation_id,),
            )
        return self._serialize_conversation(row) if row else None

    def create_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str,
        title: str = "新对话",
        mode: str = "chatbi",
        table_name: str = "",
    ) -> Dict[str, Any]:
        self.ensure_tables()
        self._db.execute(
            f"""
            INSERT INTO {_CONVERSATIONS_TABLE}
                (id, user_id, title, mode, table_name)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (conversation_id, user_id, title, mode, table_name),
        )
        row = self.get_conversation(conversation_id)
        assert row is not None
        return row

    def update_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str,
        title: Optional[str] = None,
        mode: Optional[str] = None,
        table_name: Optional[str] = None,
        touch: bool = False,
    ) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        fields: List[str] = []
        params: List[Any] = []
        if title is not None:
            fields.append("title = %s")
            params.append(title)
        if mode is not None:
            fields.append("mode = %s")
            params.append(mode)
        if table_name is not None:
            fields.append("table_name = %s")
            params.append(table_name)
        if touch and not fields:
            fields.append("updated_at = %s")
            params.append(datetime.now())
        if not fields:
            return self.get_conversation(conversation_id, user_id=user_id)
        params.extend([conversation_id, user_id])
        affected = self._db.execute(
            f"""
            UPDATE {_CONVERSATIONS_TABLE}
            SET {", ".join(fields)}
            WHERE id = %s AND user_id = %s
            """,
            tuple(params),
        )
        if affected == 0:
            return None
        return self.get_conversation(conversation_id, user_id=user_id)

    def delete_conversation(self, conversation_id: str, *, user_id: str) -> bool:
        self.ensure_tables()
        affected = self._db.execute(
            f"DELETE FROM {_CONVERSATIONS_TABLE} WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )
        return affected > 0

    def list_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        self.ensure_tables()
        rows = self._db.fetch_all(
            f"""
            SELECT id, conversation_id, turn_id, seq, role, kind, content, created_at
            FROM {_MESSAGES_TABLE}
            WHERE conversation_id = %s
            ORDER BY created_at ASC, seq ASC
            """,
            (conversation_id,),
        )
        return [self._serialize_message(r) for r in rows]

    def append_messages(
        self,
        conversation_id: str,
        messages: Sequence[Dict[str, Any]],
        *,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if not messages:
            return self.list_messages(conversation_id)
        conv = self.get_conversation(conversation_id, user_id=user_id)
        if not conv:
            raise ValueError("会话不存在或无权访问")

        rows: List[tuple] = []
        for msg in messages:
            content = msg.get("content") or {}
            rows.append(
                (
                    msg["id"],
                    conversation_id,
                    msg.get("turn_id") or msg["id"],
                    int(msg.get("seq") or 0),
                    msg["role"],
                    msg["kind"],
                    json.dumps(content, ensure_ascii=False),
                )
            )
        self._db.execute_many(
            f"""
            INSERT INTO {_MESSAGES_TABLE}
                (id, conversation_id, turn_id, seq, role, kind, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
        self.update_conversation(conversation_id, user_id=user_id, touch=True)
        return self.list_messages(conversation_id)

    @staticmethod
    def _serialize_conversation(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "mode": row["mode"],
            "table_name": row.get("table_name") or "",
            "created_at": _dt_iso(row.get("created_at")),
            "updated_at": _dt_iso(row.get("updated_at")),
        }

    @staticmethod
    def _serialize_message(row: Dict[str, Any]) -> Dict[str, Any]:
        content = row.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                content = {"text": content}
        elif content is None:
            content = {}
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "turn_id": row["turn_id"],
            "seq": row["seq"],
            "role": row["role"],
            "kind": row["kind"],
            "content": content,
            "created_at": _dt_iso(row.get("created_at")),
        }


def _dt_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    return str(value)
