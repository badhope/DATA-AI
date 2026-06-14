from configs import data_config
from data_app import DATAApp


def init_app(app: DATAApp):
    if data_config.RESPECT_XFORWARD_HEADERS_ENABLED:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_port=1)  # type: ignore[method-assign]
