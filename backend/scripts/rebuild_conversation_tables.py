"""删表重建 ChatBI 会话相关 MySQL 表（含 DROP，会清空历史会话数据）。"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from chatbi.config.settings import get_settings
from chatbi.infrastructure.db.mysql_client import MysqlClient

SCHEMA_PATH = BACKEND_ROOT / "sql" / "chat_bi_conversations_schema.sql"


def _strip_sql_comments(block: str) -> str:
    lines = [ln for ln in block.splitlines() if not ln.strip().startswith("--")]
    return "\n".join(lines).strip()


def _run_schema(client: MysqlClient, *, include_drop: bool) -> None:
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [s.strip() for s in script.split(";") if s.strip()]
    for stmt in statements:
        sql = _strip_sql_comments(stmt)
        if not sql:
            continue
        head = sql.lstrip().upper()
        if head.startswith("DROP") and not include_drop:
            continue
        client.execute(sql)
        if head.startswith("DROP"):
            print(f"OK: {sql.split(chr(10))[0][:80]}")
        elif head.startswith("SET FOREIGN_KEY"):
            print("OK: FK checks toggled")
        elif head.startswith("CREATE TABLE"):
            name = sql.split("EXISTS")[-1].split("(")[0].strip()
            print(f"OK: CREATE {name}")


def main() -> None:
    settings = get_settings()
    client = MysqlClient(settings.mysql)
    _run_schema(client, include_drop=True)
    print("会话表删表重建完成。")


if __name__ == "__main__":
    main()
