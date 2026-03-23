"""Flask application factory."""

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or "app.config.Config")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    from .auth import auth_bp
    from .dashboard import dashboard_bp
    from .integrations import integrations_bp
    from .logs import logs_bp
    from .stats import stats_bp
    from .setup import setup_bp
    from .settings import settings_bp
    from .admin import admin_bp, init_admin_cli

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(integrations_bp, url_prefix="/integrations")
    app.register_blueprint(logs_bp, url_prefix="/logs")
    app.register_blueprint(stats_bp, url_prefix="/stats")
    app.register_blueprint(setup_bp, url_prefix="/setup")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    init_admin_cli(app)

    with app.app_context():
        db.create_all()

    return app
