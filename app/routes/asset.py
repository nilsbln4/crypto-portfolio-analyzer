import os

from flask import Blueprint, render_template, abort
from flask_login import login_required

from app.models import Asset
from app.services.market_data_service import MarketDataService
from app.services.coingecko_client import CoinGeckoClient

asset_bp = Blueprint('asset', __name__)


@asset_bp.route('/asset/<asset_id>')
@login_required
def analysis(asset_id):
    asset = None
    if asset_id.isdigit():
        from app.extensions import db
        asset = db.session.get(Asset, int(asset_id))
    if not asset:
        asset = Asset.query.filter_by(symbol=asset_id.upper()).first()
    if not asset:
        asset = Asset.query.filter_by(coingecko_id=asset_id).first()
    if not asset:
        abort(404)

    client = CoinGeckoClient(api_key=os.environ.get('COINGECKO_API_KEY', ''))
    market_svc = MarketDataService(client)
    history = market_svc.get_historical_prices(asset.id, days=90)

    prices = [float(row.price) for row in history]
    dates = [row.date.isoformat() for row in history]

    current_price = prices[-1] if prices else None
    market_cap = float(history[-1].market_cap) if history and history[-1].market_cap else None
    volume = float(history[-1].volume) if history and history[-1].volume else None

    vol_proxy = None
    if len(prices) >= 30:
        import statistics
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices)) if prices[i-1] != 0]
        if returns:
            vol_proxy = round(statistics.stdev(returns[-30:]) * (365 ** 0.5) * 100, 2)

    return render_template(
        'asset/analysis.html',
        asset=asset, prices=prices, dates=dates,
        current_price=current_price, market_cap=market_cap,
        volume=volume, vol_proxy=vol_proxy,
    )
