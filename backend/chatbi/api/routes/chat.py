import logging

import pandas as pd
from flask import Blueprint, jsonify, request

from chatbi.api.decorators import requires_session
from chatbi.api.deps import get_container
from chatbi.core.ids import generate_session_id
from chatbi.core.json_util import dataframe_to_records

log = logging.getLogger("chatbi")

chat_bp = Blueprint("chat", __name__, url_prefix="/api")


@chat_bp.route("/run_sql", methods=["POST"])
def run_sql():
    data = request.get_json() or {}
    session_id = data.get("id")
    sql = data.get("sql")
    container = get_container()

    if not sql:
        bucket = container.sessions.get(session_id) if session_id else None
        if not bucket or "sql" not in bucket:
            return jsonify({"error": "No SQL provided"}), 400
        sql = bucket["sql"]

    try:
        df = container.query.run_sql(sql)
        if not session_id:
            session_id = generate_session_id(sql[:50])
        container.sessions.set_fields(session_id, df=df, sql=sql)
        return jsonify({
            "id": session_id,
            "data": dataframe_to_records(df),
            "columns": [str(c) for c in df.columns.tolist()],
            "row_count": len(df),
        })
    except Exception as e:
        log.exception("[run_sql] %s", e)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/generate_plot", methods=["POST"])
@requires_session("df", "question", "sql")
def generate_plot():
    data = request.get_json() or {}
    session_id = data.get("id")
    try:
        fig_json = get_container().enhancement.generate_plot(session_id)
        return jsonify({"id": session_id, "figure": fig_json})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/generate_followup", methods=["POST"])
@requires_session("df", "question", "sql")
def generate_followup():
    data = request.get_json() or {}
    session_id = data.get("id")
    try:
        questions = get_container().enhancement.generate_followup(session_id)
        return jsonify({"id": session_id, "questions": questions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
