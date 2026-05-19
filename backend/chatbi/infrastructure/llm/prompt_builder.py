import datetime
from typing import Dict, List, Optional

from chatbi.infrastructure.llm.messages import (
    assistant_message,
    system_message,
    user_message,
)


class SqlPromptBuilder:
    """组装 Text-to-SQL 的 RAG 提示词。"""

    def build_sql_prompt(
        self,
        *,
        initial_prompt: Optional[str],
        question: str,
        question_sql_list: List[Dict],
        ddl_list: List[str],
        doc_list: List[str],
    ) -> List[Dict]:
        if initial_prompt is None:
            initial_prompt = (
                "你是一位SQL专家。请根据给定的上下文生成SQL查询来回答问题。"
                "你的回复应严格基于所提供的上下文。"
            )

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        mysql_dialect_rules = (
            "===MySQL方言约束（必须遵守）===\n"
            "1. 目标数据库为 MySQL 8.0+，可使用窗口函数（ROW_NUMBER、COUNT OVER 等）\n"
            "2. 禁止使用其他数据库专有语法，例如：\n"
            "   - PERCENTILE_CONT、WITHIN GROUP（PostgreSQL/Oracle/SQL Server）\n"
            "   - TOP n（SQL Server）、FETCH FIRST（部分方言）\n"
            "3. LIMIT / OFFSET 的偏移量必须是常量整数，不能写子查询或表达式，"
            "例如禁止 OFFSET (SELECT ...)\n"
            "4. 计算中位数（Top N 子集）：必须先 LIMIT 取出子集，再在外层对子集做 ROW_NUMBER/COUNT；"
            "禁止在同一层对全表做 COUNT(*) OVER () 同时又 LIMIT N（cnt 会是全表行数，"
            "导致 WHERE rn IN (中间位) 匹配不到任何行，AVG 结果为 NULL）。"
            "正确结构示例：\n"
            "SELECT AVG(total_score) FROM (\n"
            "  SELECT total_score, ROW_NUMBER() OVER (ORDER BY total_score) rn,\n"
            "         COUNT(*) OVER () cnt\n"
            "  FROM (SELECT total_score FROM 表 ORDER BY rank_num ASC LIMIT 20) top20\n"
            ") ranked WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2));\n"
            "禁止 PERCENTILE_CONT\n"
            "5. 排名筛选优先使用业务字段（如 rank_num）或 ORDER BY + LIMIT，"
            "不要臆造不存在的列\n"
        )
        system_content = (
            f"{initial_prompt}\n"
            "===响应指南===\n"
            f"0. 当前日期是{today}\n"
            "1. 若提供的上下文充足，请生成有效且可执行的SQL查询语句，无需附加解释\n"
            "2. 若上下文不充分，请解释无法生成查询的原因\n"
            "3. 请使用最相关的数据表\n"
            "4. 确保输出的SQL语句符合MySQL方言规范、可执行且无语法错误\n"
            "5. 请使用中文进行思考和描述\n"
            f"\n{mysql_dialect_rules}"
            "\n===DDL信息===\n" + "\n".join(ddl_list) if ddl_list else ""
        )
        system_content += (
            "\n===文档信息===\n" + "\n".join(doc_list) if doc_list else ""
        )

        message_log = [system_message(system_content)]

        for example in question_sql_list:
            if example and "question" in example and "sql" in example:
                message_log.append(user_message(example["question"]))
                message_log.append(assistant_message(example["sql"]))

        message_log.append(user_message(question))
        return message_log
