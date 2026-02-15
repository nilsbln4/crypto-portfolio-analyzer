from flask import Flask

from app import create_app
from app.config import TestConfig


def test_app_factory_creates_app():
    app = create_app(config_class=TestConfig)
    assert isinstance(app, Flask)


def test_app_is_testing():
    app = create_app(config_class=TestConfig)
    assert app.config['TESTING'] is True


def test_app_uses_sqlite_in_test():
    app = create_app(config_class=TestConfig)
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://'
