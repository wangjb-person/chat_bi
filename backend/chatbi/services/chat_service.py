import re
from typing import Dict, Generator, List, Optional, Tuple

import pandas as pd

from chatbi.config.settings import Settings
from chatbi.infrastructure.db.mysql_executor import MysqlExecutor
from chatbi.infrastructure.llm.chinese_question_rules import (
    CHINESE_BUSINESS_QUESTION_RULES,
)
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import assistant_message, system_message, user_message
from chatbi.infrastructure.llm.prompt_builder import SqlPromptBuilder
from chatbi.infrastructure.llm.sql_extractor import SqlExtractor
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore
from chatbi.infrastructure.viz.plotly_renderer import PlotlyRenderer
from chatbi.services.session_store import InMemorySessionStore

# 首次执行失败后，最多再让 LLM 修正并尝试的次数
SQL_CORRECTION_MAX_ATTEMPTS = 2

_CORRECTION_USER_TEMPLATE = (
    "上述 SQL 在 MySQL 中执行失败，错误信息如下：\n{error}\n\n"
    "请根据错误修正 SQL。要求：\n"
    "1. 仅输出修正后的完整可执行 SQL（可用 ```sql 代码块包裹）\n"
    "2. 必须符合 MySQL 8.0+ 方言，不要使用 PERCENTILE_CONT、WITHIN GROUP 等\n"
    "3. LIMIT/OFFSET 偏移量只能是常量整数\n"
    "4. SELECT 输出列须使用中文 AS 别名（反引号），与 DDL 字段含义一致\n"
    "5. 不要重复解释原因"
)

_MYSQL_PREFLIGHT_CHECKS: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"PERCENTILE_CONT", re.IGNORECASE),
        "PERCENTILE_CONT 为 PostgreSQL/Oracle 语法，MySQL 不支持",
    ),
    (
        re.compile(r"WITHIN\s+GROUP", re.IGNORECASE),
        "WITHIN GROUP 不是 MySQL 语法",
    ),
    (
        re.compile(r"OFFSET\s*\(", re.IGNORECASE),
        "MySQL 的 OFFSET 不能使用子查询或表达式，请改用 ROW_NUMBER 等方式",
    ),
]


