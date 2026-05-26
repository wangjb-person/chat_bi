import re
from typing import List

import pandas as pd

from chatbi.infrastructure.llm.chinese_question_rules import (
    CHINESE_BUSINESS_QUESTION_RULES,
)
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message
from chatbi.infrastructure.viz.plotly_renderer import PlotlyRenderer
from chatbi.services.session_store import InMemorySessionStore


class EnhancementService:
    """查询结果增强：图表与追问。"""

    def __init__(
        self,
        llm: LlmClient,
        plotly: PlotlyRenderer,
        sessions: InMemorySessionStore,
    ) -> None:
        self._llm = llm
        self._plotly = plotly
        self._sessions = sessions

    def generate_plot(self, session_id: str) -> str:
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

    def generate_followup(self, session_id: str, n_questions: int = 5) -> List[str]:
        bucket = self._sessions.get(session_id)
        if not bucket:
            raise ValueError("会话不存在")

        question = bucket["question"]
        sql = bucket["sql"]
        df: pd.DataFrame = bucket["df"]

        if not df.empty:
            col_hint = "、".join(str(c) for c in df.columns.tolist())
            data_sample = (
                f"结果列: {col_hint}\n{df.head(5).to_string()}"
            )
        else:
            data_sample = "无数据"

        messages = [
            system_message(
                "你是业务数据分析助手。生成后续追问：\n"
                "1. 每条可用一条 SQL 回答\n"
                "2. 独立完整中文句\n"
                "3. 不要编号\n\n"
                f"{CHINESE_BUSINESS_QUESTION_RULES}\n\n"
                f"原问题：{question}\nSQL：{sql}\n示例：\n{data_sample}"
            ),
            user_message(f"请生成{n_questions}个后续问题，每行一个。"),
        ]
        llm_response = self._llm.complete(messages)
        numbers_removed = re.sub(
            r"^\d+\.\s*", "", llm_response, flags=re.MULTILINE
        )
        questions = [
            q.strip() for q in numbers_removed.split("\n") if q.strip()
        ]
        self._sessions.set_fields(session_id, followup=questions)
        return questions
