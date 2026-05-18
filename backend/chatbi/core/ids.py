import hashlib


def generate_session_id(text: str) -> str:
    """根据问题或 SQL 片段生成会话缓存键（与原 generate_id 行为一致）。"""
    return hashlib.md5(text.encode()).hexdigest()
