from datetime import datetime, timezone

from app.extensions import db


class RiskSnapshot(db.Model):
    __tablename__ = 'risk_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(
        db.Integer, db.ForeignKey('portfolio_versions.id'), nullable=False
    )
    computed_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    metrics_json = db.Column(db.JSON, nullable=False)
