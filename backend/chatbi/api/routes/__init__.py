from flask import Flask

from chatbi.api.routes.ask import ask_bp
from chatbi.api.routes.chat import chat_bp
from chatbi.api.routes.conversations import conversations_bp
from chatbi.api.routes.health import health_bp
from chatbi.api.routes.metrics import metrics_bp
from chatbi.api.routes.pages import pages_bp
from chatbi.api.routes.kb import kb_bp
from chatbi.api.routes.training import training_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(pages_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(ask_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(kb_bp)
