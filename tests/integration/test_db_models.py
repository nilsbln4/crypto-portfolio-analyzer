from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    User, Asset, Portfolio, PortfolioVersion, PortfolioHolding,
    MarketDataDaily, RiskSnapshot, Transaction, AdminAction,
)


class TestUserModel:

    def test_create_user(self, app):
        with app.app_context():
            user = User(email='test@example.com', password_hash='hashed', role='NORMAL')
            db.session.add(user)
            db.session.commit()

            fetched = db.session.get(User, user.id)
            assert fetched.email == 'test@example.com'
            assert fetched.role == 'NORMAL'
            assert fetched.is_active is True
            assert fetched.created_at is not None

            db.session.delete(fetched)
            db.session.commit()

    def test_user_email_unique(self, app):
        with app.app_context():
            u1 = User(email='dup@example.com', password_hash='h1')
            u2 = User(email='dup@example.com', password_hash='h2')
            db.session.add(u1)
            db.session.commit()
            db.session.add(u2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()
            db.session.delete(u1)
            db.session.commit()

    def test_user_is_admin(self, app):
        with app.app_context():
            normal = User(email='normal@test.com', password_hash='h', role='NORMAL')
            admin = User(email='admin@test.com', password_hash='h', role='ADMIN')
            assert normal.is_admin() is False
            assert admin.is_admin() is True

    def test_user_default_role_is_normal(self, app):
        with app.app_context():
            user = User(email='default_role@test.com', password_hash='h')
            db.session.add(user)
            db.session.commit()

            fetched = db.session.get(User, user.id)
            assert fetched.role == 'NORMAL'

            db.session.delete(fetched)
            db.session.commit()


class TestAssetModel:

    def test_create_asset(self, app):
        with app.app_context():
            asset = Asset(symbol='BTC', name='Bitcoin', coingecko_id='bitcoin', category='Layer 1')
            db.session.add(asset)
            db.session.commit()

            fetched = db.session.get(Asset, asset.id)
            assert fetched.symbol == 'BTC'
            assert fetched.coingecko_id == 'bitcoin'
            assert fetched.category == 'Layer 1'

            db.session.delete(fetched)
            db.session.commit()

    def test_asset_coingecko_id_unique(self, app):
        with app.app_context():
            a1 = Asset(symbol='BTC', name='Bitcoin', coingecko_id='bitcoin_dup', category='L1')
            a2 = Asset(symbol='BTC2', name='Bitcoin2', coingecko_id='bitcoin_dup', category='L1')
            db.session.add(a1)
            db.session.commit()
            db.session.add(a2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()
            db.session.delete(a1)
            db.session.commit()


class TestPortfolioModel:

    def test_create_portfolio_with_version_and_holdings(self, app):
        with app.app_context():
            user = User(email='port_test@test.com', password_hash='h')
            asset = Asset(symbol='ETH', name='Ethereum', coingecko_id='ethereum_test', category='Layer 1')
            db.session.add_all([user, asset])
            db.session.commit()

            portfolio = Portfolio(user_id=user.id, name='Test Portfolio')
            db.session.add(portfolio)
            db.session.commit()

            version = PortfolioVersion(portfolio_id=portfolio.id, version_num=1)
            db.session.add(version)
            db.session.commit()

            holding = PortfolioHolding(
                version_id=version.id, asset_id=asset.id, weight_pct=Decimal('100.000')
            )
            db.session.add(holding)
            db.session.commit()

            fetched_version = db.session.get(PortfolioVersion, version.id)
            assert len(fetched_version.holdings) == 1
            assert fetched_version.holdings[0].weight_pct == Decimal('100.000')
            assert fetched_version.holdings[0].asset.symbol == 'ETH'

            db.session.delete(portfolio)
            db.session.delete(asset)
            db.session.delete(user)
            db.session.commit()

    def test_portfolio_version_unique_constraint(self, app):
        with app.app_context():
            user = User(email='ver_unique@test.com', password_hash='h')
            db.session.add(user)
            db.session.commit()

            portfolio = Portfolio(user_id=user.id, name='Dup Version Test')
            db.session.add(portfolio)
            db.session.commit()

            v1 = PortfolioVersion(portfolio_id=portfolio.id, version_num=1)
            v2 = PortfolioVersion(portfolio_id=portfolio.id, version_num=1)
            db.session.add(v1)
            db.session.commit()
            db.session.add(v2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()

            db.session.delete(v1)
            db.session.delete(portfolio)
            db.session.delete(user)
            db.session.commit()

    def test_cascade_delete_portfolio_removes_versions_and_holdings(self, app):
        with app.app_context():
            user = User(email='cascade@test.com', password_hash='h')
            asset = Asset(symbol='SOL', name='Solana', coingecko_id='solana_cascade', category='Layer 1')
            db.session.add_all([user, asset])
            db.session.commit()

            portfolio = Portfolio(user_id=user.id, name='Cascade Test')
            db.session.add(portfolio)
            db.session.commit()

            version = PortfolioVersion(portfolio_id=portfolio.id, version_num=1)
            db.session.add(version)
            db.session.commit()

            holding = PortfolioHolding(
                version_id=version.id, asset_id=asset.id, weight_pct=Decimal('50.000')
            )
            db.session.add(holding)
            db.session.commit()

            version_id = version.id
            holding_id = holding.id

            db.session.delete(portfolio)
            db.session.commit()

            assert db.session.get(PortfolioVersion, version_id) is None
            assert db.session.get(PortfolioHolding, holding_id) is None

            db.session.delete(asset)
            db.session.delete(user)
            db.session.commit()


class TestMarketDataDailyModel:

    def test_create_market_data(self, app):
        with app.app_context():
            asset = Asset(symbol='ADA', name='Cardano', coingecko_id='cardano_mkt', category='Layer 1')
            db.session.add(asset)
            db.session.commit()

            md = MarketDataDaily(
                asset_id=asset.id,
                date=date(2025, 1, 15),
                price=Decimal('0.45000000'),
                market_cap=Decimal('16000000000.00'),
                volume=Decimal('500000000.00'),
            )
            db.session.add(md)
            db.session.commit()

            fetched = db.session.get(MarketDataDaily, md.id)
            assert fetched.date == date(2025, 1, 15)
            assert fetched.price == Decimal('0.45000000')

            db.session.delete(md)
            db.session.delete(asset)
            db.session.commit()

    def test_market_data_asset_date_unique(self, app):
        with app.app_context():
            asset = Asset(symbol='DOT', name='Polkadot', coingecko_id='polkadot_mkt', category='Layer 1')
            db.session.add(asset)
            db.session.commit()

            md1 = MarketDataDaily(
                asset_id=asset.id, date=date(2025, 1, 1),
                price=Decimal('7.00000000'),
            )
            md2 = MarketDataDaily(
                asset_id=asset.id, date=date(2025, 1, 1),
                price=Decimal('7.50000000'),
            )
            db.session.add(md1)
            db.session.commit()
            db.session.add(md2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()

            db.session.delete(md1)
            db.session.delete(asset)
            db.session.commit()


class TestRiskSnapshotModel:

    def test_create_risk_snapshot(self, app):
        with app.app_context():
            user = User(email='risk_snap@test.com', password_hash='h')
            db.session.add(user)
            db.session.commit()

            portfolio = Portfolio(user_id=user.id, name='Risk Test')
            db.session.add(portfolio)
            db.session.commit()

            version = PortfolioVersion(portfolio_id=portfolio.id, version_num=1)
            db.session.add(version)
            db.session.commit()

            metrics = {'hhi': 5000, 'top1': 60.0, 'stablecoin_pct': 10.0}
            snap = RiskSnapshot(version_id=version.id, metrics_json=metrics)
            db.session.add(snap)
            db.session.commit()

            fetched = db.session.get(RiskSnapshot, snap.id)
            assert fetched.metrics_json['hhi'] == 5000
            assert fetched.computed_at is not None

            db.session.delete(snap)
            db.session.delete(portfolio)
            db.session.delete(user)
            db.session.commit()


class TestTransactionModel:

    def test_create_transaction(self, app):
        with app.app_context():
            user = User(email='txn@test.com', password_hash='h')
            db.session.add(user)
            db.session.commit()

            portfolio = Portfolio(user_id=user.id, name='Txn Test')
            db.session.add(portfolio)
            db.session.commit()

            txn = Transaction(
                user_id=user.id,
                portfolio_id=portfolio.id,
                type='CREATE',
                diff_json={'changes': []},
            )
            db.session.add(txn)
            db.session.commit()

            fetched = db.session.get(Transaction, txn.id)
            assert fetched.type == 'CREATE'
            assert fetched.user.email == 'txn@test.com'

            db.session.delete(txn)
            db.session.delete(portfolio)
            db.session.delete(user)
            db.session.commit()


class TestAdminActionModel:

    def test_create_admin_action(self, app):
        with app.app_context():
            admin = User(email='admin_act@test.com', password_hash='h', role='ADMIN')
            target = User(email='target_act@test.com', password_hash='h')
            db.session.add_all([admin, target])
            db.session.commit()

            action = AdminAction(
                admin_user_id=admin.id,
                action_type='DISABLE',
                target_user_id=target.id,
            )
            db.session.add(action)
            db.session.commit()

            fetched = db.session.get(AdminAction, action.id)
            assert fetched.action_type == 'DISABLE'
            assert fetched.admin.email == 'admin_act@test.com'
            assert fetched.target.email == 'target_act@test.com'

            db.session.delete(action)
            db.session.delete(admin)
            db.session.delete(target)
            db.session.commit()
