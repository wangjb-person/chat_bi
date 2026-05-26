import hashlib
import uuid


def generate_uuid() -> str:
    """生成 UUID 字符串（对话会话 ID、轮次 ID 等）。"""
    return str(uuid.uuid4())


def generate_session_id(text: str) -> str:
    """根据问题或 SQL 片段生成会话缓存键（与原 generate_id 行为一致）。"""
    return hashlib.md5(text.encode()).hexdigest()


def generate_turn_id() -> str:
    """单次 ask 的运行时缓存键（plot/followup 等后续接口使用）。"""
    return generate_uuid()
