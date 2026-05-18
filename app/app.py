import json
import sys
import traceback
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, Response, request, send_from_directory
import pandas as pd

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent))

from chroma_vector import ChromaVectorStore
from my_vanna import VannaChroma
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__, static_folder='templates', static_url_path='')

# ==================== 配置 ====================
CONFIG = {
    # OpenAI 配置
    "api_key": os.getenv("OPENAI_API_KEY", "sk-bbcf40088d034f8dafff1597f585e1ff"),
    "base_url": os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "model": os.getenv("LLM_MODEL", "qwen-plus"),
    "initial_prompt": "你是一位MySQL数据库专家。",

    # ChromaDB 配置
    "persist_directory": os.getenv("CHROMA_DB_PATH", "./chroma_db"),
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",

    # MySQL 配置
    "mysql": {
        # Windows 下 localhost 常解析到 ::1，若 mysqld 只监听 127.0.0.1 会导致连接长时间挂起；可设 MYSQL_HOST=localhost 覆盖
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", 3306)),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "12345678"),
        "database": os.getenv("MYSQL_DATABASE", "testDatabase")
    }
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

@app.route('/')
def root():
    """首页"""
    return send_from_directory('templates', 'index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


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

            yield f"data: {json.dumps({'done': True, 'id': id, 'sql': extracted})}\n\n"
        except Exception as e:
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
            return jsonify({"error": "No SQL provided"}), 400
        sql = cache[id]['sql']

    try:
        print(f"[api/run_sql] 开始 id={id} sql_len={len(sql or '')}", flush=True)
        df = vn.run_sql(sql)
        print(f"[api/run_sql] 查询完成 row_count={len(df)}，准备返回 JSON", flush=True)

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


if __name__ == "__main__":
    print("=" * 50)
    print("ChatBI Demo 启动中...")
    print(f"MySQL: {CONFIG['mysql']['host']}:{CONFIG['mysql']['port']}/{CONFIG['mysql']['database']}")
    print(f"ChromaDB 路径: {CONFIG['persist_directory']}")
    print(f"LLM 模型: {CONFIG['model']}")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)