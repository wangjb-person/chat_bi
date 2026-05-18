import logging
import socket

from flask import Flask, request

from chatbi.api.routes import register_blueprints
from chatbi.config.settings import Settings, get_settings
from chatbi.core.logging import setup_logging
from chatbi.services.container import build_container

log = logging.getLogger("chatbi")


def create_app(settings: Settings | None = None) -> Flask:
    """应用工厂：组装配置、依赖容器与 API 蓝图。"""
    setup_logging()
    settings = settings or get_settings()
    backend_root = settings.backend_root

    app = Flask(
        __name__,
        static_folder=str(backend_root / "templates"),
        static_url_path="",
        template_folder=str(backend_root / "templates"),
        root_path=str(backend_root),
    )
    app.extensions["container"] = build_container(settings)

    register_blueprints(app)

    @app.before_request
    def log_incoming_api():
        if request.path.startswith("/api/"):
            log.info(">>> %s %s", request.method, request.path)

    return app


def ensure_port_free(port: int) -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("0.0.0.0", port))
    except OSError:
        log.error("=" * 50)
        log.error("端口 %d 已被占用！本终端无法接收浏览器请求。", port)
        log.error("请执行: netstat -ano | findstr :%d", port)
        log.error("然后结束占用进程: taskkill /PID <pid> /F")
        log.error("再只启动一个: python run.py")
        log.error("=" * 50)
        raise SystemExit(1)
    finally:
        probe.close()