class ChatService:
    """
    智能问数编排服务：组合向量检索、LLM、SQL 执行与可视化。
    路由层只调用本服务，不直接访问基础设施细节。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        vector_store: ChromaVectorStore,
        llm: LlmClient,
        prompt_builder: SqlPromptBuilder,
        sql_extractor: SqlExtractor,
        sql_executor: MysqlExecutor,
        plotly_renderer: PlotlyRenderer,
        session_store: InMemorySessionStore,
    ) -> None:
        self._settings = settings
        self._vector = vector_store
        self._llm = llm
        self._prompt_builder = prompt_builder
        self._sql_extractor = sql_extractor
        self._sql_executor = sql_executor
        self._plotly = plotly_renderer
        self._sessions = session_store

    @property
    def sessions(self) -> InMemorySessionStore:
        return self._sessions

    def _build_rag_prompt(
        self, messages: List[Dict], table_name: str
    ) -> List[Dict]:
        question = messages[-1]["content"]
        question_sql_list = self._vector.get_similar_question_sql(
            question, table_name
        )
        ddl_list = self._vector.get_related_ddl(question, table_name)
        doc_list = self._vector.get_related_documentation(question, table_name)
        gen_list = self._vector.get_related_general(question)

        prompt = self._prompt_builder.build_sql_prompt(
            initial_prompt=self._settings.initial_prompt,
            question=question,
            question_sql_list=question_sql_list,
            ddl_list=ddl_list,
            doc_list=doc_list + gen_list,
        )
        prompt[-1:-1] = messages[:-1]
        return prompt

    def generate_sql(self, messages: List[Dict], table_name: str = "") -> Dict:
        prompt = self._build_rag_prompt(messages, table_name)
        llm_response = self._llm.complete(prompt)
        sql = self._sql_extractor.extract(llm_response).replace("\\_", "_")
        return {"sql": sql, "full_response": llm_response}

    def generate_sql_stream(
        self, messages: List[Dict], table_name: str = ""
    ) -> Generator[str, None, None]:
        prompt = self._build_rag_prompt(messages, table_name)
        yield from self._llm.complete_stream(prompt)

    def extract_sql(self, llm_response: str) -> str:
        return self._sql_extractor.extract(llm_response)

    def _mysql_sql_preflight(self, sql: str) -> Optional[str]:
        for pattern, message in _MYSQL_PREFLIGHT_CHECKS:
            if pattern.search(sql):
                return message
        return None

    def run_sql(self, sql: str) -> pd.DataFrame:
        preflight_error = self._mysql_sql_preflight(sql)
        if preflight_error:
            raise Exception(f"SQL 预检失败: {preflight_error}\nSQL: {sql}")
        return self._sql_executor.execute(sql)

    def run_sql_with_correction(
        self,
        *,
        messages: List[Dict],
        table_name: str,
        sql: str,
        llm_response: str,
    ) -> Tuple[pd.DataFrame, str, str, int]:
        """
        执行 SQL；失败时将 MySQL 报错反馈给 LLM 修正后重试。
        返回 (DataFrame, 最终SQL, 最终LLM回复, 修正次数)。
        """
        current_sql = sql
        current_response = llm_response
        correction_count = 0
        last_error: Optional[Exception] = None

        for attempt in range(SQL_CORRECTION_MAX_ATTEMPTS + 1):
            try:
                df = self.run_sql(current_sql)
                return df, current_sql, current_response, correction_count
            except Exception as e:
                last_error = e
                if attempt >= SQL_CORRECTION_MAX_ATTEMPTS:
                    break

                correction_prompt = self._build_rag_prompt(messages, table_name)
                correction_prompt.append(assistant_message(current_sql))
                correction_prompt.append(
                    user_message(_CORRECTION_USER_TEMPLATE.format(error=str(e)))
                )
                current_response = self._llm.complete(correction_prompt)
                current_sql = self._sql_extractor.extract(current_response).replace(
                    "\\_", "_"
                )
                correction_count += 1

        assert last_error is not None
        raise last_error

    def save_sql_result(
        self, session_id: str, *, question: str, sql: str
    ) -> None:
        self._sessions.set_fields(session_id, question=question, sql=sql)

    def save_query_result(self, session_id: str, df: pd.DataFrame) -> None:
        self._sessions.set_fields(session_id, df=df)

    def generate_plot(
        self, session_id: str
    ) -> str:
        bucket = self._sessions.get(session_id)
        if not bucket:
            raise ValueError("会话不存在")
        df = bucket["df"]
        question = bucket["question"]
        sql = bucket["sql"]
        metadata = (
            f"DataFrame columns: {list(df.columns)}\n"
            f"Data types: {df.dtypes.to_dict()}\n"
            f"First few rows:\n{df.head().to_string()}"
        )
        code = self._plotly.generate_code(
            question=question, sql=sql, df_metadata=metadata
        )
        fig = self._plotly.render_figure(code, df)
        fig_json = fig.to_json()
        self._sessions.set_fields(session_id, fig=fig_json)
        return fig_json

    def generate_followup(
        self, session_id: str, n_questions: int = 5
    ) -> List[str]:
        bucket = self._sessions.get(session_id)
        if not bucket:
            raise ValueError("会话不存在")

        question = bucket["question"]
        sql = bucket["sql"]
        df = bucket["df"]

        if not df.empty:
            col_hint = "、".join(str(c) for c in df.columns.tolist())
            data_sample = (
                f"结果列（展示用中文表头）: {col_hint}\n"
                f"{df.head(5).to_string()}"
            )
        else:
            data_sample = "无数据"

        messages = [
            system_message(
                "你是一个业务数据分析助手。请严格按以下规则生成后续追问：\n"
                "1. 只生成能用一条 SQL 回答的问题\n"
                "2. 每个问题必须是独立、完整的中文句子\n"
                "3. 禁止包含任何解释、推理或上下文说明\n"
                "4. 直接列出问题，不要编号\n\n"
                f"{CHINESE_BUSINESS_QUESTION_RULES}\n\n"
                f"参考信息：\n"
                f"原问题：{question}\n"
                f"已执行查询（供理解，勿在追问中复述英文字段）:\n{sql}\n"
                f"查询结果示例：\n{data_sample}"
            ),
            user_message(f"请直接生成{n_questions}个后续问题，每个问题单独一行。"),
        ]
        llm_response = self._llm.complete(messages)
        if not isinstance(llm_response, str):
            llm_response = str(llm_response)

        numbers_removed = re.sub(
            r"^\d+\.\s*", "", llm_response, flags=re.MULTILINE
        )
        questions = [
            q.strip() for q in numbers_removed.split("\n") if q.strip()
        ]
        self._sessions.set_fields(session_id, followup=questions)
        return questions
