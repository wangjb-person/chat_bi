from functools import wraps
from typing import Callable, List

from flask import jsonify, request

from chatbi.api.deps import get_container


def requires_session(*fields: str) -> Callable:
    """校验会话缓存中是否包含指定字段（原 requires_cache 装饰器）。"""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            request_data = request.get_json(silent=True)
            if not request_data:
                return jsonify({"error": "Invalid JSON format"}), 400

            session_id = request_data.get("id")
            if not session_id:
                return jsonify({"error": "Missing id"}), 400

            sessions = get_container().sessions
            bucket = sessions.get(session_id)
            if not bucket:
                return jsonify({"error": f"No {fields[0]} found in cache"}), 400
            for field in fields:
                if field not in bucket:
                    return jsonify({"error": f"No {field} found in cache"}), 400

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
