from data_app import DATAApp


def init_app(app: DATAApp):
    import warnings

    warnings.simplefilter("ignore", ResourceWarning)
