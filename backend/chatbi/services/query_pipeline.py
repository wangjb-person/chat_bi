"""
查数管道：指标 SQL 优先，否则 RAG+LLM 生成 SQL，执行 MySQL 并支持有限次纠错。

被 AskOrchestrator（单次查数）与 QueryAgent（分析子任务）共用。
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import pandas as pd

from chatbi.config.settings import Settings
from chatbi.domain.metric_match_codec import metric_match_from_entity
from chatbi.domain.metric_resolver import MetricResolver
from chatbi.domain.models import AnalysisSubTask, MetricMatch
from chatbi.domain.sql_builder import MetricSqlBuilder
from chatbi.infrastructure.db.mysql_executor import MysqlExecutor
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import assistant_message, user_message
from chatbi.infrastructure.llm.prompt_builder import SqlPromptBuilder
from chatbi.infrastructure.llm.sql_extractor import SqlExtractor
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore
from chatbi.services.session_store import InMemorySessionStore

SQL_CORRECTION_MAX_ATTEMPTS = 2

_CORRECTION_USER_TEMPLATE = (
    "上述 SQL 在 MySQL 中执行失败，错误信息如下：\n{error}\n\n"
    "请根据错误修正 SQL。要求：\n"
    "1. 仅输出修正后的完整可执行 SQL（可用 ```sql 代码块包裹）\n"
    "2. 必须符合 MySQL 8.0+ 方言\n"
    "3. LIMIT/OFFSET 偏移量只能是常量整数\n"
    "4. SELECT 输出列须使用中文 AS 别名（反引号）\n"
    "5. 不要重复解释原因"
)

_MYSQL_PREFLIGHT_CHECKS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"PERCENTILE_CONT", re.IGNORECASE), "PERCENTILE_CONT 不支持"),
    (re.compile(r"WITHIN\s+GROUP", re.IGNORECASE), "WITHIN GROUP 不支持"),
    (re.compile(r"OFFSET\s*\(", re.IGNORECASE), "OFFSET 不能为表达式"),
]


@dataclass
class _RagBundle:
    """一次问数召回的语料片段，纠错时复用避免重复向量检索。"""

    question_sql_list: List[Dict]
    ddl_list: List[str]
    doc_list: List[str]


class QueryResultBundle:
    """单次 ask/generate_sql 的结果封装。"""

    def __init__(
        self,
        *,
        sql: str,
        df: Optional[pd.DataFrame] = None,
        sql_source: str = "llm",
        full_response: str = "",
        run_error: Optional[str] = None,
    ) -> None:
        self.sql = sql
        self.df = df
        self.sql_source = sql_source
        self.full_response = full_response
        self.run_error = run_error


class QueryPipeline:
    """查数通道：指标 SQL 优先，RAG+NL2SQL 兜底，含执行纠错。"""

    def __init__(
        self,
        *,
        settings: Settings,
        vector_store: ChromaVectorStore,
        llm: LlmClient,
        prompt_builder: SqlPromptBuilder,
        sql_extractor: SqlExtractor,
        sql_executor: MysqlExecutor,
        session_store: InMemorySessionStore,
        resolver: MetricResolver,
        sql_builder: MetricSqlBuilder,
    ) -> None:
        self._settings = settings
        self._vector = vector_store
        self._llm = llm
        self._prompt_builder = prompt_builder
        self._sql_extractor = sql_extractor
        self._sql_executor = sql_executor
        self._sessions = session_store
        self._resolver = resolver
        self._sql_builder = sql_builder

    @property
    def sessions(self) -> InMemorySessionStore:
        return self._sessions

    def _fetch_rag_bundle(self, retrieval_question: str, table_name: str) -> _RagBundle:
        """从 Chroma 召回相似 SQL、DDL、文档与通用规则。"""
        q = retrieval_question.strip()
        return _RagBundle(
            question_sql_list=self._vector.get_similar_question_sql(q, table_name),
            ddl_list=self._vector.get_related_ddl(q, table_name),
            doc_list=self._vector.get_related_documentation(q, table_name)
            + self._vector.get_related_general(q),
        )

    def _build_rag_prompt(
        self,
        messages: List[Dict],
        table_name: str,
        *,
        rag: Optional[_RagBundle] = None,
    ) -> List[Dict]:
        """组装发给 LLM 的 messages（system + 示例 + 用户问题）。"""
        question = messages[-1]["content"]
        bundle = rag or self._fetch_rag_bundle(question, table_name)
        prompt = self._prompt_builder.build_sql_prompt(
            initial_prompt=self._settings.initial_prompt,
            question=question,
            question_sql_list=bundle.question_sql_list,
            ddl_list=bundle.ddl_list,
            doc_list=bundle.doc_list,
        )
        prompt[-1:-1] = messages[:-1]
        return prompt

    def match_from_entity(self, data: Any) -> Optional[MetricMatch]:
        """从意图路由下发的 entities.metric_match 还原 MetricMatch。"""
        return metric_match_from_entity(data, self._resolver._store)

    def resolve_match(
        self, question: str, cached: Optional[MetricMatch] = None
    ) -> Optional[MetricMatch]:
        """解析自然语言对应的指标；cached 优先避免重复 resolve。"""
        if cached is not None:
            return cached
        return self._resolver.resolve(question)

    def try_metric_sql(
        self,
        question: str,
        *,
        match: Optional[MetricMatch] = None,
        group_by: Optional[List[str]] = None,
    ) -> Optional[str]:
        """若命中指标层则直接生成指标 SQL，否则返回 None 走 NL2SQL。"""
        resolved = self.resolve_match(question, match)
        if not resolved:
            return None
        return self._sql_builder.build(resolved, group_by=group_by)

    def generate_sql(
        self,
        messages: List[Dict],
        table_name: str = "",
        *,
        metric_match: Optional[MetricMatch] = None,
    ) -> QueryResultBundle:
        """同步生成 SQL（指标或 LLM），不执行数据库。"""
        question = messages[-1]["content"]
        metric_sql = self.try_metric_sql(question, match=metric_match)
        if metric_sql:
            return QueryResultBundle(sql=metric_sql, sql_source="metric")

        prompt = self._build_rag_prompt(messages, table_name)
        llm_response = self._llm.complete(prompt)
        sql = self._sql_extractor.extract(llm_response).replace("\\_", "_")
        return QueryResultBundle(
            sql=sql, sql_source="llm", full_response=llm_response
        )

    def generate_sql_stream(
        self,
        messages: List[Dict],
        table_name: str = "",
        *,
        metric_match: Optional[MetricMatch] = None,
    ) -> Generator[str, None, None]:
        """流式生成 SQL 文本（SSE sql_chunk 用）。"""
        question = messages[-1]["content"]
        metric_sql = self.try_metric_sql(question, match=metric_match)
        if metric_sql:
            yield metric_sql
            return
        prompt = self._build_rag_prompt(messages, table_name)
        yield from self._llm.complete_stream(prompt)

    def extract_sql(self, llm_response: str) -> str:
        """从 LLM 回复中提取可执行 SQL 片段。"""
        return self._sql_extractor.extract(llm_response)

    def _mysql_sql_preflight(self, sql: str) -> Optional[str]:
        """执行前检查不支持的方言语法，返回错误说明或 None。"""
        for pattern, message in _MYSQL_PREFLIGHT_CHECKS:
            if pattern.search(sql):
                return message
        return None

    def run_sql(self, sql: str) -> pd.DataFrame:
        """在 MySQL 上执行 SQL 并返回 DataFrame。"""
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
        llm_response: str = "",
        sql_source: str = "llm",
        rag: Optional[_RagBundle] = None,
    ) -> Tuple[pd.DataFrame, str, int]:
        """执行 SQL；失败时用同一 RAG 上下文让 LLM 修正，最多 SQL_CORRECTION_MAX_ATTEMPTS 次。"""
        if sql_source == "metric":
            return self.run_sql(sql), sql, 0

        if rag is None:
            rag = self._fetch_rag_bundle(messages[-1]["content"], table_name)

        current_sql = sql
        current_response = llm_response
        correction_count = 0
        last_error: Optional[Exception] = None

        for attempt in range(SQL_CORRECTION_MAX_ATTEMPTS + 1):
            try:
                df = self.run_sql(current_sql)
                return df, current_sql, correction_count
            except Exception as e:
                last_error = e
                if attempt >= SQL_CORRECTION_MAX_ATTEMPTS:
                    break
                correction_prompt = self._build_rag_prompt(
                    messages, table_name, rag=rag
                )
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

    def ask(
        self,
        *,
        question: str,
        table_name: str = "",
        session_id: Optional[str] = None,
        metric_match: Optional[MetricMatch] = None,
    ) -> QueryResultBundle:
        """端到端：生成 SQL + 执行（含纠错），可选写入 session。"""
        messages = [{"role": "user", "content": question}]
        bundle = self.generate_sql(
            messages, table_name, metric_match=metric_match
        )
        if not bundle.sql or not bundle.sql.strip():
            bundle.run_error = "未生成可执行 SQL"
            return bundle

        rag: Optional[_RagBundle] = None
        if bundle.sql_source != "metric":
            rag = self._fetch_rag_bundle(question, table_name)

        try:
            df, final_sql, _ = self.run_sql_with_correction(
                messages=messages,
                table_name=table_name,
                sql=bundle.sql,
                llm_response=bundle.full_response,
                sql_source=bundle.sql_source,
                rag=rag,
            )
            bundle.sql = final_sql
            bundle.df = df
        except Exception as e:
            bundle.run_error = str(e)

        if session_id:
            self._sessions.set_fields(
                session_id, question=question, sql=bundle.sql
            )
            if bundle.df is not None:
                self._sessions.set_fields(session_id, df=bundle.df)

        return bundle

    def run_preset_sql(self, sql: str) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
        """分析子任务：直接执行 Planner 给出的预设 SQL。"""
        try:
            return sql, self.run_sql(sql), None
        except Exception as e:
            return sql, None, str(e)

    def run_metric_task(
        self,
        task: AnalysisSubTask,
        base_match: MetricMatch,
    ) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
        """分析子任务：按指标模板 + group_by 生成并执行 SQL。"""
        sql = task.preset_sql
        if not sql:
            sql = self._sql_builder.build(
                base_match, group_by=task.group_by or None
            )
        if not sql:
            return "", None, "未生成指标 SQL"
        try:
            return sql, self.run_sql(sql), None
        except Exception as e:
            return sql, None, str(e)

    def run_analysis_task(
        self,
        task: AnalysisSubTask,
        *,
        table_name: str = "",
        base_match: Optional[MetricMatch] = None,
    ) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
        """按子任务 execution 类型分发：preset_sql / metric / nl2sql。"""
        if task.execution == "sql" and task.preset_sql:
            return self.run_preset_sql(task.preset_sql)
        if task.execution == "metric" and base_match is not None:
            return self.run_metric_task(task, base_match)
        return self.run_task_question(
            task.question, table_name=table_name, metric_match=base_match
        )

    def run_task_question(
        self,
        question: str,
        *,
        table_name: str = "",
        metric_match: Optional[MetricMatch] = None,
    ) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
        """分析 Agent 单条自然语言子问题的快捷入口。"""
        bundle = self.ask(
            question=question,
            table_name=table_name,
            metric_match=metric_match,
        )
        return bundle.sql, bundle.df, bundle.run_error
