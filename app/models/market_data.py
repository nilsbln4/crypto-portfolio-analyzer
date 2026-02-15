from app.extensions import db


class MarketDataDaily(db.Model):
    __tablename__ = 'market_data_daily'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    price = db.Column(db.Numeric(20, 8), nullable=False)
    market_cap = db.Column(db.Numeric(24, 2), nullable=True)
    volume = db.Column(db.Numeric(24, 2), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('asset_id', 'date', name='uq_asset_date'),
    )
