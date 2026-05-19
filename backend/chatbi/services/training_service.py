from typing import Dict, List, Optional

import pandas as pd

from chatbi.infrastructure.llm.chinese_question_rules import (
    CHINESE_BUSINESS_QUESTION_RULES,
)
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore


class TrainingService:
    """语料训练领域服务：封装向量库的增删改查与示例问题生成。"""

    def __init__(self, vector_store: ChromaVectorStore, llm: LlmClient) -> None:
        self._vector = vector_store
        self._llm = llm

    def add(
        self,
        *,
        question: Optional[str] = None,
        sql: Optional[str] = None,
        ddl: Optional[str] = None,
        documentation: Optional[str] = None,
        general: Optional[str] = None,
        table_name: str = "",
        gen_type: str = "",
    ) -> str:
        if question and sql:
            return self._vector.add_question_sql(question, sql, table_name)
        if ddl:
            return self._vector.add_ddl(ddl, table_name)
        if documentation:
            return self._vector.add_documentation(documentation, table_name)
        if general:
            return self._vector.add_general(general, gen_type)
        raise ValueError("至少需要提供一种训练数据")

    def list_all(self) -> pd.DataFrame:
        return self._vector.get_all_training_data()

    def search(
        self,
        *,
        keyword: Optional[str] = None,
        data_type: Optional[str] = None,
        table_name: Optional[str] = None,
        gen_type: Optional[str] = None,
    ) -> Dict:
        return self._vector.fuzzy_search(
            keyword=keyword,
            data_type=data_type,
            table_name=table_name,
            gen_type=gen_type,
        )

    def remove(self, doc_id: str) -> bool:
        return self._vector.remove_training_data(doc_id)

    def update(
        self,
        *,
        doc_id: str,
        new_content: Optional[str] = None,
        new_question: Optional[str] = None,
        new_gen_type: Optional[str] = None,
        table_name: str = "",
    ) -> Dict:
        return self._vector.update_training_data(
            doc_id,
            new_content=new_content,
            new_question=new_question,
            new_gen_type=new_gen_type,
            table_name=table_name,
        )

    def generate_example_questions(self, table_name: str = "") -> List[str]:
        ddl_list = self._vector.get_related_ddl("表结构", table_name)
        doc_list = self._vector.get_related_documentation("表说明", table_name)
        context = "\n".join(ddl_list + doc_list)

        messages = [
            system_message(
                "你是一个数据分析专家。根据提供的表结构，生成5个业务人员会问的示例问题。\n"
                "每个问题应能通过一条 SQL 查询回答。直接输出问题列表，每行一个，不要编号。\n\n"
                f"{CHINESE_BUSINESS_QUESTION_RULES}"
            ),
            user_message(f"根据以下表结构生成5个示例问题:\n{context}"),
        ]
        response = self._llm.complete(messages)
        return [q.strip() for q in response.split("\n") if q.strip()]
