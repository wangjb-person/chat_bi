"""
企业知识库：文档登记、多格式解析、自动切块、向量入库与检索。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore
from chatbi.services.kb_chunking import chunk_document, chunk_text
from chatbi.services.kb_retrieval import (
    extract_query_terms,
    merge_hits,
    pick_keyword_rescues,
    rerank_kb_hits,
    resolve_retrieve_counts,
)
from chatbi.services.kb_parsers import (
    SUPPORTED_SUFFIXES,
    ParsedKbDocument,
    is_supported_upload,
    parse_paste,
    parse_upload,
    supported_suffixes_hint,
)

# 路由/前端可引用
ALLOWED_SUFFIXES = SUPPORTED_SUFFIXES


class KbService:
    """知识库文档的入库、删除、列表与向量检索。"""

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        *,
        registry_path: Path,
        files_dir: Path,
        retrieve_top_k: int = 8,
        retrieve_pool_max: int = 40,
        keyword_rescue_max_chunks: int = 120,
        keyword_weight: float = 0.45,
        chunk_size: int = 600,
        chunk_overlap: int = 120,
    ) -> None:
        self._vector = vector_store
        self._registry_path = registry_path
        self._files_dir = files_dir
        self._retrieve_top_k = max(1, retrieve_top_k)
        self._retrieve_pool_max = max(self._retrieve_top_k, retrieve_pool_max)
        self._keyword_rescue_max_chunks = max(0, keyword_rescue_max_chunks)
        self._keyword_weight = min(max(0.0, keyword_weight), 0.85)
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._files_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_registry()

    def list_documents(self) -> List[Dict[str, Any]]:
        """返回已入库文档元数据列表（新在前）。"""
        return list(self._load_registry().get("documents", []))

    def ingest_text(
        self,
        *,
        title: str,
        content: str,
        filename: str = "",
    ) -> Dict[str, Any]:
        """粘贴/纯文本入库。"""
        parsed = parse_paste(content, filename=filename or "paste.txt")
        return self._ingest_parsed(
            parsed,
            title=title or parsed.text[:20],
            filename=filename or "paste.txt",
        )

    def ingest_upload(
        self,
        *,
        title: str,
        raw_bytes: bytes,
        original_filename: str,
    ) -> Dict[str, Any]:
        """上传文件入库（后缀决定解析器）。"""
        if not is_supported_upload(original_filename):
            suf = Path(original_filename or "").suffix.lower()
            raise ValueError(
                f"不支持该文件类型 {suf}，支持：{supported_suffixes_hint()}"
            )
        parsed = parse_upload(raw_bytes, original_filename)
        return self._ingest_parsed(
            parsed,
            title=title or Path(original_filename or "文档").stem,
            filename=original_filename,
            raw_bytes=raw_bytes,
        )

    def delete_document(self, doc_id: str) -> bool:
        """删除登记信息、磁盘文件与向量切片。"""
        reg = self._load_registry()
        docs = reg.get("documents", [])
        new_docs = [d for d in docs if d.get("id") != doc_id]
        if len(new_docs) == len(docs):
            return False
        reg["documents"] = new_docs
        self._save_registry(reg)
        self._vector.delete_kb_document(doc_id)
        for path in self._files_dir.glob(f"{doc_id}.*"):
            path.unlink(missing_ok=True)
        return True

    def retrieve(
        self, question: str, *, top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        混合检索：向量扩大候选池 → 关键词重排 → 小库关键词补救。

        长文档切片较多时自动提高送入 LLM 的条数，降低「库里有、Top5 没有」的漏召回。
        """
        q = (question or "").strip()
        if not q:
            return []

        total = self._vector.kb_chunk_count()
        if total == 0:
            return []

        base_k = top_k if top_k is not None else self._retrieve_top_k
        pool_k, final_k = resolve_retrieve_counts(
            total,
            top_k=base_k,
            pool_max=self._retrieve_pool_max,
        )

        pool = self._vector.query_kb(q, n_results=pool_k)

        if total <= self._keyword_rescue_max_chunks:
            rescues = pick_keyword_rescues(
                extract_query_terms(q),
                self._vector.list_all_kb_chunks(),
                pool,
            )
            pool = merge_hits(pool, rescues)

        return rerank_kb_hits(
            q,
            pool,
            final_k=final_k,
            keyword_weight=self._keyword_weight,
        )

    def _ensure_registry(self) -> None:
        """初始化空登记文件。"""
        if self._registry_path.exists():
            return
        self._save_registry({"documents": []})

    def _load_registry(self) -> Dict[str, Any]:
        """读取 kb_documents.json。"""
        self._ensure_registry()
        with open(self._registry_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_registry(self, data: Dict[str, Any]) -> None:
        """写入 kb_documents.json。"""
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _ingest_parsed(
        self,
        parsed: ParsedKbDocument,
        *,
        title: str,
        filename: str,
        raw_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """切块、写文件、写向量、登记元数据。"""
        name = (title or "").strip() or (filename or "未命名文档")
        doc_id = str(uuid.uuid4())
        chunks = chunk_document(
            parsed.text,
            parsed.chunk_profile,
            chunk_size=self._chunk_size,
            overlap=self._chunk_overlap,
        )
        if not chunks:
            raise ValueError("分块后无有效内容")

        stored_name = self._persist_file(
            doc_id,
            raw_bytes=raw_bytes,
            text=parsed.text,
            suffix=parsed.suffix,
        )
        count = self._vector.add_kb_chunks(doc_id, name, chunks)
        record = {
            "id": doc_id,
            "title": name,
            "filename": filename or stored_name,
            "chunk_count": count,
            "file_kind": parsed.file_kind.value,
            "chunk_profile": parsed.chunk_profile.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        reg = self._load_registry()
        docs = reg.get("documents", [])
        docs.insert(0, record)
        reg["documents"] = docs
        self._save_registry(reg)
        return record

    def _persist_file(
        self,
        doc_id: str,
        *,
        raw_bytes: Optional[bytes],
        text: str,
        suffix: str,
    ) -> str:
        """保存原始文件或纯文本副本到 kb_files/。"""
        ext = suffix if suffix.startswith(".") else f".{suffix}"
        path = self._files_dir / f"{doc_id}{ext or '.txt'}"
        if raw_bytes is not None:
            path.write_bytes(raw_bytes)
        else:
            path.write_text(text, encoding="utf-8")
        return path.name


__all__ = ["KbService", "chunk_text", "ALLOWED_SUFFIXES", "SUPPORTED_SUFFIXES"]
