from core.hosting_configuration import HostingConfiguration

hosting_configuration = HostingConfiguration()


from data_app import DATAApp


def init_app(app: DATAApp):
    hosting_configuration.init_app(app)
