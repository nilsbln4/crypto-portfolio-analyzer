import json
from decimal import Decimal

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user

from app.services.portfolio_service import PortfolioService
from app.services.risk_service import RiskService, Holding, ReturnMetrics
from app.services.market_data_service import MarketDataService
from app.services.coingecko_client import CoinGeckoClient
from app.models import Asset

import os

dashboard_bp = Blueprint('dashboard', __name__)


def _get_market_service():
    client = CoinGeckoClient(api_key=os.environ.get('COINGECKO_API_KEY', ''))
    return MarketDataService(client)


def _build_holdings_from_version(version):
    holdings = []
    for h in version.holdings:
        holdings.append(Holding(
            asset_id=h.asset_id,
            symbol=h.asset.symbol,
            weight_pct=h.weight_pct,
            category=h.asset.category,
        ))
    return holdings


def _get_active_portfolio(portfolios, portfolio_id=None):
    if portfolio_id:
        return next((p for p in portfolios if p.id == portfolio_id), portfolios[0])
    return portfolios[0]


def _find_btc_asset_id():
    """Find BTC asset ID from database, not from holdings."""
    btc_asset = Asset.query.filter_by(symbol='BTC').first()
    return btc_asset.id if btc_asset else None


@dashboard_bp.route('/dashboard')
@login_required
def index():
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    portfolio_id = request.args.get('portfolio_id', type=int)

    portfolio_data = None
    metrics = None
    returns = None
    holdings_list = []

    if portfolios:
        portfolio = _get_active_portfolio(portfolios, portfolio_id)
        version = PortfolioService.get_active_version(portfolio.id)
        if version:
            holdings_list = _build_holdings_from_version(version)
            market_svc = _get_market_service()

            price_histories = {}
            for h in holdings_list:
                cached = market_svc.get_historical_prices(h.asset_id, days=90)
                if cached:
                    price_histories[h.asset_id] = [row.price for row in cached]

            # Always fetch BTC data for beta calculation, even if not in portfolio
            btc_asset_id = _find_btc_asset_id()
            if btc_asset_id and btc_asset_id not in price_histories:
                btc_cached = market_svc.get_historical_prices(btc_asset_id, days=90)
                if btc_cached:
                    price_histories[btc_asset_id] = [row.price for row in btc_cached]

            metrics = RiskService.compute_all_metrics(
                holdings_list, price_histories=price_histories,
                btc_asset_id=btc_asset_id,
            )
            returns = RiskService.compute_all_returns(
                holdings_list, price_histories, btc_asset_id=btc_asset_id,
            )

            portfolio_data = {
                'name': portfolio.name,
                'version': version.version_num,
                'holdings': [
                    {'symbol': h.symbol, 'weight': float(h.weight_pct), 'category': h.category}
                    for h in holdings_list
                ],
            }

    return render_template(
        'dashboard/index.html',
        portfolio=portfolio_data,
        metrics=metrics,
        returns=returns,
        has_portfolio=portfolio_data is not None,
        portfolios=portfolios,
    )


@dashboard_bp.route('/api/chart/allocation')
@login_required
def chart_allocation():
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return jsonify({'labels': [], 'values': [], 'categories': []})

    portfolio = _get_active_portfolio(portfolios, request.args.get('portfolio_id', type=int))
    version = PortfolioService.get_active_version(portfolio.id)
    if not version:
        return jsonify({'labels': [], 'values': [], 'categories': []})

    labels = [h.asset.symbol for h in version.holdings]
    values = [float(h.weight_pct) for h in version.holdings]
    categories = [h.asset.category for h in version.holdings]
    return jsonify({'labels': labels, 'values': values, 'categories': categories})


@dashboard_bp.route('/api/chart/sector')
@login_required
def chart_sector():
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return jsonify({'labels': [], 'values': []})

    portfolio = _get_active_portfolio(portfolios, request.args.get('portfolio_id', type=int))
    version = PortfolioService.get_active_version(portfolio.id)
    if not version:
        return jsonify({'labels': [], 'values': []})

    holdings = _build_holdings_from_version(version)
    sectors = RiskService.sector_exposure(holdings)
    return jsonify({
        'labels': list(sectors.keys()),
        'values': [float(v) for v in sectors.values()],
    })


