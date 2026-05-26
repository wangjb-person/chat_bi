"""将数据库 / SQL 异常格式化为「原始报错 + 中文说明」。"""

from __future__ import annotations

import re
from typing import Any, Dict


def format_sql_run_error_parts(
    exc: BaseException, *, sql: str = ""
) -> Dict[str, str]:
    raw = _extract_raw_message(exc)
    hint_zh = _build_chinese_hint(raw, sql=sql)
    display = (
        f"【原始错误 / Original】\n{raw}\n\n"
        f"【中文说明】\n{hint_zh}"
    )
    if sql.strip():
        display += f"\n\n【相关 SQL】\n{sql.strip()[:2000]}"
    return {"raw": raw, "hint_zh": hint_zh, "display": display}


def format_sql_run_error(exc: BaseException, *, sql: str = "") -> str:
    return format_sql_run_error_parts(exc, sql=sql)["display"]


def _extract_raw_message(exc: BaseException) -> str:
    parts: list[str] = [str(exc).strip()]
    if exc.__cause__ and str(exc.__cause__).strip():
        parts.append(str(exc.__cause__).strip())
    args = getattr(exc, "args", None)
    if args:
        for a in args:
            if isinstance(a, (int, float)):
                continue
            s = str(a).strip()
            if s and s not in parts:
                parts.append(s)
    return "\n".join(p for p in parts if p) or repr(exc)


def _build_chinese_hint(raw: str, *, sql: str = "") -> str:
    lower = raw.lower()
    if "unknown column" in lower or "1054" in raw:
        col = _match_unknown_column(raw)
        col_part = f"字段 `{col}`" if col else "某个字段"
        return (
            f"数据库报错：不存在列 {col_part}。\n"
            "常见原因：模型根据不完整信息猜错了英文字段名。\n"
            "建议：在「语料管理」补充准确 DDL，或改用表中已有字段（如 student_name、total_score、school_name）。"
        )
    if "doesn't exist" in lower or "1146" in raw:
        return (
            "数据库报错：引用的数据表不存在。\n"
            "建议：检查表名是否在 DDL 语料中，或修正 SQL 中的 FROM 表名。"
        )
    if "syntax" in lower or "1064" in raw:
        return (
            "数据库报错：SQL 语法错误。\n"
            "建议：检查方言是否为 MySQL 8.0，或让模型重新生成 SQL。"
        )
    if "connection" in lower or "connect" in lower or "2003" in raw:
        return (
            "无法连接 MySQL。\n"
            "建议：确认数据库已启动，并检查 .env 中 MYSQL_* 配置。"
        )
    if "timed out" in lower or "timeout" in lower:
        return "查询超时。建议：缩小时间范围、增加 LIMIT，或检查库负载。"
    if "access denied" in lower or "1045" in raw:
        return "数据库认证失败。请检查 MYSQL_USER / MYSQL_PASSWORD。"
    return (
        "SQL 执行失败。请结合上方原始错误排查；"
        "若为字段/表名问题，请更新语料中的 DDL 与示例 SQL。"
    )


def _match_unknown_column(raw: str) -> str:
    m = re.search(r"Unknown column\s+'([^']+)'", raw, re.I)
    if m:
        return m.group(1)
    m = re.search(r"unknown column\s+`([^`]+)`", raw, re.I)
    if m:
        return m.group(1)
    return ""
