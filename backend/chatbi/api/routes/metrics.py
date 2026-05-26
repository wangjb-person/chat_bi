from flask import Blueprint, jsonify, request

from chatbi.api.deps import get_container

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


@metrics_bp.route("", methods=["GET"])
def list_metrics():
    items = get_container().metrics.list_metrics()
    return jsonify(
        {
            "metrics": [
                {
                    "code": m.code,
                    "name": m.name,
                    "dataset_id": m.dataset_id,
                    "base_table": m.base_table,
                    "expression": m.expression,
                    "format": m.format,
                    "description": m.description,
                    "synonyms": m.synonyms,
                    "dimensions": m.dimensions,
                    "status": m.status,
                }
                for m in items
            ]
        }
    )


@metrics_bp.route("/<code>", methods=["GET"])
def get_metric(code: str):
    m = get_container().metrics.get_metric(code)
    if not m:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        {
            "code": m.code,
            "name": m.name,
            "dataset_id": m.dataset_id,
            "base_table": m.base_table,
            "expression": m.expression,
            "format": m.format,
            "description": m.description,
            "synonyms": m.synonyms,
            "dimensions": m.dimensions,
            "status": m.status,
        }
    )


@metrics_bp.route("", methods=["POST"])
def upsert_metric():
    data = request.get_json() or {}
    required = ["code", "name", "base_table", "expression"]
    for key in required:
        if not data.get(key):
            return jsonify({"error": f"missing {key}"}), 400
    m = get_container().metrics.upsert(data)
    return jsonify({"ok": True, "code": m.code})


@metrics_bp.route("/<code>", methods=["DELETE"])
def delete_metric(code: str):
    ok = get_container().metrics.delete(code)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@metrics_bp.route("/resolve", methods=["POST"])
def resolve_metric():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "missing question"}), 400
    return jsonify(get_container().metrics.resolve_question(question))
