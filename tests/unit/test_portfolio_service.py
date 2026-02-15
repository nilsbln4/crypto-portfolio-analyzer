from decimal import Decimal

import pytest

from app.extensions import db
from app.models import User, Asset, Portfolio, PortfolioVersion, PortfolioHolding, Transaction
from app.services.portfolio_service import PortfolioService, PortfolioError
from app.services.auth_service import AuthService
from app.seeds import load_assets


@pytest.fixture(autouse=True)
def seed_assets(app):
    with app.app_context():
        load_assets()
        yield


@pytest.fixture
def user(app, request):
    with app.app_context():
        email = f'portfolio_{request.node.name}@test.com'
        u = User(email=email, password_hash='h', role='NORMAL')
        db.session.add(u)
        db.session.commit()
        yield u


class TestLoadPredefined:

    def test_creates_portfolio_with_version(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            assert portfolio.name == 'BTC/ETH Core'
            assert portfolio.user_id == user.id

            version = PortfolioService.get_active_version(portfolio.id)
            assert version.version_num == 1

    def test_copies_correct_holdings(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            version = PortfolioService.get_active_version(portfolio.id)
            holdings = version.holdings
            assert len(holdings) == 3

            symbols = {h.asset.symbol for h in holdings}
            assert symbols == {'BTC', 'ETH', 'USDC'}

    def test_creates_transaction_record(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            txn = Transaction.query.filter_by(
                portfolio_id=portfolio.id, type='CREATE'
            ).first()
            assert txn is not None
            assert txn.diff_json['template'] == 'BTC/ETH Core'

    def test_unknown_template_raises_error(self, app, user):
        with app.app_context():
            with pytest.raises(PortfolioError, match='Unknown template'):
                PortfolioService.load_predefined(user.id, 'Nonexistent')


class TestUpdateAllocations:

    def test_creates_new_version(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            btc = Asset.query.filter_by(symbol='BTC').first()
            eth = Asset.query.filter_by(symbol='ETH').first()
            usdc = Asset.query.filter_by(symbol='USDC').first()

            new_version = PortfolioService.update_allocations(
                portfolio.id, user.id,
                {btc.id: Decimal('50'), eth.id: Decimal('40'), usdc.id: Decimal('10')},
            )
            assert new_version.version_num == 2

    def test_validates_weights_sum_to_100(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            btc = Asset.query.filter_by(symbol='BTC').first()

            with pytest.raises(PortfolioError, match='sum to 100'):
                PortfolioService.update_allocations(
                    portfolio.id, user.id, {btc.id: Decimal('50')},
                )

    def test_rejects_negative_weights(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            btc = Asset.query.filter_by(symbol='BTC').first()
            eth = Asset.query.filter_by(symbol='ETH').first()

            with pytest.raises(PortfolioError, match='negative'):
                PortfolioService.update_allocations(
                    portfolio.id, user.id,
                    {btc.id: Decimal('110'), eth.id: Decimal('-10')},
                )

    def test_saves_transaction_with_diff(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            btc = Asset.query.filter_by(symbol='BTC').first()
            eth = Asset.query.filter_by(symbol='ETH').first()
            usdc = Asset.query.filter_by(symbol='USDC').first()

            PortfolioService.update_allocations(
                portfolio.id, user.id,
                {btc.id: Decimal('50'), eth.id: Decimal('40'), usdc.id: Decimal('10')},
            )
            txn = Transaction.query.filter_by(
                portfolio_id=portfolio.id, type='MODIFY'
            ).first()
            assert txn is not None
            assert len(txn.diff_json['changes']) > 0


class TestNormalizeWeights:

    def test_scales_to_100(self):
        holdings = {1: Decimal('30'), 2: Decimal('20')}
        result = PortfolioService.normalize_weights(holdings)
        assert sum(result.values()) == Decimal('100.000')

    def test_already_100_unchanged(self):
        holdings = {1: Decimal('60'), 2: Decimal('40')}
        result = PortfolioService.normalize_weights(holdings)
        assert result[1] == Decimal('60.000')
        assert result[2] == Decimal('40.000')


class TestGetPortfolioForUser:

    def test_returns_own_portfolio(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            result = PortfolioService.get_portfolio_for_user(user.id, portfolio.id)
            assert result.id == portfolio.id

    def test_rejects_other_users_portfolio(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            with pytest.raises(PortfolioError, match='not found'):
                PortfolioService.get_portfolio_for_user(user.id + 999, portfolio.id)


class TestCreatePortfolio:
    def test_creates_named_portfolio(self, app):
        with app.app_context():
            user = AuthService.register('create_test@test.com', 'testpass1')
            portfolio = PortfolioService.create_portfolio(user.id, 'My Portfolio')
            assert portfolio.name == 'My Portfolio'
            assert portfolio.user_id == user.id
            assert portfolio.is_active is True

    def test_rejects_empty_name(self, app):
        with app.app_context():
            user = AuthService.register('create_empty@test.com', 'testpass1')
            with pytest.raises(PortfolioError):
                PortfolioService.create_portfolio(user.id, '')

    def test_rejects_long_name(self, app):
        with app.app_context():
            user = AuthService.register('create_long@test.com', 'testpass1')
            with pytest.raises(PortfolioError):
                PortfolioService.create_portfolio(user.id, 'x' * 101)


class TestRenamePortfolio:
    def test_renames_portfolio(self, app):
        with app.app_context():
            user = AuthService.register('rename_test@test.com', 'testpass1')
            portfolio = PortfolioService.create_portfolio(user.id, 'Old Name')
            PortfolioService.rename_portfolio(portfolio.id, user.id, 'New Name')
            refreshed = db.session.get(Portfolio, portfolio.id)
            assert refreshed.name == 'New Name'

    def test_rejects_empty_name(self, app):
        with app.app_context():
            user = AuthService.register('rename_empty@test.com', 'testpass1')
            portfolio = PortfolioService.create_portfolio(user.id, 'Test')
            with pytest.raises(PortfolioError):
                PortfolioService.rename_portfolio(portfolio.id, user.id, '')


class TestDeletePortfolio:
    def test_soft_deletes(self, app):
        with app.app_context():
            user = AuthService.register('delete_test@test.com', 'testpass1')
            portfolio = PortfolioService.create_portfolio(user.id, 'To Delete')
            PortfolioService.delete_portfolio(portfolio.id, user.id)
            refreshed = db.session.get(Portfolio, portfolio.id)
            assert refreshed.is_active is False

    def test_creates_delete_transaction(self, app):
        with app.app_context():
            user = AuthService.register('delete_txn@test.com', 'testpass1')
            portfolio = PortfolioService.create_portfolio(user.id, 'To Delete')
            PortfolioService.delete_portfolio(portfolio.id, user.id)
            txn = Transaction.query.filter_by(user_id=user.id, type='DELETE').first()
            assert txn is not None

    def test_excluded_from_user_list(self, app):
        with app.app_context():
            user = AuthService.register('delete_list@test.com', 'testpass1')
            portfolio = PortfolioService.create_portfolio(user.id, 'Active')
            PortfolioService.delete_portfolio(portfolio.id, user.id)
            portfolios = PortfolioService.get_user_portfolios(user.id)
            assert len(portfolios) == 0


class TestRevertToVersion:

    def test_creates_new_version_with_old_holdings(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            v1 = PortfolioService.get_active_version(portfolio.id)
            v1_holdings = {h.asset.symbol: h.weight_pct for h in v1.holdings}

            btc = Asset.query.filter_by(symbol='BTC').first()
            eth = Asset.query.filter_by(symbol='ETH').first()
            usdc = Asset.query.filter_by(symbol='USDC').first()
            PortfolioService.update_allocations(
                portfolio.id, user.id,
                {btc.id: Decimal('80'), eth.id: Decimal('15'), usdc.id: Decimal('5')},
            )

            new_version = PortfolioService.revert_to_version(
                portfolio.id, user.id, v1.id
            )
            assert new_version.version_num == 3
            reverted_holdings = {h.asset.symbol: h.weight_pct for h in new_version.holdings}
            assert reverted_holdings == v1_holdings

    def test_creates_revert_transaction(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            v1 = PortfolioService.get_active_version(portfolio.id)

            btc = Asset.query.filter_by(symbol='BTC').first()
            eth = Asset.query.filter_by(symbol='ETH').first()
            usdc = Asset.query.filter_by(symbol='USDC').first()
            PortfolioService.update_allocations(
                portfolio.id, user.id,
                {btc.id: Decimal('80'), eth.id: Decimal('15'), usdc.id: Decimal('5')},
            )

            PortfolioService.revert_to_version(portfolio.id, user.id, v1.id)
            txn = Transaction.query.filter_by(
                portfolio_id=portfolio.id, type='REVERT'
            ).first()
            assert txn is not None
            assert txn.diff_json['action'] == 'revert'
            assert txn.diff_json['to_version'] == 1

    def test_rejects_invalid_version(self, app, user):
        with app.app_context():
            portfolio = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            with pytest.raises(PortfolioError, match='Version not found'):
                PortfolioService.revert_to_version(portfolio.id, user.id, 99999)

    def test_rejects_other_portfolios_version(self, app, user):
        with app.app_context():
            p1 = PortfolioService.load_predefined(user.id, 'BTC/ETH Core')
            p2 = PortfolioService.create_portfolio(user.id, 'Other')
            btc = Asset.query.filter_by(symbol='BTC').first()
            PortfolioService.update_allocations(
                p2.id, user.id, {btc.id: Decimal('100')},
            )
            v_other = PortfolioService.get_active_version(p2.id)

            with pytest.raises(PortfolioError, match='Version not found'):
                PortfolioService.revert_to_version(p1.id, user.id, v_other.id)
