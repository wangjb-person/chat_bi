"""MySQL 通用客户端：会话表 CRUD 等非 DataFrame 查询。"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Tuple

import pymysql

from chatbi.config.settings import MysqlSettings

log = logging.getLogger("chatbi")


class MysqlClient:
    """基于 pymysql 的轻量客户端，每次操作独立连接。"""

    def __init__(self, mysql: MysqlSettings) -> None:
        self._mysql = mysql

    def _connect(self) -> pymysql.connections.Connection:
        cfg = self._mysql
        if not all([cfg.host, cfg.port, cfg.user, cfg.password, cfg.database]):
            raise ValueError(
                "MySQL 连接信息不完整，请在 .env 中配置 MYSQL_HOST / MYSQL_PORT / "
                "MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE"
            )
        return pymysql.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            read_timeout=60,
            write_timeout=60,
            autocommit=True,
        )

    @contextmanager
    def cursor(self) -> Generator[pymysql.cursors.DictCursor, None, None]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                yield cur
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def fetch_all(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return list(rows) if rows else []

    def fetch_one(self, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> int:
        with self.cursor() as cur:
            return cur.execute(sql, params or ())

    def execute_many(self, sql: str, params_list: Iterable[Sequence[Any]]) -> int:
        with self.cursor() as cur:
            return cur.executemany(sql, list(params_list))

    def execute_script(self, script: str) -> None:
        statements = [s.strip() for s in script.split(";") if s.strip()]
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
        finally:
            try:
                conn.close()
            except Exception:
                pass
