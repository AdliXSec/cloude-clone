"""App factory KosanHub."""
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        from kosanhub.config import Config

        config_class = Config
    app.config.from_object(config_class)
    app.json.sort_keys = False

    db.init_app(app)
    migrate.init_app(app, db, directory="migrations")

    from kosanhub import models  # noqa: F401  (daftarkan model ke metadata)
    from kosanhub.errors import register_error_handlers
    from kosanhub.routes import register_blueprints

    register_error_handlers(app)
    register_blueprints(app)

    from kosanhub.seeder import register_cli

    register_cli(app)
    return app
