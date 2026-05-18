import logging
from typing import Any, Dict

import pandas as pd
import pymysql

from chatbi.config.settings import MysqlSettings

log = logging.getLogger("chatbi")


class MysqlExecutor:
    """MySQL 查询执行器：每次请求独立连接，适配 Flask 多线程。"""

    def __init__(self, mysql: MysqlSettings) -> None:
        self._mysql = mysql

    def execute(self, sql: str) -> pd.DataFrame:
        cfg = self._mysql
        if not all([cfg.host, cfg.port, cfg.user, cfg.password, cfg.database]):
            raise ValueError(
                "MySQL 连接信息不完整，请在 .env 中配置 MYSQL_HOST / MYSQL_PORT / "
                "MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE"
            )

        log.info("[run_sql] 连接 MySQL %s:%s ...", cfg.host, cfg.port)
        conn = None
        try:
            conn = pymysql.connect(
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
            log.info("[run_sql] 已连接，执行 SQL")
            with conn.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                log.info("[run_sql] 已取回 %d 行", len(results))
                return pd.DataFrame(results)
        except Exception as e:
            log.exception("[run_sql] SQL 执行失败: %s", e)
            raise Exception(f"SQL 执行失败: {str(e)}\nSQL: {sql}") from e
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
