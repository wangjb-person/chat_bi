"""ChromaDB 向量存储：仅负责语料嵌入、检索与 CRUD，不包含 LLM 逻辑。"""

from __future__ import annotations

import os
import uuid
from typing import Dict, List, Optional

import pandas as pd

if os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT")
elif "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class ChromaVectorStore:
    """
    基于 ChromaDB 的向量存储实现。
    支持四类语料集合：问答 SQL、DDL、业务文档、通用规则。
    """

    # 持久化库中的集合名（沿用早期标识，避免已有 chroma 数据失效）
    COLLECTION_SQL = "vanna_sql"
    COLLECTION_DDL = "vanna_ddl"
    COLLECTION_DOC = "vanna_doc"
    COLLECTION_GEN = "vanna_gen"
    COLLECTION_KB = "kb_chunks"

    def __init__(
        self,
        *,
        persist_directory: str = "./chroma_db",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        model_cache_dir: str = "./model_cache",
        sql_results: int = 5,
        ddl_results: int = 5,
        doc_results: int = 15,
        gen_results: int = 15,
    ) -> None:
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self.embedding_model = SentenceTransformer(
            embedding_model,
            cache_folder=model_cache_dir,
        )
        self.sql_results = sql_results
        self.ddl_results = ddl_results
        self.doc_results = doc_results
        self.gen_results = gen_results
        self._ensure_collections()

    def _get_embedding(self, text: str) -> List[float]:
        return self.embedding_model.encode(text).tolist()

    def _ensure_collections(self) -> None:
        collections = [
            self.COLLECTION_SQL,
            self.COLLECTION_DDL,
            self.COLLECTION_DOC,
            self.COLLECTION_GEN,
            self.COLLECTION_KB,
        ]
        existing = self.chroma_client.list_collections()
        existing_names = [col.name for col in existing] if existing else []

        for name in collections:
            if name not in existing_names:
                try:
                    self.chroma_client.create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"},
                    )
                    print(f"[chroma] created collection: {name}")
                except Exception as e:
                    print(f"[chroma] create collection {name} failed: {e}")
            else:
                print(f"[chroma] collection exists: {name}")

    def add_question_sql(self, question: str, sql: str, table_name: str = "") -> str:
        if not question or not sql:
            raise ValueError("question and sql cannot be empty")

        doc_id = str(uuid.uuid4()) + "-sql"
        collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
        collection.add(
            ids=[doc_id],
            embeddings=[self._get_embedding(question)],
            metadatas=[{"question": question, "sql": sql, "table_name": table_name}],
            documents=[question],
        )
        return doc_id

    def get_similar_question_sql(
        self, question: str, table_name: str = ""
    ) -> List[Dict]:
        collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
        where_filter = {"table_name": table_name} if table_name else None
        results = collection.query(
            query_embeddings=[self._get_embedding(question)],
            n_results=self.sql_results,
            where=where_filter,
            include=["metadatas", "documents", "distances"],
        )

        similar_list = []
        if results["metadatas"] and results["metadatas"][0]:
            for i, metadata in enumerate(results["metadatas"][0]):
                similar_list.append(
                    {
                        "question": metadata.get("question", ""),
                        "sql": metadata.get("sql", ""),
                        "score": (
                            1 - results["distances"][0][i]
                            if results["distances"]
                            else 0
                        ),
                    }
                )
        return similar_list

    def add_ddl(self, ddl: str, table_name: str = "") -> str:
        if not ddl:
            raise ValueError("ddl cannot be empty")

        doc_id = str(uuid.uuid4()) + "-ddl"
        collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
        collection.add(
            ids=[doc_id],
            embeddings=[self._get_embedding(ddl)],
            metadatas=[{"ddl": ddl, "table_name": table_name}],
            documents=[ddl],
        )
        return doc_id

    def get_related_ddl(self, question: str, table_name: str = "") -> List[str]:
        collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
        where_filter = {"table_name": table_name} if table_name else None
        results = collection.query(
            query_embeddings=[self._get_embedding(question)],
            n_results=self.ddl_results,
            where=where_filter,
            include=["metadatas", "documents"],
        )

        ddl_list = []
        if results["metadatas"] and results["metadatas"][0]:
            for metadata in results["metadatas"][0]:
                if "ddl" in metadata:
                    ddl_list.append(metadata["ddl"])
        return ddl_list

    def list_all_ddl(self, *, limit: int = 50) -> List[str]:
        """列出已入库 DDL（无向量检索，供意图路由预热）。"""
        try:
            collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
            data = collection.get(include=["metadatas"], limit=limit)
        except Exception:
            return []
        ddl_list: List[str] = []
        if data.get("metadatas"):
            for metadata in data["metadatas"]:
                if metadata and "ddl" in metadata:
                    ddl_list.append(metadata["ddl"])
        return ddl_list

    def add_documentation(self, documentation: str, table_name: str = "") -> str:
        if not documentation:
            raise ValueError("documentation cannot be empty")

        doc_id = str(uuid.uuid4()) + "-doc"
        collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
        collection.add(
            ids=[doc_id],
            embeddings=[self._get_embedding(documentation)],
            metadatas=[{"doc": documentation, "table_name": table_name}],
            documents=[documentation],
        )
        return doc_id

    def get_related_documentation(
        self, question: str, table_name: str = ""
    ) -> List[str]:
        collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
        where_filter = {"table_name": table_name} if table_name else None
        results = collection.query(
            query_embeddings=[self._get_embedding(question)],
            n_results=self.doc_results,
            where=where_filter,
            include=["metadatas", "documents"],
        )

        doc_list = []
        if results["metadatas"] and results["metadatas"][0]:
            for metadata in results["metadatas"][0]:
                if "doc" in metadata:
                    doc_list.append(metadata["doc"])
        return doc_list

    def add_general(self, general: str, gen_type: str = "") -> str:
        if not general:
            raise ValueError("general cannot be empty")

        doc_id = str(uuid.uuid4()) + "-gen"
        collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
        collection.add(
            ids=[doc_id],
            embeddings=[self._get_embedding(general)],
            metadatas=[{"gen": general, "type": gen_type}],
            documents=[general],
        )
        return doc_id

    def get_related_general(self, question: str) -> List[str]:
        collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
        results = collection.query(
            query_embeddings=[self._get_embedding(question)],
            n_results=self.gen_results,
            include=["metadatas", "documents"],
        )

        gen_list = []
        if results["metadatas"] and results["metadatas"][0]:
            for metadata in results["metadatas"][0]:
                if "gen" in metadata:
                    gen_list.append(metadata["gen"])
        return gen_list

    def get_all_training_data(self) -> pd.DataFrame:
        all_data = []

        sql_collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
        sql_data = sql_collection.get(include=["metadatas", "documents"])
        if sql_data["ids"]:
            for i, doc_id in enumerate(sql_data["ids"]):
                metadata = sql_data["metadatas"][i] if sql_data["metadatas"] else {}
                all_data.append(
                    {
                        "id": doc_id,
                        "type": "sql",
                        "question": metadata.get("question", ""),
                        "content": metadata.get("sql", ""),
                        "table_name": metadata.get("table_name", ""),
                    }
                )

        ddl_collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
        ddl_data = ddl_collection.get(include=["metadatas"])
        if ddl_data["ids"]:
            for i, doc_id in enumerate(ddl_data["ids"]):
                metadata = ddl_data["metadatas"][i] if ddl_data["metadatas"] else {}
                all_data.append(
                    {
                        "id": doc_id,
                        "type": "ddl",
                        "question": "",
                        "content": metadata.get("ddl", ""),
                        "table_name": metadata.get("table_name", ""),
                    }
                )

        doc_collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
        doc_data = doc_collection.get(include=["metadatas"])
        if doc_data["ids"]:
            for i, doc_id in enumerate(doc_data["ids"]):
                metadata = doc_data["metadatas"][i] if doc_data["metadatas"] else {}
                all_data.append(
                    {
                        "id": doc_id,
                        "type": "doc",
                        "question": "",
                        "content": metadata.get("doc", ""),
                        "table_name": metadata.get("table_name", ""),
                    }
                )

        gen_collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
        gen_data = gen_collection.get(include=["metadatas"])
        if gen_data["ids"]:
            for i, doc_id in enumerate(gen_data["ids"]):
                metadata = gen_data["metadatas"][i] if gen_data["metadatas"] else {}
                all_data.append(
                    {
                        "id": doc_id,
                        "type": "gen",
                        "question": "",
                        "content": metadata.get("gen", ""),
                        "table_name": metadata.get("type", ""),
                    }
                )

        return pd.DataFrame(all_data)

    def remove_training_data(self, doc_id: str) -> bool:
        mapping = {
            "-sql": self.COLLECTION_SQL,
            "-ddl": self.COLLECTION_DDL,
            "-doc": self.COLLECTION_DOC,
            "-gen": self.COLLECTION_GEN,
        }
        for suffix, collection_name in mapping.items():
            if doc_id.endswith(suffix):
                collection = self.chroma_client.get_collection(collection_name)
                collection.delete(ids=[doc_id])
                return True
        return False

    def update_training_data(
        self,
        doc_id: str,
        new_content: Optional[str] = None,
        new_question: Optional[str] = None,
        new_gen_type: Optional[str] = None,
        table_name: str = "",
    ) -> Dict:
        try:
            if doc_id.endswith("-sql"):
                if not new_question or not new_content:
                    return {
                        "success": False,
                        "message": "需要提供问题和SQL",
                        "exists": True,
                    }
                collection = self.chroma_client.get_collection(self.COLLECTION_SQL)
                collection.update(
                    ids=[doc_id],
                    embeddings=[self._get_embedding(new_question)],
                    metadatas=[
                        {
                            "question": new_question,
                            "sql": new_content,
                            "table_name": table_name,
                        }
                    ],
                    documents=[new_question],
                )
            elif doc_id.endswith("-ddl"):
                if not new_content:
                    return {
                        "success": False,
                        "message": "需要提供DDL内容",
                        "exists": True,
                    }
                collection = self.chroma_client.get_collection(self.COLLECTION_DDL)
                collection.update(
                    ids=[doc_id],
                    embeddings=[self._get_embedding(new_content)],
                    metadatas=[{"ddl": new_content, "table_name": table_name}],
                    documents=[new_content],
                )
            elif doc_id.endswith("-doc"):
                if not new_content:
                    return {
                        "success": False,
                        "message": "需要提供文档内容",
                        "exists": True,
                    }
                collection = self.chroma_client.get_collection(self.COLLECTION_DOC)
                collection.update(
                    ids=[doc_id],
                    embeddings=[self._get_embedding(new_content)],
                    metadatas=[{"doc": new_content, "table_name": table_name}],
                    documents=[new_content],
                )
            elif doc_id.endswith("-gen"):
                collection = self.chroma_client.get_collection(self.COLLECTION_GEN)
                current = collection.get(ids=[doc_id], include=["metadatas"])
                current_gen = ""
                current_type = ""
                if current["metadatas"] and current["metadatas"][0]:
                    current_gen = current["metadatas"][0].get("gen", "")
                    current_type = current["metadatas"][0].get("type", "")

                final_content = new_content if new_content else current_gen
                final_type = (
                    new_gen_type if new_gen_type is not None else current_type
                )
                collection.update(
                    ids=[doc_id],
                    embeddings=[self._get_embedding(final_content)],
                    metadatas=[{"gen": final_content, "type": final_type}],
                    documents=[final_content],
                )
            else:
                return {"success": False, "message": "无效的ID格式", "exists": False}

            return {"success": True, "message": "更新成功", "exists": True}
        except Exception as e:
            return {
                "success": False,
                "message": f"更新失败: {str(e)}",
                "exists": False,
            }

    def fuzzy_search(
        self,
        keyword: Optional[str] = None,
        data_type: Optional[str] = None,
        table_name: Optional[str] = None,
        gen_type: Optional[str] = None,
    ) -> Dict:
        all_results = []

        if data_type == "sql":
            collections_to_search = [
                (self.COLLECTION_SQL, "sql", "question", "sql")
            ]
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
                (self.COLLECTION_GEN, "gen", "gen", "type"),
            ]

        for (
            collection_name,
            data_type_name,
            content_field,
            extra_field,
        ) in collections_to_search:
            try:
                collection = self.chroma_client.get_collection(collection_name)
                all_data = collection.get(include=["metadatas", "documents"])

                for i, item_id in enumerate(all_data["ids"]):
                    metadata = (
                        all_data["metadatas"][i] if all_data["metadatas"] else {}
                    )
                    document = (
                        all_data["documents"][i] if all_data["documents"] else ""
                    )

                    if keyword and keyword.lower() not in document.lower():
                        continue
                    if table_name and metadata.get("table_name", "") != table_name:
                        continue
                    if gen_type and metadata.get("type", "") != gen_type:
                        continue
                    if data_type and data_type != data_type_name:
                        continue

                    result = {
                        "id": item_id,
                        "data_type": data_type_name,
                        "content": document,
                        "table_name": metadata.get("table_name", ""),
                        extra_field: metadata.get(extra_field, ""),
                    }
                    if data_type_name == "sql":
                        result["question"] = metadata.get("question", "")

                    all_results.append(result)
            except Exception as e:
                print(f"Error searching {collection_name}: {e}")

        return {"data": all_results, "total": len(all_results)}

    def add_kb_chunks(self, doc_id: str, doc_title: str, chunks: List[str]) -> int:
        """写入文档切片到独立知识库集合（与 vanna_doc 隔离）。"""
        if not chunks:
            return 0
        collection = self.chroma_client.get_collection(self.COLLECTION_KB)
        ids: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict] = []
        documents: List[str] = []
        for index, chunk in enumerate(chunks):
            text = chunk.strip()
            if not text:
                continue
            ids.append(f"{doc_id}-{index}")
            embeddings.append(self._get_embedding(text))
            metadatas.append(
                {
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "chunk_index": index,
                }
            )
            documents.append(text)
        if not ids:
            return 0
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        return len(ids)

    def delete_kb_document(self, doc_id: str) -> None:
        """按 doc_id 删除该文档的全部切片。"""
        try:
            collection = self.chroma_client.get_collection(self.COLLECTION_KB)
            collection.delete(where={"doc_id": doc_id})
        except Exception as e:
            print(f"[chroma] delete kb doc {doc_id}: {e}")

    def kb_chunk_count(self) -> int:
        """知识库集合中的切片总数。"""
        try:
            collection = self.chroma_client.get_collection(self.COLLECTION_KB)
            return int(collection.count())
        except Exception:
            return 0

    def list_all_kb_chunks(self) -> List[Dict[str, object]]:
        """返回库内全部切片（用于小库关键词补救）。"""
        try:
            collection = self.chroma_client.get_collection(self.COLLECTION_KB)
        except Exception:
            return []
        if collection.count() == 0:
            return []

        data = collection.get(include=["metadatas", "documents"])
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        out: List[Dict[str, object]] = []
        for meta, doc in zip(metas, docs):
            if not doc:
                continue
            out.append(
                {
                    "text": doc,
                    "doc_title": (meta or {}).get("doc_title", ""),
                    "doc_id": (meta or {}).get("doc_id", ""),
                    "chunk_index": (meta or {}).get("chunk_index", 0),
                    "score": 0.0,
                }
            )
        return out

    def query_kb(
        self, question: str, *, n_results: int = 5
    ) -> List[Dict[str, object]]:
        """检索知识库切片；返回 text、doc_title、chunk_index、score（越大越相似）。"""
        try:
            collection = self.chroma_client.get_collection(self.COLLECTION_KB)
        except Exception:
            return []
        total = collection.count()
        if total == 0:
            return []

        k = min(max(1, n_results), total)
        results = collection.query(
            query_embeddings=[self._get_embedding(question)],
            n_results=k,
            include=["metadatas", "documents", "distances"],
        )
        out: List[Dict[str, object]] = []
        metas = results.get("metadatas") or [[]]
        docs = results.get("documents") or [[]]
        dists = results.get("distances") or [[]]
        for meta, doc, dist in zip(metas[0], docs[0], dists[0]):
            if not doc:
                continue
            score = 1.0 - float(dist) if dist is not None else 0.0
            out.append(
                {
                    "text": doc,
                    "doc_title": (meta or {}).get("doc_title", ""),
                    "doc_id": (meta or {}).get("doc_id", ""),
                    "chunk_index": (meta or {}).get("chunk_index", 0),
                    "score": round(score, 4),
                }
            )
        return out
