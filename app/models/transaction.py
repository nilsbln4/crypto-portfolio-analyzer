from datetime import datetime, timezone

from app.extensions import db


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    version_id = db.Column(
        db.Integer, db.ForeignKey('portfolio_versions.id'), nullable=True
    )
    type = db.Column(db.String(10), nullable=False)
    diff_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship('User', backref='transactions')
    portfolio = db.relationship('Portfolio', backref='transactions')


class AdminAction(db.Model):
    __tablename__ = 'admin_actions'

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )
    action_type = db.Column(db.String(20), nullable=False)
    target_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    admin = db.relationship('User', foreign_keys=[admin_user_id])
    target = db.relationship('User', foreign_keys=[target_user_id])
