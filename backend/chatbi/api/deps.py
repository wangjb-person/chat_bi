from flask import current_app

from chatbi.services.container import ServiceContainer


def get_container() -> ServiceContainer:
    return current_app.extensions["container"]
