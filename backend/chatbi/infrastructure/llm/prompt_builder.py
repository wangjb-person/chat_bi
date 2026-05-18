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
        system_content = (
            f"{initial_prompt}\n"
            "===响应指南===\n"
            f"0. 当前日期是{today}\n"
            "1. 若提供的上下文充足，请生成有效且可执行的SQL查询语句，无需附加解释\n"
            "2. 若上下文不充分，请解释无法生成查询的原因\n"
            "3. 请使用最相关的数据表\n"
            "4. 确保输出的SQL语句符合MySQL方言规范、可执行且无语法错误\n"
            "5. 请使用中文进行思考和描述\n"
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
