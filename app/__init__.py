import logging
import sys

from flask import Flask
from dotenv import load_dotenv

from app.config import DevelopmentConfig, ProductionConfig
from app.extensions import db, login_manager, csrf


def _configure_logging(app):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    handler.setLevel(logging.INFO)

    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    for name in ('app.services', 'app.routes'):
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def create_app(config_class=None):
    load_dotenv()

    app = Flask(__name__)

    if config_class is None:
        import os
        if os.environ.get('FLASK_ENV') == 'production':
            config_class = ProductionConfig
        else:
            config_class = DevelopmentConfig
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    if not app.config.get('TESTING'):
        _configure_logging(app)

    from app import models  # noqa: F401 — register models with SQLAlchemy
    from app import seeds
    seeds.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return db.session.get(User, int(user_id))

    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.portfolio import portfolio_bp
    from app.routes.asset import asset_bp
    from app.routes.history import history_bp
    from app.routes.reporting import reporting_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(asset_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(admin_bp)

    return app
