from datetime import datetime, timezone

from app.extensions import db


class Portfolio(db.Model):
    __tablename__ = 'portfolios'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    versions = db.relationship(
        'PortfolioVersion',
        backref='portfolio',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )


class PortfolioVersion(db.Model):
    __tablename__ = 'portfolio_versions'

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(
        db.Integer, db.ForeignKey('portfolios.id'), nullable=False
    )
    version_num = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    holdings = db.relationship(
        'PortfolioHolding',
        backref='version',
        lazy='joined',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint('portfolio_id', 'version_num', name='uq_portfolio_version'),
    )


class PortfolioHolding(db.Model):
    __tablename__ = 'portfolio_holdings'

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(
        db.Integer, db.ForeignKey('portfolio_versions.id'), nullable=False
    )
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    weight_pct = db.Column(db.Numeric(6, 3), nullable=False)

    asset = db.relationship('Asset', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('version_id', 'asset_id', name='uq_version_asset'),
        db.CheckConstraint('weight_pct >= 0 AND weight_pct <= 100', name='ck_weight_range'),
    )
