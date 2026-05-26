import logging

from flask import Blueprint, jsonify, request

from chatbi.api.deps import get_container
from chatbi.core.ids import generate_uuid

log = logging.getLogger("chatbi")

conversations_bp = Blueprint("conversations", __name__, url_prefix="/api/conversations")


def _user_id() -> str:
    return (request.args.get("user_id") or request.headers.get("X-User-Id") or "").strip()


def _user_id_from_body(data: dict) -> str:
    return (data.get("user_id") or request.headers.get("X-User-Id") or "").strip()


@conversations_bp.route("", methods=["GET"])
def list_conversations():
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    items = get_container().conversations.list_conversations(user_id)
    return jsonify({"items": items})


@conversations_bp.route("", methods=["POST"])
def create_conversation():
    data = request.get_json() or {}
    user_id = _user_id_from_body(data)
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    conv_id = (data.get("id") or generate_uuid()).strip()
    title = (data.get("title") or "新对话").strip() or "新对话"
    mode = (data.get("mode") or "chatbi").strip().lower()
    if mode not in ("chatbi", "kb"):
        mode = "chatbi"
    table_name = (data.get("table_name") or "").strip()
    try:
        item = get_container().conversations.create_conversation(
            conversation_id=conv_id,
            user_id=user_id,
            title=title,
            mode=mode,
            table_name=table_name,
        )
        return jsonify(item), 201
    except Exception as e:
        log.exception("[conversations/create] %s", e)
        return jsonify({"error": str(e)}), 500


@conversations_bp.route("/<conversation_id>", methods=["GET"])
def get_conversation(conversation_id: str):
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    item = get_container().conversations.get_conversation(conversation_id, user_id=user_id)
    if not item:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify(item)


@conversations_bp.route("/<conversation_id>", methods=["PATCH"])
def update_conversation(conversation_id: str):
    data = request.get_json() or {}
    user_id = _user_id_from_body(data)
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    item = get_container().conversations.update_conversation(
        conversation_id,
        user_id=user_id,
        title=data.get("title"),
        mode=data.get("mode"),
        table_name=data.get("table_name"),
    )
    if not item:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify(item)


@conversations_bp.route("/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id: str):
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    ok = get_container().conversations.delete_conversation(conversation_id, user_id=user_id)
    if not ok:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify({"ok": True})


@conversations_bp.route("/<conversation_id>/messages", methods=["GET"])
def list_messages(conversation_id: str):
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    conv = get_container().conversations.get_conversation(conversation_id, user_id=user_id)
    if not conv:
        return jsonify({"error": "会话不存在"}), 404
    items = get_container().conversations.list_messages(conversation_id)
    return jsonify({"items": items})


@conversations_bp.route("/<conversation_id>/messages", methods=["POST"])
def append_messages(conversation_id: str):
    data = request.get_json() or {}
    user_id = _user_id_from_body(data)
    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    messages = data.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages 不能为空"}), 400
    try:
        items = get_container().conversations.append_messages(
            conversation_id, messages, user_id=user_id
        )
        return jsonify({"items": items}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        log.exception("[conversations/messages] %s", e)
        return jsonify({"error": str(e)}), 500
