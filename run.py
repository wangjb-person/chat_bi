#!/usr/bin/env python3
"""
ChatBI 启动入口。

用法（在仓库根目录 chat_bi/ 下）:
    python run.py

等价于:
    cd backend && python -m chatbi
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 将 backend 加入模块搜索路径，使 import chatbi 生效
_BACKEND = Path(__file__).resolve().parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.chdir(_BACKEND)

from chatbi.config.settings import get_settings  # noqa: E402
from chatbi.core.logging import get_logger  # noqa: E402
from chatbi.main import create_app, ensure_port_free  # noqa: E402

app = create_app()

if __name__ == "__main__":
    log = get_logger()
    settings = get_settings()

    log.info("=" * 50)
    log.info("ChatBI 启动 (pid=%s cwd=%s)", os.getpid(), os.getcwd())
    log.info(
        "MySQL: %s:%s/%s",
        settings.mysql.host,
        settings.mysql.port,
        settings.mysql.database,
    )
    log.info("ChromaDB: %s", settings.persist_directory)
    log.info("LLM: %s", settings.model)
    log.info("API 服务: http://127.0.0.1:%d", settings.flask_port)
    log.info("生产 UI: 先 cd frontend && npm run build，再访问上述地址")
    log.info("开发 UI: cd frontend && npm run dev  → http://127.0.0.1:5173")
    log.info("=" * 50)

    ensure_port_free(settings.flask_port)
    app.run(host="0.0.0.0", port=settings.flask_port, debug=False, threaded=True)
