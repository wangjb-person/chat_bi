"""知识库文档维护 API（与语料训练 / 问数隔离）。"""

from __future__ import annotations

from typing import Any, Callable, Tuple

from flask import Blueprint, Response, jsonify, request

from chatbi.api.deps import get_container

kb_bp = Blueprint("kb", __name__, url_prefix="/api/kb")


def _json_error(message: str, status: int) -> Tuple[Response, int]:
    """统一错误响应。"""
    return jsonify({"error": message}), status


def _handle_ingest(action: Callable[[], Any]) -> Tuple[Response, int]:
    """捕获入库过程中的 ValueError。"""
    try:
        return jsonify(action()), 201
    except ValueError as e:
        return _json_error(str(e), 400)


@kb_bp.route("/documents", methods=["GET"])
def list_documents() -> Response:
    """列出已入库文档。"""
    return jsonify({"documents": get_container().kb.list_documents()})


@kb_bp.route("/documents", methods=["POST"])
def create_document() -> Tuple[Response, int]:
    """上传文件或 JSON 粘贴文本入库。"""
    content_type = request.content_type or ""
    if "multipart/form-data" in content_type:
        return _create_from_upload()
    return _create_from_json()


def _create_from_upload() -> Tuple[Response, int]:
    """multipart 文件上传。"""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return _json_error("请上传文件", 400)
    title = (request.form.get("title") or "").strip()
    kb = get_container().kb
    return _handle_ingest(
        lambda: kb.ingest_upload(
            title=title,
            raw_bytes=upload.read(),
            original_filename=upload.filename,
        )
    )


def _create_from_json() -> Tuple[Response, int]:
    """JSON 粘贴正文入库。"""
    data = request.get_json() or {}
    content = (data.get("content") or "").strip()
    if not content:
        return _json_error("content 不能为空", 400)
    title = (data.get("title") or "").strip() or "未命名文档"
    kb = get_container().kb
    return _handle_ingest(
        lambda: kb.ingest_text(
            title=title,
            content=content,
            filename=data.get("filename") or "paste.txt",
        )
    )


@kb_bp.route("/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id: str) -> Tuple[Response, int]:
    """删除指定文档。"""
    if not get_container().kb.delete_document(doc_id):
        return _json_error("文档不存在", 404)
    return jsonify({"ok": True}), 200
