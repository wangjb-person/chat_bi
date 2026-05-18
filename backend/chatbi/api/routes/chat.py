import json
import logging
from typing import Any, Dict

import pandas as pd
from flask import Blueprint, Response, jsonify, request

from chatbi.api.decorators import requires_session
from chatbi.api.deps import get_container
from chatbi.core.ids import generate_session_id
from chatbi.core.json_util import dataframe_to_records

log = logging.getLogger("chatbi")

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "close",
    "X-Accel-Buffering": "no",
}


def _query_result_payload(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        "data": dataframe_to_records(df),
        "columns": df.columns.tolist(),
        "row_count": len(df),
    }

chat_bp = Blueprint("chat", __name__, url_prefix="/api")


@chat_bp.route("/generate_sql", methods=["POST"])
def generate_sql():
    data = request.get_json()
    messages = data.get("messages", [])
    table_name = data.get("table_name", "")

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    question = messages[-1]["content"]
    container = get_container()

    try:
        result = container.chat.generate_sql(messages=messages, table_name=table_name)
        session_id = generate_session_id(question)
        container.chat.save_sql_result(
            session_id, question=question, sql=result["sql"]
        )
        return jsonify({
            "id": session_id,
            "sql": result["sql"],
            "full_response": result.get("full_response", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/generate_sql_stream", methods=["POST"])
def generate_sql_stream():
    data = request.get_json()
    messages = data.get("messages", [])
    table_name = data.get("table_name", "")

    question = messages[-1]["content"]
    session_id = generate_session_id(question)
    container = get_container()

    log.info(
        "[generate_sql_stream] 开始 question=%r table=%r id=%s",
        question[:80] + ("..." if len(question) > 80 else ""),
        table_name or "(空)",
        session_id,
    )

    def generate():
        full_response = ""
        try:
            for chunk in container.chat.generate_sql_stream(
                messages=messages, table_name=table_name
            ):
                full_response += chunk
                yield f"data: {json.dumps({'sql': chunk})}\n\n"

            extracted = container.chat.extract_sql(full_response).replace("\\_", "_")
            container.chat.save_sql_result(
                session_id, question=question, sql=extracted
            )

            done_payload: Dict[str, Any] = {
                "done": True,
                "id": session_id,
                "sql": extracted,
            }

            if extracted and extracted.strip():
                try:
                    log.info(
                        "[generate_sql_stream] 同流执行 SQL id=%s sql_len=%d",
                        session_id,
                        len(extracted),
                    )
                    df = container.chat.run_sql(extracted)
                    container.chat.save_query_result(session_id, df)
                    done_payload["query_result"] = _query_result_payload(df)
                    log.info(
                        "[generate_sql_stream] SQL 完成 row_count=%d",
                        len(df),
                    )
                except Exception as run_err:
                    log.exception(
                        "[generate_sql_stream] SQL 执行失败: %s", run_err
                    )
                    done_payload["run_error"] = str(run_err)

            log.info(
                "[generate_sql_stream] 结束 id=%s 提取SQL长度=%d",
                session_id,
                len(extracted or ""),
            )
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        except Exception as e:
            log.exception("[generate_sql_stream] 失败: %s", e)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers=_SSE_HEADERS,
    )


@chat_bp.route("/run_sql", methods=["POST"])
def run_sql():
    data = request.get_json()
    session_id = data.get("id")
    sql = data.get("sql")
    container = get_container()
    sessions = container.sessions

    if not sql:
        bucket = sessions.get(session_id) if session_id else None
        if not bucket or "sql" not in bucket:
            log.warning("[run_sql] 拒绝: 无 SQL 且缓存未命中 id=%s", session_id)
            return jsonify({"error": "No SQL provided"}), 400
        sql = bucket["sql"]

    try:
        log.info("[run_sql] 开始 id=%s sql_len=%d", session_id, len(sql or ""))
        df = container.chat.run_sql(sql)
        log.info("[run_sql] 完成 row_count=%d", len(df))

        if not session_id:
            session_id = generate_session_id(sql[:50])

        container.chat.save_query_result(session_id, df)

        return jsonify({
            "id": session_id,
            **_query_result_payload(df),
        })
    except Exception as e:
        log.exception("[run_sql] 失败: %s", e)
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/generate_plot", methods=["POST"])
@requires_session("df", "question", "sql")
def generate_plot():
    data = request.get_json()
    session_id = data.get("id")

    try:
        fig_json = get_container().chat.generate_plot(session_id)
        return jsonify({"id": session_id, "figure": fig_json})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/generate_followup", methods=["POST"])
@requires_session("df", "question", "sql")
def generate_followup():
    data = request.get_json()
    session_id = data.get("id")

    try:
        questions = get_container().chat.generate_followup(session_id)
        return jsonify({"id": session_id, "questions": questions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/get_cache", methods=["GET"])
def get_cache():
    sessions = get_container().sessions
    return jsonify({
        "cache_keys": sessions.keys(),
        "cache": sessions.debug_snapshot(),
    })
