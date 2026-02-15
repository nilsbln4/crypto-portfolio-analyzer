import logging

import bcrypt

from app.extensions import db
from app.models import User, Transaction, AdminAction

logger = logging.getLogger(__name__)


class AdminService:

    @staticmethod
    def list_users():
        return User.query.order_by(User.created_at.desc()).all()

    @staticmethod
    def disable_user(admin_user_id, target_user_id):
        target = db.session.get(User, target_user_id)
        if not target:
            raise ValueError('User not found')
        target.is_active = False
        action = AdminAction(
            admin_user_id=admin_user_id,
            action_type='DISABLE',
            target_user_id=target_user_id,
        )
        db.session.add(action)
        db.session.commit()
        logger.info('Admin %d disabled user %d', admin_user_id, target_user_id)

    @staticmethod
    def enable_user(admin_user_id, target_user_id):
        target = db.session.get(User, target_user_id)
        if not target:
            raise ValueError('User not found')
        target.is_active = True
        action = AdminAction(
            admin_user_id=admin_user_id,
            action_type='ENABLE',
            target_user_id=target_user_id,
        )
        db.session.add(action)
        db.session.commit()
        logger.info('Admin %d enabled user %d', admin_user_id, target_user_id)

    @staticmethod
    def reset_password(admin_user_id, target_user_id, new_password):
        target = db.session.get(User, target_user_id)
        if not target:
            raise ValueError('User not found')
        target.password_hash = bcrypt.hashpw(
            new_password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        action = AdminAction(
            admin_user_id=admin_user_id,
            action_type='RESET_PW',
            target_user_id=target_user_id,
        )
        db.session.add(action)
        db.session.commit()
        logger.info('Admin %d reset password for user %d', admin_user_id, target_user_id)

    @staticmethod
    def get_all_transactions():
        return (
            Transaction.query
            .order_by(Transaction.created_at.desc())
            .all()
        )
