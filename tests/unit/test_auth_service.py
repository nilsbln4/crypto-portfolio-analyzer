import pytest

from app.extensions import db
from app.models import User
from app.services.auth_service import AuthService, AuthError


class TestRegister:

    def test_creates_user_with_hashed_password(self, app):
        with app.app_context():
            user = AuthService.register('new@example.com', 'securepass123')
            assert user.id is not None
            assert user.email == 'new@example.com'
            assert user.password_hash != 'securepass123'
            assert user.password_hash.startswith('$2b$')

            db.session.delete(user)
            db.session.commit()

    def test_rejects_duplicate_email(self, app):
        with app.app_context():
            user = AuthService.register('dup@example.com', 'securepass123')
            with pytest.raises(AuthError, match='already registered'):
                AuthService.register('dup@example.com', 'otherpass123')

            db.session.delete(user)
            db.session.commit()

    def test_validates_email_format(self, app):
        with app.app_context():
            with pytest.raises(AuthError, match='Invalid email'):
                AuthService.register('not-an-email', 'securepass123')

    def test_validates_password_strength(self, app):
        with app.app_context():
            with pytest.raises(AuthError, match='at least 8'):
                AuthService.register('short@example.com', 'short')

    def test_normalizes_email_to_lowercase(self, app):
        with app.app_context():
            user = AuthService.register('Upper@Example.COM', 'securepass123')
            assert user.email == 'upper@example.com'

            db.session.delete(user)
            db.session.commit()


class TestAuthenticate:

    def test_returns_user_for_valid_credentials(self, app):
        with app.app_context():
            user = AuthService.register('auth@example.com', 'mypassword123')
            result = AuthService.authenticate('auth@example.com', 'mypassword123')
            assert result is not None
            assert result.id == user.id

            db.session.delete(user)
            db.session.commit()

    def test_returns_none_for_wrong_password(self, app):
        with app.app_context():
            user = AuthService.register('wrong@example.com', 'mypassword123')
            result = AuthService.authenticate('wrong@example.com', 'badpassword')
            assert result is None

            db.session.delete(user)
            db.session.commit()

    def test_returns_none_for_unknown_email(self, app):
        with app.app_context():
            result = AuthService.authenticate('nobody@example.com', 'whatever')
            assert result is None

    def test_returns_none_for_disabled_account(self, app):
        with app.app_context():
            user = AuthService.register('disabled@example.com', 'mypassword123')
            user.is_active = False
            db.session.commit()

            result = AuthService.authenticate('disabled@example.com', 'mypassword123')
            assert result is None

            db.session.delete(user)
            db.session.commit()


class TestVerifyPassword:

    def test_returns_true_for_correct_password(self, app):
        with app.app_context():
            user = AuthService.register('verify@example.com', 'correctpass1')
            assert AuthService.verify_password(user, 'correctpass1') is True

            db.session.delete(user)
            db.session.commit()

    def test_returns_false_for_wrong_password(self, app):
        with app.app_context():
            user = AuthService.register('verify2@example.com', 'correctpass1')
            assert AuthService.verify_password(user, 'wrongpass') is False

            db.session.delete(user)
            db.session.commit()
