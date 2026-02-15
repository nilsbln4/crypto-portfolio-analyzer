import re
import logging

import bcrypt

from app.extensions import db
from app.models.user import User

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    pass


class AuthService:

    @staticmethod
    def register(email, password):
        email = email.strip().lower()

        if not EMAIL_REGEX.match(email):
            raise AuthError('Invalid email format')

        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f'Password must be at least {MIN_PASSWORD_LENGTH} characters')

        if User.query.filter_by(email=email).first():
            raise AuthError('Email already registered')

        password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

        user = User(email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()

        logger.info('User registered: %s', email)
        return user

    @staticmethod
    def authenticate(email, password):
        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user:
            return None

        if not user.is_active:
            return None

        if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return user

        return None

    @staticmethod
    def verify_password(user, password):
        return bcrypt.checkpw(
            password.encode('utf-8'),
            user.password_hash.encode('utf-8'),
        )
