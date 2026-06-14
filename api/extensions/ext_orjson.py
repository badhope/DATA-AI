from flask_orjson import OrjsonProvider

from data_app import DATAApp


def init_app(app: DATAApp):
    """Initialize Flask-Orjson extension for faster JSON serialization"""
    app.json = OrjsonProvider(app)
