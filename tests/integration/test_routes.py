import json
from decimal import Decimal
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import User, Asset
from app.models.market_data import MarketDataDaily
from app.services.auth_service import AuthService
from app.services.portfolio_service import PortfolioService
from app.seeds import load_assets


@pytest.fixture(autouse=True)
def seed(app):
    with app.app_context():
        load_assets()
        yield


class TestAuthRoutes:

    def test_login_page_renders(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'Authenticate' in resp.data

    def test_register_page_renders(self, client):
        resp = client.get('/register')
        assert resp.status_code == 200
        assert b'Create Account' in resp.data

    def test_register_creates_user_and_redirects(self, app, client):
        resp = client.post('/register', data={
            'email': 'route_reg@test.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)

        with app.app_context():
            user = User.query.filter_by(email='route_reg@test.com').first()
            assert user is not None

    def test_login_authenticates_and_redirects(self, app, client):
        with app.app_context():
            AuthService.register('route_login@test.com', 'mypassword123')

        resp = client.post('/login', data={
            'email': 'route_login@test.com',
            'password': 'mypassword123',
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)

    def test_protected_route_redirects_unauthenticated(self, client):
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code in (302, 303)

    def test_logout_clears_session(self, app, client):
        with app.app_context():
            AuthService.register('route_logout@test.com', 'mypassword123')

        client.post('/login', data={
            'email': 'route_logout@test.com',
            'password': 'mypassword123',
        })
        resp = client.get('/logout', follow_redirects=False)
        assert resp.status_code in (302, 303)

        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code in (302, 303)


class TestAdminRoutes:

    def test_non_admin_rejected(self, app, client):
        with app.app_context():
            AuthService.register('normal_admin_test@test.com', 'password123')

        client.post('/login', data={
            'email': 'normal_admin_test@test.com',
            'password': 'password123',
        })
        resp = client.get('/admin')
        assert resp.status_code == 403


_chart_test_counter = 0


def _login_with_portfolio(app, client, email='chart@test.com'):
    """Helper: register, login, create portfolio with BTC+ETH, seed price data."""
    global _chart_test_counter
    _chart_test_counter += 1

    with app.app_context():
        user = AuthService.register(email, 'password123')
        portfolio = PortfolioService.create_portfolio(user.id, 'Test')

        btc = Asset.query.filter_by(symbol='BTC').first()
        eth = Asset.query.filter_by(symbol='ETH').first()

        holdings = {btc.id: Decimal('60'), eth.id: Decimal('40')}
        PortfolioService.update_allocations(portfolio.id, user.id, holdings)

        # Seed 30 days of price data using unique date ranges per call
        # to avoid unique constraint conflicts across tests
        base = date(2019, 1, 1) + timedelta(days=_chart_test_counter * 40)
        for i in range(31):
            d = base + timedelta(days=i)
            existing = MarketDataDaily.query.filter_by(
                asset_id=btc.id, date=d).first()
            if not existing:
                db.session.add(MarketDataDaily(
                    asset_id=btc.id, date=d,
                    price=Decimal('40000') + Decimal(str(i * 100)),
                ))
            existing = MarketDataDaily.query.filter_by(
                asset_id=eth.id, date=d).first()
            if not existing:
                db.session.add(MarketDataDaily(
                    asset_id=eth.id, date=d,
                    price=Decimal('2500') + Decimal(str(i * 20)),
                ))
        db.session.commit()

    client.post('/login', data={'email': email, 'password': 'password123'})


class TestChartPerformanceAPI:

    def test_returns_weighted_index(self, app, client):
        _login_with_portfolio(app, client, 'perf1@test.com')
        resp = client.get('/api/chart/performance')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'dates' in data
        assert 'values' in data
        assert len(data['dates']) > 0
        assert len(data['values']) == len(data['dates'])
        # First value should be close to 100 (rebased)
        assert 95 <= data['values'][0] <= 105

    def test_empty_portfolio_returns_empty(self, app, client):
        with app.app_context():
            AuthService.register('perf_empty@test.com', 'password123')
        client.post('/login', data={'email': 'perf_empty@test.com', 'password': 'password123'})
        resp = client.get('/api/chart/performance')
        data = resp.get_json()
        assert data['dates'] == []
        assert data['values'] == []

    def test_unauthenticated_redirects(self, client):
        resp = client.get('/api/chart/performance', follow_redirects=False)
        assert resp.status_code in (302, 303)


class TestChartCorrelationAPI:

    def test_returns_matrix_and_symbols(self, app, client):
        _login_with_portfolio(app, client, 'corr1@test.com')
        resp = client.get('/api/chart/correlation')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'symbols' in data
        assert 'matrix' in data
        if data['symbols']:
            assert len(data['matrix']) == len(data['symbols'])
            assert len(data['matrix'][0]) == len(data['symbols'])
            # Diagonal should be 1.0
            for i in range(len(data['symbols'])):
                assert data['matrix'][i][i] == 1.0

    def test_empty_portfolio_returns_empty(self, app, client):
        with app.app_context():
            AuthService.register('corr_empty@test.com', 'password123')
        client.post('/login', data={'email': 'corr_empty@test.com', 'password': 'password123'})
        resp = client.get('/api/chart/correlation')
        data = resp.get_json()
        assert data['symbols'] == []
        assert data['matrix'] == []

    def test_unauthenticated_redirects(self, client):
        resp = client.get('/api/chart/correlation', follow_redirects=False)
        assert resp.status_code in (302, 303)


class TestRiskPreviewAPI:

    def test_valid_holdings_returns_metrics(self, app, client):
        _login_with_portfolio(app, client, 'preview1@test.com')
        with app.app_context():
            btc = Asset.query.filter_by(symbol='BTC').first()
            eth = Asset.query.filter_by(symbol='ETH').first()

        resp = client.post('/api/portfolio/risk-preview',
                           data=json.dumps({'holdings': {str(btc.id): 70, str(eth.id): 30}}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'top1_concentration' in data
        assert 'hhi' in data
        assert 'sector_exposure' in data
        assert data['top1_concentration'] == 70.0

    def test_missing_holdings_returns_400(self, app, client):
        _login_with_portfolio(app, client, 'preview2@test.com')
        resp = client.post('/api/portfolio/risk-preview',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_unauthenticated_redirects(self, client):
        resp = client.post('/api/portfolio/risk-preview', follow_redirects=False)
        assert resp.status_code in (302, 303)


def _setup_versioned_portfolio(app, client, email):
    """Helper: create portfolio with 2 versions for compare/revert testing.
    Returns IDs instead of ORM objects to avoid detached instance errors."""
    with app.app_context():
        user = AuthService.register(email, 'password123')
        portfolio = PortfolioService.create_portfolio(user.id, 'CompareTest')

        btc = Asset.query.filter_by(symbol='BTC').first()
        eth = Asset.query.filter_by(symbol='ETH').first()

        PortfolioService.update_allocations(
            portfolio.id, user.id,
            {btc.id: Decimal('60'), eth.id: Decimal('40')},
        )
        v1 = PortfolioService.get_active_version(portfolio.id)

        PortfolioService.update_allocations(
            portfolio.id, user.id,
            {btc.id: Decimal('80'), eth.id: Decimal('20')},
        )
        v2 = PortfolioService.get_active_version(portfolio.id)

        return portfolio.id, v1.id, v2.id


class TestCompareRoute:

    def test_renders_comparison(self, app, client):
        portfolio_id, v1_id, v2_id = _setup_versioned_portfolio(app, client, 'compare1@test.com')
        client.post('/login', data={'email': 'compare1@test.com', 'password': 'password123'})
        resp = client.get(f'/history/compare/{v1_id}/{v2_id}')
        assert resp.status_code == 200
        assert b'Version Comparison' in resp.data
        assert b'BTC' in resp.data

    def test_invalid_version_redirects(self, app, client):
        with app.app_context():
            AuthService.register('compare_bad@test.com', 'password123')
        client.post('/login', data={'email': 'compare_bad@test.com', 'password': 'password123'})
        resp = client.get('/history/compare/99999/99998', follow_redirects=True)
        assert resp.status_code == 200

    def test_unauthenticated_redirects(self, client):
        resp = client.get('/history/compare/1/2', follow_redirects=False)
        assert resp.status_code in (302, 303)


class TestRevertRoute:

    def test_reverts_and_redirects(self, app, client):
        portfolio_id, v1_id, v2_id = _setup_versioned_portfolio(app, client, 'revert1@test.com')
        client.post('/login', data={'email': 'revert1@test.com', 'password': 'password123'})
        resp = client.post(f'/history/revert/{v1_id}', follow_redirects=False)
        assert resp.status_code in (302, 303)

        with app.app_context():
            active = PortfolioService.get_active_version(portfolio_id)
            assert active.version_num == 3
            holdings = {h.asset.symbol: h.weight_pct for h in active.holdings}
            assert holdings['BTC'] == Decimal('60')
            assert holdings['ETH'] == Decimal('40')

    def test_invalid_version_redirects(self, app, client):
        with app.app_context():
            AuthService.register('revert_bad@test.com', 'password123')
        client.post('/login', data={'email': 'revert_bad@test.com', 'password': 'password123'})
        resp = client.post('/history/revert/99999', follow_redirects=True)
        assert resp.status_code == 200

    def test_unauthenticated_redirects(self, client):
        resp = client.post('/history/revert/1', follow_redirects=False)
        assert resp.status_code in (302, 303)
