import json
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Optional
from functools import wraps
from flask import Flask, jsonify, Response, request, send_from_directory
import pandas as pd

# 统一 API 日志（PyCharm / 终端均输出到 stdout，避免“没日志”的误解）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [chatbi] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger("chatbi")

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent))

from chroma_vector import ChromaVectorStore
from my_vanna import VannaChroma
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _env(key: str, default: Optional[str] = None, *, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise RuntimeError(
            f"缺少环境变量 {key}，请在项目根目录 .env 中配置"
        )
    return value


app = Flask(__name__, static_folder='templates', static_url_path='')

# ==================== 配置 ====================
CONFIG = {
    # OpenAI 配置
    "api_key": _env("OPENAI_API_KEY", required=True),
    "base_url": _env("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "model": _env("LLM_MODEL", "qwen-plus"),
    "initial_prompt": "你是一位MySQL数据库专家。",

    # ChromaDB 配置
    "persist_directory": _env("CHROMA_DB_PATH", "./chroma_db"),
    "embedding_model": _env("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
    "model_cache_dir": _env("MODEL_CACHE_DIR", "./model_cache"),

    # MySQL 配置
    "mysql": {
        # Windows 下 localhost 常解析到 ::1，若 mysqld 只监听 127.0.0.1 会导致连接长时间挂起；可设 MYSQL_HOST=localhost 覆盖
        "host": _env("MYSQL_HOST", "127.0.0.1"),
        "port": int(_env("MYSQL_PORT", "3306")),
        "user": _env("MYSQL_USER", "root"),
        "password": _env("MYSQL_PASSWORD", required=True),
        "database": _env("MYSQL_DATABASE", "testDatabase"),
    },
}

# 初始化 Vanna 实例
vn = VannaChroma(config=CONFIG)

# 缓存（简单内存缓存）
cache = {}


def generate_id(question: str) -> str:
    """生成缓存ID"""
    import hashlib
    return hashlib.md5(question.encode()).hexdigest()


def requires_cache(fields):
    """缓存检查装饰器"""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            request_data = request.get_json(silent=True)

            if not request_data:
                return jsonify({"error": "Invalid JSON format"}), 400

            id = request_data.get('id')

            if not id:
                return jsonify({"error": "Missing id"}), 400

            for field in fields:
                if id not in cache or field not in cache[id]:
                    return jsonify({"error": f"No {field} found in cache"}), 400

            return f(*args, **kwargs)

        return decorated

    return decorator


# ==================== API 路由 ====================

@app.before_request
def _log_incoming_api():
    """记录所有 /api 请求，便于确认浏览器是否打到当前 Flask 进程。"""
    if request.path.startswith("/api/"):
        log.info(">>> %s %s", request.method, request.path)


@app.route('/')
def root():
    """首页"""
    return send_from_directory('templates', 'index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


@app.route('/api/ping', methods=['GET'])
def ping():
    """健康检查（含进程号，用于确认浏览器连的是当前终端这一个 Flask）"""
    return jsonify({
        "status": "ok",
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    })


@app.route('/api/train', methods=['POST'])
def train():
    """
    添加训练数据
    支持类型: question+sql, ddl, documentation, general
    """
    data = request.get_json()

    try:
        if 'question' in data and 'sql' in data:
            id = vn.train(
                question=data['question'],
                sql=data['sql'],
                table_name=data.get('table_name', '')
            )
        elif 'ddl' in data:
            id = vn.train(
                ddl=data['ddl'],
                table_name=data.get('table_name', '')
            )
        elif 'documentation' in data:
            id = vn.train(
                documentation=data['documentation'],
                table_name=data.get('table_name', '')
            )
        elif 'general' in data:
            id = vn.train(
                general=data['general'],
                gen_type=data.get('gen_type', '')
            )
        else:
            return jsonify({"error": "Invalid training data"}), 400

        return jsonify({"id": id, "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate_sql', methods=['POST'])
def generate_sql():
    """生成 SQL"""
    data = request.get_json()
    messages = data.get('messages', [])
    table_name = data.get('table_name', '')

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    question = messages[-1]["content"]

    try:
        result = vn.generate_sql(messages=messages, table_name=table_name)

        id = generate_id(question)

        # 缓存结果
        if id not in cache:
            cache[id] = {}
        cache[id]['sql'] = result['sql']
        cache[id]['question'] = question

        return jsonify({
            "id": id,
            "sql": result['sql'],
            "full_response": result.get('full_response', '')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate_sql_stream', methods=['POST'])
def generate_sql_stream():
    """流式生成 SQL"""
    data = request.get_json()
    messages = data.get('messages', [])
    table_name = data.get('table_name', '')

    question = messages[-1]["content"]
    id = generate_id(question)
    log.info(
        "[generate_sql_stream] 开始 question=%r table=%r id=%s",
        question[:80] + ("..." if len(question) > 80 else ""),
        table_name or "(空)",
        id,
    )

    def generate():
        full_sql = ""
        try:
            for chunk in vn.generate_sql_stream(messages=messages, table_name=table_name):
                full_sql += chunk
                yield f"data: {json.dumps({'sql': chunk})}\n\n"

            # 与 /api/generate_sql 一致：从完整 LLM 输出中提取可执行 SQL（去掉说明与 markdown）
            extracted = vn.extract_sql(full_sql).replace("\\_", "_")

            if id not in cache:
                cache[id] = {}
            cache[id]['sql'] = extracted
            cache[id]['question'] = question

            log.info(
                "[generate_sql_stream] 结束 id=%s 提取SQL长度=%d",
                id,
                len(extracted or ""),
            )
            yield f"data: {json.dumps({'done': True, 'id': id, 'sql': extracted})}\n\n"
        except Exception as e:
            log.exception("[generate_sql_stream] 失败: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/run_sql', methods=['POST'])
def run_sql():
    """执行 SQL"""
    data = request.get_json()
    id = data.get('id')
    sql = data.get('sql')

    if not sql:
        # 从缓存获取
        if not id or id not in cache or 'sql' not in cache[id]:
            log.warning("[run_sql] 拒绝: 无 SQL 且缓存未命中 id=%s", id)
            return jsonify({"error": "No SQL provided"}), 400
        sql = cache[id]['sql']

    try:
        log.info("[run_sql] 开始 id=%s sql_len=%d", id, len(sql or ""))
        df = vn.run_sql(sql)
        log.info("[run_sql] 完成 row_count=%d", len(df))

        if not id:
            id = generate_id(sql[:50])

        # 缓存结果
        if id not in cache:
            cache[id] = {}
        cache[id]['df'] = df

        return jsonify({
            "id": id,
            "data": df.head(500).to_dict(orient='records'),
            "columns": df.columns.tolist(),
            "row_count": len(df)
        })
    except Exception as e:
        log.exception("[run_sql] 失败: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate_plot', methods=['POST'])
@requires_cache(['df', 'question', 'sql'])
def generate_plot():
    """生成图表"""
    data = request.get_json()
    id = data.get('id')

    df = cache[id]['df']
    question = cache[id]['question']
    sql = cache[id]['sql']

    try:
        code = vn.generate_plotly_code(
            question=question,
            sql=sql,
            df_metadata=f"DataFrame columns: {list(df.columns)}\nData types: {df.dtypes.to_dict()}\nFirst few rows:\n{df.head().to_string()}"
        )

        fig = vn.get_plotly_figure(plotly_code=code, df=df)
        fig_json = fig.to_json()

        cache[id]['fig'] = fig_json

        return jsonify({
            "id": id,
            "figure": fig_json
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate_followup', methods=['POST'])
@requires_cache(['df', 'question', 'sql'])
def generate_followup():
    """生成后续问题"""
    data = request.get_json()
    id = data.get('id')

    df = cache[id]['df']
    question = cache[id]['question']
    sql = cache[id]['sql']

    try:
        questions = vn.generate_followup_questions(
            question=question,
            sql=sql,
            df=df,
            n_questions=5
        )

        cache[id]['followup'] = questions

        return jsonify({
            "id": id,
            "questions": questions
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/get_training_data', methods=['GET'])
def get_training_data():
    """获取所有训练数据"""
    try:
        df = vn.get_all_training_data()

        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        start = (page - 1) * page_size
        end = start + page_size

        total = len(df)
        paginated = df.iloc[start:end].to_dict(orient='records')

        return jsonify({
            "data": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/search_training_data', methods=['POST'])
def search_training_data():
    """搜索训练数据"""
    data = request.get_json()

    try:
        result = vn.fuzzy_search(
            keyword=data.get('keyword'),
            data_type=data.get('data_type'),
            table_name=data.get('table_name'),
            gen_type=data.get('gen_type')
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/remove_training_data', methods=['POST'])
def remove_training_data():
    """删除训练数据"""
    data = request.get_json()
    id = data.get('id')

    if not id:
        return jsonify({"error": "No id provided"}), 400

    if vn.remove_training_data(id):
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to remove"}), 500


@app.route('/api/update_training_data', methods=['POST'])
def update_training_data():
    """更新训练数据"""
    data = request.get_json()

    try:
        result = vn.update_training_data(
            id=data.get('id'),
            new_content=data.get('new_content'),
            new_question=data.get('new_question'),
            new_gen_type=data.get('new_gen_type'),
            table_name=data.get('table_name', '')
        )

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate_example_questions', methods=['POST'])
def generate_example_questions():
    """生成示例问题"""
    data = request.get_json()
    table_name = data.get('table_name', '')

    try:
        questions = vn.generate_questions(table_name=table_name)
        return jsonify({"questions": questions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/get_cache', methods=['GET'])
def get_cache():
    """查看缓存（调试用）"""
    return jsonify({
        "cache_keys": list(cache.keys()),
        "cache": {k: {kk: str(vv)[:100] for kk, vv in v.items()} for k, v in cache.items()}
    })


def _ensure_port_free(port: int) -> None:
    """启动前检测端口，避免多个 Flask 同时监听 5000 导致浏览器连错进程、终端无日志。"""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("0.0.0.0", port))
    except OSError:
        log.error("=" * 50)
        log.error("端口 %d 已被占用！本终端无法接收浏览器请求。", port)
        log.error("请执行: netstat -ano | findstr :%d", port)
        log.error("然后结束所有占用该端口的 python: taskkill /PID <pid> /F")
        log.error("再只启动一个: cd app && python app.py")
        log.error("=" * 50)
        raise SystemExit(1)
    finally:
        probe.close()


if __name__ == "__main__":
    port = int(_env("FLASK_PORT", "5000"))

    log.info("=" * 50)
    log.info("ChatBI Demo 启动 (pid=%s cwd=%s)", os.getpid(), os.getcwd())
    log.info("MySQL: %s:%s/%s", CONFIG['mysql']['host'], CONFIG['mysql']['port'], CONFIG['mysql']['database'])
    log.info("ChromaDB: %s", CONFIG['persist_directory'])
    log.info("LLM: %s", CONFIG['model'])
    log.info("浏览器请打开: http://127.0.0.1:%d  （页头应显示 pid=%s）", port, os.getpid())
    log.info("提问后应依次看到: >>> POST /api/generate_sql_stream -> [run_sql]")
    log.info("=" * 50)

    _ensure_port_free(port)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)