"""启动时预热 DDL 摘要，意图路由查库范围判断不再每次做向量检索。"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from chatbi.domain.schema_scope import SchemaScopeChecker
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore

log = logging.getLogger("chatbi")


class SchemaContextCache:
    """启动时从 Chroma 拉全量 DDL，构建意图路由用的 schema 摘要与词表。"""

    def __init__(self, vector_store: ChromaVectorStore) -> None:
        self._vector = vector_store
        self._hint: str = ""
        self._vocab: List[str] = []
        self._scope = SchemaScopeChecker()
        self._ready = False

    def warm(self) -> None:
        """首次调用时加载 DDL；失败也标记 ready 避免反复打向量库。"""
        if self._ready:
            return
        try:
            ddls = self._vector.list_all_ddl()
            self._hint = self._scope.build_hint_from_ddl(ddls)
            self._vocab = self._scope.extract_vocab_from_ddl(ddls)
            self._scope = SchemaScopeChecker(self._vocab)
            self._ready = True
            log.info("[schema_cache] 已预热 DDL 条数=%d", len(ddls))
        except Exception as e:
            log.warning("[schema_cache] 预热失败: %s", e)
            self._ready = True

    def get(self) -> Tuple[str, List[str], SchemaScopeChecker]:
        """返回 (DDL 摘要, 词表, SchemaScopeChecker)，供 IntentRouter 使用。"""
        if not self._ready:
            self.warm()
        return self._hint, self._vocab, self._scope

    def refresh(self) -> None:
        """DDL 语料增删改后重建词表与 schema 摘要（替代旧 chat.refresh_ddl_registry）。"""
        self._ready = False
        self._hint = ""
        self._vocab = []
        self._scope = SchemaScopeChecker()
        self.warm()