@dashboard_bp.route('/api/chart/historical')
@login_required
def chart_historical():
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return jsonify({'series': []})

    portfolio = _get_active_portfolio(portfolios, request.args.get('portfolio_id', type=int))
    version = PortfolioService.get_active_version(portfolio.id)
    if not version:
        return jsonify({'series': []})

    market_svc = _get_market_service()
    series = []

    for h in version.holdings:
        cached = market_svc.get_historical_prices(h.asset_id, days=90)
        if cached:
            first_price = cached[0].price
            if first_price > 0:
                series.append({
                    'name': h.asset.symbol,
                    'dates': [row.date.isoformat() for row in cached],
                    'values': [float(row.price / first_price * 100) for row in cached],
                })

    return jsonify({'series': series})


@dashboard_bp.route('/api/chart/performance')
@login_required
def chart_performance():
    """Weighted portfolio index rebased to 100."""
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return jsonify({'dates': [], 'values': []})

    portfolio = _get_active_portfolio(portfolios, request.args.get('portfolio_id', type=int))
    version = PortfolioService.get_active_version(portfolio.id)
    if not version:
        return jsonify({'dates': [], 'values': []})

    market_svc = _get_market_service()
    holdings = _build_holdings_from_version(version)

    # Collect price series per asset with dates
    asset_data = {}
    all_dates = set()
    for h in holdings:
        cached = market_svc.get_historical_prices(h.asset_id, days=90)
        if cached:
            prices_by_date = {row.date.isoformat(): row.price for row in cached}
            asset_data[h.asset_id] = {
                'weight': float(h.weight_pct) / 100,
                'prices': prices_by_date,
                'first_price': cached[0].price,
            }
            all_dates.update(prices_by_date.keys())

    if not all_dates or not asset_data:
        return jsonify({'dates': [], 'values': []})

    dates = sorted(all_dates)
    values = []
    for d in dates:
        day_value = 0.0
        for aid, data in asset_data.items():
            price = data['prices'].get(d)
            if price and data['first_price'] > 0:
                normalized = float(price / data['first_price'])
                day_value += data['weight'] * normalized
        values.append(round(day_value * 100, 2))

    return jsonify({'dates': dates, 'values': values})


@dashboard_bp.route('/api/chart/correlation')
@login_required
def chart_correlation():
    """Correlation matrix for heatmap: {symbols: [...], matrix: [[...]]}."""
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return jsonify({'symbols': [], 'matrix': []})

    portfolio = _get_active_portfolio(portfolios, request.args.get('portfolio_id', type=int))
    version = PortfolioService.get_active_version(portfolio.id)
    if not version:
        return jsonify({'symbols': [], 'matrix': []})

    market_svc = _get_market_service()
    holdings = _build_holdings_from_version(version)

    price_histories = {}
    id_to_symbol = {}
    for h in holdings:
        cached = market_svc.get_historical_prices(h.asset_id, days=90)
        if cached:
            price_histories[h.asset_id] = [row.price for row in cached]
            id_to_symbol[h.asset_id] = h.symbol

    corr = RiskService.compute_correlation_matrix(price_histories)
    if not corr:
        return jsonify({'symbols': [], 'matrix': []})

    asset_ids = sorted(id_to_symbol.keys())
    symbols = [id_to_symbol[aid] for aid in asset_ids]
    matrix = []
    for aid_a in asset_ids:
        row = []
        for aid_b in asset_ids:
            val = corr.get((aid_a, aid_b))
            row.append(float(val) if val is not None else 0.0)
        matrix.append(row)

    return jsonify({'symbols': symbols, 'matrix': matrix})


@dashboard_bp.route('/api/chart/returns')
@login_required
def chart_returns():
    """Per-asset returns for bar chart: {symbols, returns_7d, returns_30d}."""
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return jsonify({'symbols': [], 'returns_7d': [], 'returns_30d': []})

    portfolio = _get_active_portfolio(portfolios, request.args.get('portfolio_id', type=int))
    version = PortfolioService.get_active_version(portfolio.id)
    if not version:
        return jsonify({'symbols': [], 'returns_7d': [], 'returns_30d': []})

    market_svc = _get_market_service()
    holdings = _build_holdings_from_version(version)

    symbols = []
    returns_7d = []
    returns_30d = []

    for h in holdings:
        cached = market_svc.get_historical_prices(h.asset_id, days=90)
        if cached:
            prices = [row.price for row in cached]
            r7 = RiskService.compute_period_return(prices, 7)
            r30 = RiskService.compute_period_return(prices, 30)
            symbols.append(h.symbol)
            returns_7d.append(float(r7) if r7 is not None else 0)
            returns_30d.append(float(r30) if r30 is not None else 0)

    return jsonify({'symbols': symbols, 'returns_7d': returns_7d, 'returns_30d': returns_30d})
