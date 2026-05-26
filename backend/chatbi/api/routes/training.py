"""
语料训练 API：向 Chroma 写入 question-SQL / DDL / 文档 / 通用规则。

DDL 变更后会刷新 SchemaContextCache，供意图路由使用最新表结构。
"""

from flask import Blueprint, jsonify, request

from chatbi.api.deps import get_container
from chatbi.core.json_util import dataframe_to_records

training_bp = Blueprint("training", __name__, url_prefix="/api")


def _refresh_ddl_cache_if_needed(doc_id: str) -> None:
    """DDL 语料变更后重建意图用的 schema 缓存。"""
    if doc_id and str(doc_id).endswith("-ddl"):
        get_container().refresh_ddl_cache()


@training_bp.route("/train", methods=["POST"])
def train():
    """新增一条训练语料（四选一：question+sql / ddl / documentation / general）。"""
    data = request.get_json()
    service = get_container().training

    try:
        if "question" in data and "sql" in data:
            doc_id = service.add(
                question=data["question"],
                sql=data["sql"],
                table_name=data.get("table_name", ""),
            )
        elif "ddl" in data:
            doc_id = service.add(
                ddl=data["ddl"],
                table_name=data.get("table_name", ""),
            )
            _refresh_ddl_cache_if_needed(doc_id)
        elif "documentation" in data:
            doc_id = service.add(
                documentation=data["documentation"],
                table_name=data.get("table_name", ""),
            )
        elif "general" in data:
            doc_id = service.add(
                general=data["general"],
                gen_type=data.get("gen_type", ""),
            )
        else:
            return jsonify({"error": "Invalid training data"}), 400

        return jsonify({"id": doc_id, "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/get_training_data", methods=["GET"])
def get_training_data():
    try:
        df = get_container().training.list_all()
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        start = (page - 1) * page_size
        end = start + page_size
        total = len(df)
        paginated = dataframe_to_records(df.iloc[start:end], limit=page_size)
        return jsonify({
            "data": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/search_training_data", methods=["POST"])
def search_training_data():
    data = request.get_json()
    try:
        result = get_container().training.search(
            keyword=data.get("keyword"),
            data_type=data.get("data_type"),
            table_name=data.get("table_name"),
            gen_type=data.get("gen_type"),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/remove_training_data", methods=["POST"])
def remove_training_data():
    data = request.get_json()
    doc_id = data.get("id")
    if not doc_id:
        return jsonify({"error": "No id provided"}), 400

    container = get_container()
    if container.training.remove(doc_id):
        _refresh_ddl_cache_if_needed(doc_id)
        return jsonify({"success": True})
    return jsonify({"error": "Failed to remove"}), 500


@training_bp.route("/update_training_data", methods=["POST"])
def update_training_data():
    data = request.get_json()
    try:
        result = get_container().training.update(
            doc_id=data.get("id"),
            new_content=data.get("new_content"),
            new_question=data.get("new_question"),
            new_gen_type=data.get("new_gen_type"),
            table_name=data.get("table_name", ""),
        )
        if result["success"]:
            _refresh_ddl_cache_if_needed(str(data.get("id") or ""))
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/generate_example_questions", methods=["POST"])
def generate_example_questions():
    data = request.get_json()
    table_name = data.get("table_name", "")

    try:
        questions = get_container().training.generate_example_questions(
            table_name=table_name
        )
        return jsonify({"questions": questions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
