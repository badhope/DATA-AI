from configs import data_config
from data_app import DATAApp


def is_enabled() -> bool:
    return data_config.API_COMPRESSION_ENABLED


def init_app(app: DATAApp):
    from flask_compress import Compress

    compress = Compress()
    compress.init_app(app)
