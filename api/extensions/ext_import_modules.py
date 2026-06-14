from data_app import DATAApp


def init_app(app: DATAApp):
    from events import event_handlers  # noqa: F401
