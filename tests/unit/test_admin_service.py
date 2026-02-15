import pytest

from app.extensions import db
from app.models import User, AdminAction
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService


@pytest.fixture
def admin_and_target(app, request):
    with app.app_context():
        admin = AuthService.register(f'admin_{request.node.name}@test.com', 'adminpass1')
        admin.role = 'ADMIN'
        db.session.commit()

        target = AuthService.register(f'target_{request.node.name}@test.com', 'targetpass1')
        yield admin, target


class TestAdminService:

    def test_list_users_returns_all(self, app, admin_and_target):
        with app.app_context():
            users = AdminService.list_users()
            assert len(users) >= 2

    def test_disable_user_sets_inactive(self, app, admin_and_target):
        with app.app_context():
            admin, target = admin_and_target
            AdminService.disable_user(admin.id, target.id)
            refreshed = db.session.get(User, target.id)
            assert refreshed.is_active is False

    def test_disabled_user_cannot_login(self, app, admin_and_target):
        with app.app_context():
            admin, target = admin_and_target
            AdminService.disable_user(admin.id, target.id)
            result = AuthService.authenticate(target.email, 'targetpass1')
            assert result is None

    def test_reset_password_changes_hash(self, app, admin_and_target):
        with app.app_context():
            admin, target = admin_and_target
            old_hash = target.password_hash
            AdminService.reset_password(admin.id, target.id, 'newpassword123')
            refreshed = db.session.get(User, target.id)
            assert refreshed.password_hash != old_hash

    def test_admin_action_is_logged(self, app, admin_and_target):
        with app.app_context():
            admin, target = admin_and_target
            AdminService.disable_user(admin.id, target.id)
            action = AdminAction.query.filter_by(
                admin_user_id=admin.id, target_user_id=target.id,
            ).first()
            assert action is not None
            assert action.action_type == 'DISABLE'
