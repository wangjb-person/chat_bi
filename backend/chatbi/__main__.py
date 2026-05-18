"""支持: cd backend && python -m chatbi"""

import os
import sys

from chatbi.config.settings import get_settings
from chatbi.core.logging import get_logger
from chatbi.main import create_app, ensure_port_free

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app = create_app()
    log = get_logger()
    settings = get_settings()

    log.info("ChatBI 启动 http://127.0.0.1:%d", settings.flask_port)
    ensure_port_free(settings.flask_port)
    app.run(host="0.0.0.0", port=settings.flask_port, debug=False, threaded=True)
