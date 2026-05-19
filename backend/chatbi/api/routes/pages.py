from pathlib import Path

from flask import Blueprint, current_app, send_from_directory

pages_bp = Blueprint("pages", __name__)


def _spa_dist_dir() -> Path:
    return Path(current_app.root_path) / "static" / "dist"


def _serve_spa_index():
    dist = _spa_dist_dir()
    index = dist / "index.html"
    if index.is_file():
        return send_from_directory(dist, "index.html")
    # 开发期未 build 时的提示页
    return (
        "<h3>ChatBI 前端未构建</h3>"
        "<p>请在 <code>frontend/</code> 执行：<code>npm install && npm run build</code></p>"
        "<p>或开发模式：<code>cd frontend && npm run dev</code>（端口 5173，已代理 /api）</p>",
        503,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@pages_bp.route("/")
def index():
    return _serve_spa_index()


@pages_bp.route("/<path:asset_path>")
def spa_static(asset_path: str):
    """Vite 构建产物中的 js/css 等资源。"""
    if asset_path.startswith("api/"):
        return {"error": "Not Found"}, 404

    dist = _spa_dist_dir()
    target = dist / asset_path
    if target.is_file():
        return send_from_directory(dist, asset_path)

    # History fallback：未知路径回退 index.html（便于后续 Vue Router）
    return _serve_spa_index()
