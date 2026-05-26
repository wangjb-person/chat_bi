from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from chatbi.config.settings import get_settings
from chatbi.infrastructure.db.mysql_client import MysqlClient

c = MysqlClient(get_settings().mysql)
for t in ["chat_bi_conversations_table", "chat_bi_messages_table"]:
    row = c.fetch_one(f"SHOW TABLE STATUS LIKE '{t}'")
    print("TABLE", t, ":", (row or {}).get("Comment", "MISSING"))
    if row:
        for col in c.fetch_all(f"SHOW FULL COLUMNS FROM {t}"):
            print(" ", col["Field"], "->", col.get("Comment", ""))
