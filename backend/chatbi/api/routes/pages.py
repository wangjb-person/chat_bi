from flask import Blueprint, send_from_directory

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def root():
    return send_from_directory("templates", "index.html")
