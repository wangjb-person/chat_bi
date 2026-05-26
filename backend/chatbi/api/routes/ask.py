import json
import logging

from flask import Blueprint, Response, request

from chatbi.api.deps import get_container
from chatbi.core.conversation_context import trim_messages

log = logging.getLogger("chatbi")

ask_bp = Blueprint("ask", __name__, url_prefix="/api")

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "close",
    "X-Accel-Buffering": "no",
}


@ask_bp.route("/ask/stream", methods=["POST"])
def ask_stream():
    data = request.get_json() or {}
    messages = data.get("messages", [])
    table_name = data.get("table_name", "")
    mode = (data.get("mode") or "chatbi").strip().lower()
    if mode not in ("chatbi", "kb"):
        mode = "chatbi"

    if not messages:
        return Response(
            json.dumps({"error": "No messages provided"}),
            status=400,
            mimetype="application/json",
        )

    question = messages[-1].get("content", "").strip()
    if not question:
        return Response(
            json.dumps({"error": "Empty question"}),
            status=400,
            mimetype="application/json",
        )

    conversation_id = (data.get("conversation_id") or "").strip() or None
    container = get_container()
    messages = trim_messages(messages)
    if conversation_id and len(messages) <= 1:
        try:
            history = container.conversations.build_llm_messages(conversation_id)
            if history:
                # 保留当前问题，前面拼接历史（去重最后一轮 user）
                if history and history[-1].get("role") == "user":
                    if history[-1].get("content", "").strip() == question:
                        history = history[:-1]
                messages = history + [{"role": "user", "content": question}]
        except Exception as e:
            log.warning("[ask/stream] 加载会话历史失败 conversation_id=%s: %s", conversation_id, e)

    log.info(
        "[ask/stream] mode=%s question=%r table=%r",
        mode,
        question[:80],
        table_name or "(空)",
    )

    def generate():
        try:
            yield from container.ask.stream_ask(
                question=question,
                table_name=table_name,
                messages=messages,
                mode=mode,
            )
        except Exception as e:
            log.exception("[ask/stream] failed: %s", e)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers=_SSE_HEADERS,
    )
