import re


class SqlExtractor:
    """从 LLM 自然语言回复中提取可执行 SQL（规则抽取，无额外模型调用）。"""

    def extract(self, llm_response: str) -> str:
        sqls = re.findall(
            r"\bCREATE\s+TABLE\b[\s\S]*?\bAS\b.*?;",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if sqls:
            return sqls[-1]

        sqls = re.findall(
            r"\bWITH\b[\s\S]*?;", llm_response, re.DOTALL | re.IGNORECASE
        )
        if sqls:
            return sqls[-1]

        sqls = re.findall(
            r"\bSELECT\b[\s\S]*?;", llm_response, re.DOTALL | re.IGNORECASE
        )
        if sqls:
            return sqls[-1]

        sqls = re.findall(
            r"```sql\s*\n(.*?)```", llm_response, re.DOTALL | re.IGNORECASE
        )
        if sqls:
            return sqls[-1].strip()

        sqls = re.findall(r"```(.*?)```", llm_response, re.DOTALL)
        if sqls:
            return sqls[-1].strip()

        return llm_response
