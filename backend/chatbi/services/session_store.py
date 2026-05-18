from typing import Any, Dict, List, Optional


class InMemorySessionStore:
    """问数会话临时状态（SQL、结果集等）；演示版内存实现，可替换为 Redis。"""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(session_id)

    def ensure(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._store:
            self._store[session_id] = {}
        return self._store[session_id]

    def set_fields(self, session_id: str, **fields: Any) -> None:
        bucket = self.ensure(session_id)
        bucket.update(fields)

    def has_fields(self, session_id: str, fields: List[str]) -> bool:
        bucket = self._store.get(session_id)
        if not bucket:
            return False
        return all(field in bucket for field in fields)

    def keys(self) -> List[str]:
        return list(self._store.keys())

    def debug_snapshot(self) -> Dict[str, Dict[str, str]]:
        return {
            k: {kk: str(vv)[:100] for kk, vv in v.items()}
            for k, v in self._store.items()
        }
