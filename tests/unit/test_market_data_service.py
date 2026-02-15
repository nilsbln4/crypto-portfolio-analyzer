from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.extensions import db
from app.models import Asset, MarketDataDaily
from app.services.market_data_service import MarketDataService
from app.services.coingecko_client import CoinGeckoClientError


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def service(mock_client):
    return MarketDataService(mock_client)


@pytest.fixture
def btc_asset(app):
    with app.app_context():
        asset = Asset.query.filter_by(coingecko_id='bitcoin').first()
        if not asset:
            asset = Asset(symbol='BTC', name='Bitcoin', coingecko_id='bitcoin', category='Layer 1')
            db.session.add(asset)
            db.session.commit()
        yield asset


class TestGetCurrentPrices:

    def test_returns_cached_when_fresh(self, app, service, mock_client, btc_asset):
        with app.app_context():
            # Clean up any existing data first
            MarketDataDaily.query.filter_by(asset_id=btc_asset.id).delete()
            db.session.commit()

            md = MarketDataDaily(
                asset_id=btc_asset.id, date=date.today(),
                price=Decimal('70000'), market_cap=Decimal('1300000000000'),
                volume=Decimal('40000000000'),
            )
            db.session.add(md)
            db.session.commit()

            result = service.get_current_prices([btc_asset.id])
            assert result[btc_asset.id] == Decimal('70000')
            mock_client.get_coin_markets.assert_not_called()

            db.session.delete(md)
            db.session.commit()

    def test_fetches_when_stale(self, app, service, mock_client, btc_asset):
        with app.app_context():
            # Clean up any existing data that might conflict
            MarketDataDaily.query.filter_by(asset_id=btc_asset.id).delete()
            db.session.commit()

            old_date = date.today() - timedelta(days=2)
            md = MarketDataDaily(
                asset_id=btc_asset.id, date=old_date,
                price=Decimal('65000'),
            )
            db.session.add(md)
            db.session.commit()

            mock_client.get_coin_markets.return_value = [
                {'id': 'bitcoin', 'current_price': 71000, 'market_cap': 1.35e12, 'total_volume': 4.1e10}
            ]
            result = service.get_current_prices([btc_asset.id])
            mock_client.get_coin_markets.assert_called_once()
            assert result[btc_asset.id] == Decimal('71000')

            MarketDataDaily.query.filter_by(asset_id=btc_asset.id).delete()
            db.session.commit()

    def test_falls_back_to_cache_on_api_failure(self, app, service, mock_client, btc_asset):
        with app.app_context():
            # Clean up any existing data that might conflict
            MarketDataDaily.query.filter_by(asset_id=btc_asset.id).delete()
            db.session.commit()

            old_date = date.today() - timedelta(days=3)
            md = MarketDataDaily(
                asset_id=btc_asset.id, date=old_date,
                price=Decimal('60000'),
            )
            db.session.add(md)
            db.session.commit()

            mock_client.get_coin_markets.side_effect = CoinGeckoClientError('fail')
            result = service.get_current_prices([btc_asset.id])
            assert result[btc_asset.id] == Decimal('60000')

            db.session.delete(md)
            db.session.commit()


class TestRefreshAllMarketData:

    def test_batch_updates_all_assets(self, app, service, mock_client, btc_asset):
        with app.app_context():
            mock_client.get_coin_markets.return_value = [
                {'id': 'bitcoin', 'current_price': 72000, 'market_cap': 1.4e12, 'total_volume': 4.2e10}
            ]
            count = service.refresh_all_market_data()
            assert count >= 1

            today_data = MarketDataDaily.query.filter_by(
                asset_id=btc_asset.id, date=date.today()
            ).first()
            assert today_data is not None
            assert today_data.price == Decimal('72000')

            MarketDataDaily.query.filter_by(asset_id=btc_asset.id, date=date.today()).delete()
            db.session.commit()
