import os
# HuggingFace 镜像（在导入 sentence_transformers 之前；可由 .env 的 HF_ENDPOINT 覆盖）
if os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT")
elif "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import uuid
import pandas as pd
from typing import List, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings



class ChromaVectorStore:
    """
    基于 ChromaDB 的向量存储实现
    支持 4 种集合: documentation, ddl, sql, gen
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化 ChromaDB 客户端

        Args:
            config: 配置字典，可包含:
                - persist_directory: 持久化目录，默认为 "./chroma_db"
                - embedding_model: 嵌入模型名称，默认为 "paraphrase-multilingual-MiniLM-L12-v2"
                - openai_api_key: OpenAI API Key (用于 LLM)
                - openai_base_url: OpenAI API 地址
                - model: LLM 模型名称
        """
        self.config = config or {}

        # 初始化 ChromaDB 客户端（持久化模式）
        persist_directory = self.config.get("persist_directory", "./chroma_db")
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )


        # 初始化嵌入模型（sentence-transformers）
        embedding_name = self.config.get(
            "embedding_model", "paraphrase-multilingual-MiniLM-L12-v2"
        )
        cache_folder = self.config.get("model_cache_dir", "./model_cache")
        self.embedding_model = SentenceTransformer(
            embedding_name,
            cache_folder=cache_folder,
        )
        self._embedding_dim = 384  # paraphrase-multilingual-MiniLM-L12-v2 的维度

        # 初始化 OpenAI 客户端（用于 LLM）
        from openai import OpenAI

        api_key = self.config.get("api_key")
        if not api_key:
            raise ValueError("api_key is required for LLM")

        self.model = self.config.get("model", "gpt-3.5-turbo")
        base_url = self.config.get("base_url", "https://api.openai.com/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

        # 集合名称常量
        self.COLLECTION_SQL = "vanna_sql"
        self.COLLECTION_DDL = "vanna_ddl"
        self.COLLECTION_DOC = "vanna_doc"
        self.COLLECTION_GEN = "vanna_gen"

        # 查询结果数量配置
        self.sql_results = 5
        self.ddl_results = 5
        self.doc_results = 15
        self.gen_results = 15

        # 创建所有集合
        self._ensure_collections()

        #文本向量化
    def _get_embedding(self, text: str) -> List[float]:
        """获取文本的嵌入向量"""
        return self.embedding_model.encode(text).tolist()

    def _ensure_collections(self):
        """确保所有集合存在"""
        collections = [
            self.COLLECTION_SQL,
            self.COLLECTION_DDL,
            self.COLLECTION_DOC,
            self.COLLECTION_GEN
        ]

        # 获取已存在的集合列表
        existing_collections = self.chroma_client.list_collections()
        existing_names = [col.name for col in existing_collections] if existing_collections else []

        for collection_name in collections:
            if collection_name not in existing_names:
                try:
                    self.chroma_client.create_collection(
                        name=collection_name,
                        metadata={"hnsw:space": "cosine"}
                    )
                    print(f"✅ 创建集合: {collection_name}")
                except Exception as e:
                    print(f"⚠️ 创建集合 {collection_name} 失败: {e}")
            else:
                print(f"✅ 集合已存在: {collection_name}")

    # ==================== SQL 集合操作 ====================

    def add_question_sql(self, question: str, sql: str, table_name: str = "") -> str:
        """
        添加问答对到 SQL 集合
        """
        if not question or not sql:
            raise ValueError("question and sql cannot be empty")

        _id = str(uuid.uuid4()) + "-sql"
        collection = self.chroma_client.get_collection(self.COLLECTION_SQL)

        embedding = self._get_embedding(question)

        collection.add(
            ids=[_id],
            embeddings=[embedding],
            metadatas=[{
                "question": question,
                "sql": sql,
                "table_name": table_name
            }],
            documents=[question]
        )

        return _id

    def get_similar_question_sql(self, question: str, table_name: str = "") -> List[Dict]:
        """
        根据问题获取相似的 SQL 示例
        """
        collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
        embedding = self._get_embedding(question)

        # 构建过滤条件
        where_filter = None
        if table_name:
            where_filter = {"table_name": table_name}

        results = collection.query(
            query_embeddings=[embedding],
            n_results=self.sql_results,
            where=where_filter,
            include=["metadatas", "documents", "distances"]
        )

        similar_list = []
        if results['metadatas'] and results['metadatas'][0]:
            for i, metadata in enumerate(results['metadatas'][0]):
                similar_list.append({
                    "question": metadata.get("question", ""),
                    "sql": metadata.get("sql", ""),
                    "score": 1 - results['distances'][0][i] if results['distances'] else 0
                })

        return similar_list

    # ==================== DDL 集合操作 ====================

    def add_ddl(self, ddl: str, table_name: str = "") -> str:
        """添加 DDL 语句"""
        if not ddl:
            raise ValueError("ddl cannot be empty")

        _id = str(uuid.uuid4()) + "-ddl"
        collection = self.chroma_client.get_collection(self.COLLECTION_DDL)

        embedding = self._get_embedding(ddl)

        collection.add(
            ids=[_id],
            embeddings=[embedding],
            metadatas=[{
                "ddl": ddl,
                "table_name": table_name
            }],
            documents=[ddl]
        )

        return _id

    def get_related_ddl(self, question: str, table_name: str = "") -> List[str]:
        """获取与问题相关的 DDL"""
        collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
        embedding = self._get_embedding(question)

        where_filter = None
        if table_name:
            where_filter = {"table_name": table_name}

        results = collection.query(
            query_embeddings=[embedding],
            n_results=self.ddl_results,
            where=where_filter,
            include=["metadatas", "documents"]
        )

        ddl_list = []
        if results['metadatas'] and results['metadatas'][0]:
            for metadata in results['metadatas'][0]:
                if "ddl" in metadata:
                    ddl_list.append(metadata["ddl"])

        return ddl_list

    # ==================== Documentation 集合操作 ====================

    def add_documentation(self, documentation: str, table_name: str = "") -> str:
        """添加文档"""
        if not documentation:
            raise ValueError("documentation cannot be empty")

        _id = str(uuid.uuid4()) + "-doc"
        collection = self.chroma_client.get_collection(self.COLLECTION_DOC)

        embedding = self._get_embedding(documentation)

        collection.add(
            ids=[_id],
            embeddings=[embedding],
            metadatas=[{
                "doc": documentation,
                "table_name": table_name
            }],
            documents=[documentation]
        )

        return _id

    def get_related_documentation(self, question: str, table_name: str = "") -> List[str]:
        """获取与问题相关的文档"""
        collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
        embedding = self._get_embedding(question)

        where_filter = None
        if table_name:
            where_filter = {"table_name": table_name}

        results = collection.query(
            query_embeddings=[embedding],
            n_results=self.doc_results,
            where=where_filter,
            include=["metadatas", "documents"]
        )

        doc_list = []
        if results['metadatas'] and results['metadatas'][0]:
            for metadata in results['metadatas'][0]:
                if "doc" in metadata:
                    doc_list.append(metadata["doc"])

        return doc_list

    # ==================== General/Gen 集合操作 ====================

    def add_general(self, general: str, gen_type: str = "") -> str:
        """添加通用知识"""
        if not general:
            raise ValueError("general cannot be empty")

        _id = str(uuid.uuid4()) + "-gen"
        collection = self.chroma_client.get_collection(self.COLLECTION_GEN)

        embedding = self._get_embedding(general)

        collection.add(
            ids=[_id],
            embeddings=[embedding],
            metadatas=[{
                "gen": general,
                "type": gen_type
            }],
            documents=[general]
        )

        return _id

    def get_related_general(self, question: str) -> List[str]:
        """获取与问题相关的通用知识"""
        collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
        embedding = self._get_embedding(question)

        results = collection.query(
            query_embeddings=[embedding],
            n_results=self.gen_results,
            include=["metadatas", "documents"]
        )

        gen_list = []
        if results['metadatas'] and results['metadatas'][0]:
            for metadata in results['metadatas'][0]:
                if "gen" in metadata:
                    gen_list.append(metadata["gen"])

        return gen_list

    # ==================== 通用操作 ====================

    def get_all_training_data(self) -> pd.DataFrame:
        """获取所有训练数据"""
        all_data = []

        # 获取 SQL 数据
        sql_collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
        sql_data = sql_collection.get(include=["metadatas", "documents"])
        if sql_data['ids']:
            for i, id_ in enumerate(sql_data['ids']):
                metadata = sql_data['metadatas'][i] if sql_data['metadatas'] else {}
                all_data.append({
                    "id": id_,
                    "type": "sql",
                    "question": metadata.get("question", ""),
                    "content": metadata.get("sql", ""),
                    "table_name": metadata.get("table_name", "")
                })

        # 获取 DDL 数据
        ddl_collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
        ddl_data = ddl_collection.get(include=["metadatas"])
        if ddl_data['ids']:
            for i, id_ in enumerate(ddl_data['ids']):
                metadata = ddl_data['metadatas'][i] if ddl_data['metadatas'] else {}
                all_data.append({
                    "id": id_,
                    "type": "ddl",
                    "question": "",
                    "content": metadata.get("ddl", ""),
                    "table_name": metadata.get("table_name", "")
                })

        # 获取 Documentation 数据
        doc_collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
        doc_data = doc_collection.get(include=["metadatas"])
        if doc_data['ids']:
            for i, id_ in enumerate(doc_data['ids']):
                metadata = doc_data['metadatas'][i] if doc_data['metadatas'] else {}
                all_data.append({
                    "id": id_,
                    "type": "doc",
                    "question": "",
                    "content": metadata.get("doc", ""),
                    "table_name": metadata.get("table_name", "")
                })

        # 获取 General 数据
        gen_collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
        gen_data = gen_collection.get(include=["metadatas"])
        if gen_data['ids']:
            for i, id_ in enumerate(gen_data['ids']):
                metadata = gen_data['metadatas'][i] if gen_data['metadatas'] else {}
                all_data.append({
                    "id": id_,
                    "type": "gen",
                    "question": "",
                    "content": metadata.get("gen", ""),
                    "table_name": metadata.get("type", "")
                })

        return pd.DataFrame(all_data)

    def remove_training_data(self, id: str) -> bool:
        """删除训练数据"""
        if id.endswith("-sql"):
            collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
            collection.delete(ids=[id])
            return True
        elif id.endswith("-ddl"):
            collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
            collection.delete(ids=[id])
            return True
        elif id.endswith("-doc"):
            collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
            collection.delete(ids=[id])
            return True
        elif id.endswith("-gen"):
            collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
            collection.delete(ids=[id])
            return True
        return False

    def update_training_data(self, id: str, new_content: str = None,
                             new_question: str = None, new_gen_type: str = None,
                             table_name: str = "") -> Dict:
        """更新训练数据"""
        try:
            if id.endswith("-sql"):
                if not new_question or not new_content:
                    return {"success": False, "message": "需要提供问题和SQL", "exists": True}

                collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
                embedding = self._get_embedding(new_question)

                collection.update(
                    ids=[id],
                    embeddings=[embedding],
                    metadatas=[{
                        "question": new_question,
                        "sql": new_content,
                        "table_name": table_name
                    }],
                    documents=[new_question]
                )

            elif id.endswith("-ddl"):
                if not new_content:
                    return {"success": False, "message": "需要提供DDL内容", "exists": True}

                collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
                embedding = self._get_embedding(new_content)

                collection.update(
                    ids=[id],
                    embeddings=[embedding],
                    metadatas=[{
                        "ddl": new_content,
                        "table_name": table_name
                    }],
                    documents=[new_content]
                )

            elif id.endswith("-doc"):
                if not new_content:
                    return {"success": False, "message": "需要提供文档内容", "exists": True}

                collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
                embedding = self._get_embedding(new_content)

                collection.update(
                    ids=[id],
                    embeddings=[embedding],
                    metadatas=[{
                        "doc": new_content,
                        "table_name": table_name
                    }],
                    documents=[new_content]
                )

            elif id.endswith("-gen"):
                collection = self.chroma_client.get_collection(self.COLLECTION_GEN)

                # 获取当前数据
                current = collection.get(ids=[id], include=["metadatas"])
                current_gen = ""
                current_type = ""
                if current['metadatas'] and current['metadatas'][0]:
                    current_gen = current['metadatas'][0].get("gen", "")
                    current_type = current['metadatas'][0].get("type", "")

                final_content = new_content if new_content else current_gen
                final_type = new_gen_type if new_gen_type is not None else current_type

                embedding = self._get_embedding(final_content)

                collection.update(
                    ids=[id],
                    embeddings=[embedding],
                    metadatas=[{
                        "gen": final_content,
                        "type": final_type
                    }],
                    documents=[final_content]
                )
            else:
                return {"success": False, "message": "无效的ID格式", "exists": False}

            return {"success": True, "message": "更新成功", "exists": True}

        except Exception as e:
            return {"success": False, "message": f"更新失败: {str(e)}", "exists": False}

    def fuzzy_search(self, keyword: str = None, data_type: str = None,
                     table_name: str = None, gen_type: str = None) -> Dict:
        """模糊搜索训练数据"""
        all_results = []

        collections_to_search = []
        if data_type == "sql":
            collections_to_search = [(self.COLLECTION_SQL, "sql", "question", "sql")]
        elif data_type == "ddl":
            collections_to_search = [(self.COLLECTION_DDL, "ddl", "ddl", "ddl")]
        elif data_type == "doc":
            collections_to_search = [(self.COLLECTION_DOC, "doc", "doc", "doc")]
        elif data_type == "gen":
            collections_to_search = [(self.COLLECTION_GEN, "gen", "gen", "type")]
        else:
            collections_to_search = [
                (self.COLLECTION_SQL, "sql", "question", "sql"),
                (self.COLLECTION_DDL, "ddl", "ddl", "ddl"),
                (self.COLLECTION_DOC, "doc", "doc", "doc"),
                (self.COLLECTION_GEN, "gen", "gen", "type")
            ]

        for collection_name, data_type_name, content_field, extra_field in collections_to_search:
            try:
                collection = self.chroma_client.get_collection(collection_name)

                # 获取所有数据并手动过滤（ChromaDB 的全文搜索有限）
                all_data = collection.get(include=["metadatas", "documents"])

                for i, id_ in enumerate(all_data['ids']):
                    metadata = all_data['metadatas'][i] if all_data['metadatas'] else {}
                    document = all_data['documents'][i] if all_data['documents'] else ""

                    # 应用过滤条件
                    if keyword and keyword.lower() not in document.lower():
                        continue

                    if table_name and metadata.get("table_name", "") != table_name:
                        continue

                    if gen_type and metadata.get("type", "") != gen_type:
                        continue

                    if data_type and data_type != data_type_name:
                        continue

                    result = {
                        "id": id_,
                        "data_type": data_type_name,
                        "content": document,
                        "table_name": metadata.get("table_name", ""),
                        extra_field: metadata.get(extra_field, "")
                    }
                    if data_type_name == "sql":
                        result["question"] = metadata.get("question", "")

                    all_results.append(result)

            except Exception as e:
                print(f"Error searching {collection_name}: {e}")

        return {
            "data": all_results,
            "total": len(all_results)
        }

    # ==================== LLM 相关方法 ====================

    def submit_prompt(self, messages: List[Dict]) -> str:
        """提交提示词给 LLM"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content

    def submit_prompt_stream(self, messages: List[Dict]):
        """流式提交提示词给 LLM"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def extract_sql(self, llm_response: str) -> str:
        """从 LLM 响应中提取 SQL"""
        import re

        # 匹配 CREATE TABLE ... AS SELECT
        sqls = re.findall(r"\bCREATE\s+TABLE\b[\s\S]*?\bAS\b.*?;", llm_response, re.DOTALL | re.IGNORECASE)
        if sqls:
            return sqls[-1]

        # 匹配 WITH 子句
        sqls = re.findall(r"\bWITH\b[\s\S]*?;", llm_response, re.DOTALL | re.IGNORECASE)
        if sqls:
            return sqls[-1]

        # 匹配 SELECT 语句
        sqls = re.findall(r"\bSELECT\b[\s\S]*?;", llm_response, re.DOTALL | re.IGNORECASE)
        if sqls:
            return sqls[-1]

        # 匹配 ```sql ... ``` 块
        sqls = re.findall(r"```sql\s*\n(.*?)```", llm_response, re.DOTALL | re.IGNORECASE)
        if sqls:
            return sqls[-1].strip()

        # 匹配任意 ``` ... ``` 块
        sqls = re.findall(r"```(.*?)```", llm_response, re.DOTALL)
        if sqls:
            return sqls[-1].strip()

        return llm_response

    def system_message(self, message: str) -> Dict:
        """创建系统消息"""
        return {"role": "system", "content": message}

    def user_message(self, message: str) -> Dict:
        """创建用户消息"""
        return {"role": "user", "content": message}

    def assistant_message(self, message: str) -> Dict:
        """创建助手消息"""
        return {"role": "assistant", "content": message}

    def get_sql_prompt(self, initial_prompt: str, question: str,
                       question_sql_list: List[Dict], ddl_list: List[str],
                       doc_list: List[str]) -> List[Dict]:
        """生成 SQL 提示词"""
        import datetime

        if initial_prompt is None:
            initial_prompt = "你是一位SQL专家。请根据给定的上下文生成SQL查询来回答问题。你的回复应严格基于所提供的上下文。"

        today = datetime.datetime.now().strftime("%Y-%m-%d")

        initial_prompt = (
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

        initial_prompt += "\n===文档信息===\n" + "\n".join(doc_list) if doc_list else ""

        message_log = [self.system_message(initial_prompt)]

        for example in question_sql_list:
            if example and "question" in example and "sql" in example:
                message_log.append(self.user_message(example["question"]))
                message_log.append(self.assistant_message(example["sql"]))

        message_log.append(self.user_message(question))

        return message_log

    def generate_sql(self, messages: List[Dict], table_name: str = "") -> Dict:
        """生成 SQL"""
        question = messages[-1]["content"]

        # 获取相似问答对
        question_sql_list = self.get_similar_question_sql(question, table_name)
        # 获取相关 DDL
        ddl_list = self.get_related_ddl(question, table_name)
        # 获取相关文档
        doc_list = self.get_related_documentation(question, table_name)
        # 获取通用知识
        gen_list = self.get_related_general(question)

        prompt = self.get_sql_prompt(
            initial_prompt=self.config.get("initial_prompt"),
            question=question,
            question_sql_list=question_sql_list,
            ddl_list=ddl_list,
            doc_list=doc_list + gen_list
        )

        # 插入历史对话
        prompt[-1:-1] = messages[:-1]

        llm_response = self.submit_prompt(prompt)
        sql = self.extract_sql(llm_response)
        sql = sql.replace("\\_", "_")

        return {"sql": sql, "full_response": llm_response}

    def generate_sql_stream(self, messages: List[Dict], table_name: str = ""):
        """流式生成 SQL"""
        question = messages[-1]["content"]

        question_sql_list = self.get_similar_question_sql(question, table_name)
        ddl_list = self.get_related_ddl(question, table_name)
        doc_list = self.get_related_documentation(question, table_name)
        gen_list = self.get_related_general(question)

        prompt = self.get_sql_prompt(
            initial_prompt=self.config.get("initial_prompt"),
            question=question,
            question_sql_list=question_sql_list,
            ddl_list=ddl_list,
            doc_list=doc_list + gen_list
        )

        prompt[-1:-1] = messages[:-1]

        for chunk in self.submit_prompt_stream(prompt):
            yield chunk

    def generate_followup_questions(self, question: str, sql: str, df: pd.DataFrame, n_questions: int = 5) -> List[str]:
        """生成后续问题"""
        import re

        message_log = [
            self.system_message(
                "你是一个SQL问题生成器。请严格按以下规则生成后续问题："
                "1. 只生成能用一条SQL回答的问题\n"
                "2. 每个问题必须是独立、完整的中文句子\n"
                "3. 禁止包含任何解释、推理或上下文说明\n"
                "4. 直接列出问题，不要编号\n\n"
                f"参考信息：原问题='{question}'，SQL='{sql}'，数据示例：\n{df.head(5).to_string() if not df.empty else '无数据'}"
            ),
            self.user_message(f"请直接生成{n_questions}个后续问题，每个问题单独一行。")
        ]

        llm_response = self.submit_prompt(message_log)

        if not isinstance(llm_response, str):
            llm_response = str(llm_response)

        numbers_removed = re.sub(r"^\d+\.\s*", "", llm_response, flags=re.MULTILINE)
        return [q.strip() for q in numbers_removed.split("\n") if q.strip()]

    def generate_plotly_code(self, question: str, sql: str, df_metadata: str) -> str:
        """生成 Plotly 图表代码"""
        message_log = [
            self.system_message(
                "你是一个数据可视化专家。根据用户的问题、SQL查询和数据结构，生成完整的Python Plotly代码来创建图表。\n"
                "要求：\n"
                "1. 只返回Python代码，不要有任何解释\n"
                "2. 代码必须包含 plotly 库的导入\n"
                "3. 生成的 figure 对象必须赋值给 fig 变量\n"
                "4. 根据数据特征选择合适的图表类型\n"
                "5. 确保代码可以直接运行"
            ),
            self.user_message(
                f"问题: {question}\n"
                f"SQL: {sql}\n"
                f"数据结构:\n{df_metadata}\n\n"
                f"请生成 Python Plotly 代码来可视化这些数据。"
            )
        ]

        return self.submit_prompt(message_log)

    def get_plotly_figure(self, plotly_code: str, df: pd.DataFrame, dark_mode: bool = False):
        """执行 Plotly 代码生成图表"""
        import plotly.express as px
        import plotly.graph_objects as go

        local_vars = {"df": df, "px": px, "go": go, "pd": pd}

        try:
            exec(plotly_code, globals(), local_vars)
            fig = local_vars.get("fig")
            if fig is None:
                raise ValueError("代码没有生成 fig 对象")
            return fig
        except Exception as e:
            raise Exception(f"执行图表代码失败: {str(e)}")