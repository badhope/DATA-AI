from data_app import DATAApp


def init_app(app: DATAApp):
    import flask_migrate

    from extensions.ext_database import db

    flask_migrate.Migrate(app, db)
