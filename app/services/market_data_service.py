import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.models.asset import Asset
from app.models.market_data import MarketDataDaily
from app.services.coingecko_client import CoinGeckoClient, CoinGeckoClientError

logger = logging.getLogger(__name__)

STALENESS_HOURS = 24


class MarketDataService:
    """Cache-aware market data fetching. Decides when to call API vs. serve from DB."""

    def __init__(self, coingecko_client):
        self._client = coingecko_client

    def get_current_prices(self, asset_ids):
        """Return {asset_id: Decimal(price)} for given asset IDs, using cache or API."""
        assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
        if not assets:
            return {}

        result = {}
        stale_assets = []
        cutoff_date = date.today() - timedelta(days=1)

        for asset in assets:
            latest = (
                MarketDataDaily.query
                .filter_by(asset_id=asset.id)
                .order_by(MarketDataDaily.date.desc())
                .first()
            )
            if latest and latest.date >= cutoff_date:
                result[asset.id] = latest.price
            else:
                stale_assets.append(asset)

        if stale_assets:
            try:
                self._fetch_and_cache_current(stale_assets)
                for asset in stale_assets:
                    latest = (
                        MarketDataDaily.query
                        .filter_by(asset_id=asset.id)
                        .order_by(MarketDataDaily.date.desc())
                        .first()
                    )
                    if latest:
                        result[asset.id] = latest.price
            except CoinGeckoClientError:
                logger.warning('API failed, falling back to stale cache')
                for asset in stale_assets:
                    latest = (
                        MarketDataDaily.query
                        .filter_by(asset_id=asset.id)
                        .order_by(MarketDataDaily.date.desc())
                        .first()
                    )
                    if latest:
                        result[asset.id] = latest.price

        return result

    def get_historical_prices(self, asset_id, days=90):
        """Return list of MarketDataDaily for the asset, fetching from API if missing."""
        cutoff_date = date.today() - timedelta(days=days)
        cached = (
            MarketDataDaily.query
            .filter(
                MarketDataDaily.asset_id == asset_id,
                MarketDataDaily.date >= cutoff_date,
            )
            .order_by(MarketDataDaily.date.asc())
            .all()
        )

        expected_days = (date.today() - cutoff_date).days
        if len(cached) >= expected_days * 0.8:
            return cached

        asset = db.session.get(Asset, asset_id)
        if not asset:
            return cached

        try:
            data = self._client.get_market_chart(asset.coingecko_id, days=days)
            self._save_market_chart(asset.id, data)
            return (
                MarketDataDaily.query
                .filter(
                    MarketDataDaily.asset_id == asset_id,
                    MarketDataDaily.date >= cutoff_date,
                )
                .order_by(MarketDataDaily.date.asc())
                .all()
            )
        except CoinGeckoClientError:
            logger.warning('API failed for historical data, returning cached')
            return cached

    def refresh_all_market_data(self):
        """Batch-refresh current prices for all assets. Returns count of updated records."""
        assets = Asset.query.all()
        if not assets:
            return 0
        try:
            return self._fetch_and_cache_current(assets)
        except CoinGeckoClientError:
            logger.error('Failed to refresh market data')
            return 0

    def _fetch_and_cache_current(self, assets):
        coin_ids = [a.coingecko_id for a in assets]
        id_map = {a.coingecko_id: a.id for a in assets}
        market_data = self._client.get_coin_markets(coin_ids)
        today = date.today()
        count = 0

        for coin in market_data:
            asset_id = id_map.get(coin['id'])
            if asset_id is None:
                continue

            existing = MarketDataDaily.query.filter_by(
                asset_id=asset_id, date=today
            ).first()

            raw_price = coin.get('current_price')
            if raw_price is None:
                continue
            price = Decimal(str(raw_price))
            market_cap = Decimal(str(coin.get('market_cap') or 0))
            volume = Decimal(str(coin.get('total_volume') or 0))

            if existing:
                existing.price = price
                existing.market_cap = market_cap
                existing.volume = volume
            else:
                md = MarketDataDaily(
                    asset_id=asset_id, date=today,
                    price=price, market_cap=market_cap, volume=volume,
                )
                db.session.add(md)
            count += 1

        db.session.commit()
        return count

    def _save_market_chart(self, asset_id, data):
        prices = data.get('prices', [])
        market_caps = data.get('market_caps', [])
        total_volumes = data.get('total_volumes', [])

        caps_dict = {int(ts): val for ts, val in market_caps}
        vols_dict = {int(ts): val for ts, val in total_volumes}

        for ts, price in prices:
            ts_int = int(ts)
            d = datetime.fromtimestamp(ts_int / 1000, tz=timezone.utc).date()

            existing = MarketDataDaily.query.filter_by(
                asset_id=asset_id, date=d
            ).first()
            if existing:
                continue

            md = MarketDataDaily(
                asset_id=asset_id, date=d,
                price=Decimal(str(price)),
                market_cap=Decimal(str(caps_dict.get(ts_int, 0))),
                volume=Decimal(str(vols_dict.get(ts_int, 0))),
            )
            db.session.add(md)

        db.session.commit()
