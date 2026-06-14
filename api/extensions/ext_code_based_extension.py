from core.extension.extension import Extension
from data_app import DATAApp


def init_app(app: DATAApp):
    code_based_extension.init()


code_based_extension = Extension()
