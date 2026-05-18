import re
from typing import Dict, Generator, List

import pandas as pd

from chatbi.config.settings import Settings
from chatbi.infrastructure.db.mysql_executor import MysqlExecutor
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message
from chatbi.infrastructure.llm.prompt_builder import SqlPromptBuilder
from chatbi.infrastructure.llm.sql_extractor import SqlExtractor
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore
from chatbi.infrastructure.viz.plotly_renderer import PlotlyRenderer
from chatbi.services.session_store import InMemorySessionStore


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

    def run_sql(self, sql: str) -> pd.DataFrame:
        return self._sql_executor.execute(sql)

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

        messages = [
            system_message(
                "你是一个SQL问题生成器。请严格按以下规则生成后续问题："
                "1. 只生成能用一条SQL回答的问题\n"
                "2. 每个问题必须是独立、完整的中文句子\n"
                "3. 禁止包含任何解释、推理或上下文说明\n"
                "4. 直接列出问题，不要编号\n\n"
                f"参考信息：原问题='{question}'，SQL='{sql}'，数据示例：\n"
                f"{df.head(5).to_string() if not df.empty else '无数据'}"
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
