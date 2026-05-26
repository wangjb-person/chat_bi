"""判断文本是否为可执行的 SQL，避免把闲聊/说明文字拿去查库。"""

from __future__ import annotations

import re


_SQL_START = re.compile(
    r"^\s*(WITH|SELECT|SHOW|DESCRIBE|DESC|EXPLAIN)\b",
    re.IGNORECASE | re.DOTALL,
)


def looks_like_executable_sql(text: str) -> bool:
    if not text or not text.strip():
        return False

    snippet = text.strip()
    # 去掉 markdown 代码块标记后取首条语句
    if "```" in snippet:
        blocks = re.findall(r"```(?:sql)?\s*([\s\S]*?)```", snippet, re.IGNORECASE)
        if blocks:
            snippet = blocks[0].strip()
        else:
            snippet = re.sub(r"```\w*\s*", "", snippet).strip()

    # 取第一条以 SELECT/WITH 开头的语句
    for line in snippet.split(";"):
        part = line.strip()
        if _SQL_START.match(part):
            snippet = part
            break
    else:
        if not _SQL_START.search(snippet):
            return False

    upper = snippet.upper()
    if "SELECT" not in upper and "WITH" not in upper:
        return False

    # 纯中文说明（无 SQL 关键字结构）不执行
    cjk = len(re.findall(r"[\u4e00-\u9fff]", snippet))
    if cjk > len(snippet) * 0.55 and "FROM" not in upper:
        return False

    return True
