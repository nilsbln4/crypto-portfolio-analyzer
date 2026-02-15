from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db, csrf
from app.models import Asset
from app.models.market_data import MarketDataDaily
from app.services.portfolio_service import PortfolioService, PortfolioError
from app.services.risk_service import RiskService, Holding
from app.seeds import get_portfolio_templates

portfolio_bp = Blueprint('portfolio', __name__)


def _get_btc_asset_id():
    """Find BTC asset ID from database, not from holdings."""
    btc_asset = Asset.query.filter_by(symbol='BTC').first()
    return btc_asset.id if btc_asset else None


def _ensure_btc_in_price_histories(price_histories, btc_asset_id):
    """Fetch BTC price data if not already in price_histories."""
    if btc_asset_id and btc_asset_id not in price_histories:
        btc_cached = (
            MarketDataDaily.query
            .filter(MarketDataDaily.asset_id == btc_asset_id)
            .order_by(MarketDataDaily.date.desc())
            .limit(90)
            .all()
        )
        if btc_cached:
            price_histories[btc_asset_id] = [row.price for row in reversed(btc_cached)]


@portfolio_bp.route('/portfolio/analysis')
@portfolio_bp.route('/portfolio/analysis/<int:portfolio_id>')
@login_required
def analysis(portfolio_id=None):
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if not portfolios:
        return redirect(url_for('portfolio.adjustments'))

    if portfolio_id:
        portfolio = next((p for p in portfolios if p.id == portfolio_id), None)
        if not portfolio:
            flash('Portfolio not found.', 'error')
            return redirect(url_for('portfolio.analysis'))
    else:
        portfolio = portfolios[0]

    version = PortfolioService.get_active_version(portfolio.id)

    holdings = []
    current_holdings = {}
    metrics = None
    returns = None
    if version:
        for h in version.holdings:
            holdings.append({
                'symbol': h.asset.symbol,
                'name': h.asset.name,
                'weight': h.weight_pct,
                'category': h.asset.category,
                'asset_id': h.asset_id,
            })
            current_holdings[h.asset_id] = h.weight_pct
        holding_objs = [
            Holding(asset_id=h.asset_id, symbol=h.asset.symbol,
                    weight_pct=h.weight_pct, category=h.asset.category)
            for h in version.holdings
        ]

        price_histories = {}
        for h in holding_objs:
            cached = (
                MarketDataDaily.query
                .filter(MarketDataDaily.asset_id == h.asset_id)
                .order_by(MarketDataDaily.date.desc())
                .limit(90)
                .all()
            )
            if cached:
                price_histories[h.asset_id] = [row.price for row in reversed(cached)]

        # Always fetch BTC data for beta calculation, even if not in portfolio
        btc_id = _get_btc_asset_id()
        _ensure_btc_in_price_histories(price_histories, btc_id)

        metrics = RiskService.compute_all_metrics(
            holding_objs, price_histories=price_histories, btc_asset_id=btc_id
        )
        returns = RiskService.compute_all_returns(
            holding_objs, price_histories, btc_asset_id=btc_id
        )

    assets = Asset.query.order_by(Asset.symbol).all()
    assets_json = [
        {'id': a.id, 'symbol': a.symbol, 'name': a.name, 'category': a.category}
        for a in assets
    ]
    templates = get_portfolio_templates()

    return render_template(
        'portfolio/analysis.html',
        portfolio=portfolio, version=version,
        holdings=holdings, metrics=metrics, returns=returns,
        portfolios=portfolios, active_portfolio_id=portfolio.id,
        assets=assets, templates=templates,
        current_holdings=current_holdings,
        assets_json=assets_json,
    )


@portfolio_bp.route('/portfolio/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    try:
        portfolio = PortfolioService.create_portfolio(current_user.id, name)
        flash(f'Created portfolio: {name}', 'success')
    except PortfolioError as e:
        flash(str(e), 'error')
    return redirect(url_for('portfolio.analysis'))


@portfolio_bp.route('/portfolio/<int:portfolio_id>/rename', methods=['POST'])
@login_required
def rename(portfolio_id):
    new_name = request.form.get('name', '').strip()
    try:
        PortfolioService.rename_portfolio(portfolio_id, current_user.id, new_name)
        flash(f'Renamed to: {new_name}', 'success')
    except PortfolioError as e:
        flash(str(e), 'error')
    return redirect(url_for('portfolio.analysis', portfolio_id=portfolio_id))


@portfolio_bp.route('/portfolio/<int:portfolio_id>/delete', methods=['POST'])
@login_required
def delete(portfolio_id):
    try:
        PortfolioService.delete_portfolio(portfolio_id, current_user.id)
        flash('Portfolio deleted.', 'success')
    except PortfolioError as e:
        flash(str(e), 'error')
    return redirect(url_for('portfolio.analysis'))


@portfolio_bp.route('/api/portfolio/risk-preview', methods=['POST'])
@csrf.exempt
@login_required
def risk_preview():
    """Compute risk metrics for proposed weights without saving."""
    data = request.get_json()
    if not data or 'holdings' not in data:
        return jsonify({'error': 'Missing holdings'}), 400

    holdings_input = data['holdings']
    holding_objs = []
    for asset_id_str, weight in holdings_input.items():
        asset_id = int(asset_id_str)
        asset = db.session.get(Asset, asset_id)
        if not asset:
            continue
        w = Decimal(str(weight))
        if w > 0:
            holding_objs.append(Holding(
                asset_id=asset_id, symbol=asset.symbol,
                weight_pct=w, category=asset.category,
            ))

    price_histories = {}
    for h in holding_objs:
        cached = (
            MarketDataDaily.query
            .filter(MarketDataDaily.asset_id == h.asset_id)
            .order_by(MarketDataDaily.date.desc())
            .limit(90)
            .all()
        )
        if cached:
            price_histories[h.asset_id] = [row.price for row in reversed(cached)]

    # Always fetch BTC data for beta calculation, even if not in portfolio
    btc_asset_id = _get_btc_asset_id()
    _ensure_btc_in_price_histories(price_histories, btc_asset_id)

    metrics = RiskService.compute_all_metrics(
        holding_objs, price_histories=price_histories,
        btc_asset_id=btc_asset_id,
    )
    returns = RiskService.compute_all_returns(
        holding_objs, price_histories, btc_asset_id=btc_asset_id,
    )

    return jsonify({
        'top1_concentration': float(metrics.top1_concentration),
        'top3_concentration': float(metrics.top3_concentration),
        'hhi': float(metrics.hhi),
        'stablecoin_exposure': float(metrics.stablecoin_exposure),
        'sharpe_ratio': float(metrics.sharpe_ratio) if metrics.sharpe_ratio else None,
        'var_95': float(metrics.var_95) if metrics.var_95 else None,
        'portfolio_beta': float(metrics.portfolio_beta) if metrics.portfolio_beta else None,
        'diversification_score': float(metrics.diversification_score) if metrics.diversification_score else None,
        'interpretations': metrics.interpretations,
        'sector_exposure': {k: float(v) for k, v in metrics.sector_exposure.items()},
        'portfolio_return_1d': float(returns.portfolio_return_1d) if returns.portfolio_return_1d else None,
        'portfolio_return_7d': float(returns.portfolio_return_7d) if returns.portfolio_return_7d else None,
        'portfolio_return_30d': float(returns.portfolio_return_30d) if returns.portfolio_return_30d else None,
        'portfolio_return_90d': float(returns.portfolio_return_90d) if returns.portfolio_return_90d else None,
    })


@portfolio_bp.route('/portfolio/adjustments', methods=['GET', 'POST'])
@login_required
def adjustments():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'load_predefined':
            template_name = request.form.get('template_name')
            try:
                PortfolioService.load_predefined(current_user.id, template_name)
                flash(f'Loaded portfolio: {template_name}', 'success')
            except PortfolioError as e:
                flash(str(e), 'error')
            return redirect(url_for('portfolio.analysis'))

        elif action == 'update_allocations':
            portfolio_id = request.form.get('portfolio_id', type=int)
            portfolios = PortfolioService.get_user_portfolios(current_user.id)
            if not portfolios:
                flash('No portfolio to update.', 'error')
                return redirect(url_for('portfolio.adjustments'))

            if portfolio_id:
                portfolio = next((p for p in portfolios if p.id == portfolio_id), portfolios[0])
            else:
                portfolio = portfolios[0]

            new_holdings = {}
            normalize = request.form.get('normalize') == 'on'

            for key, value in request.form.items():
                if key.startswith('weight_'):
                    asset_id = int(key.replace('weight_', ''))
                    weight = Decimal(value) if value else Decimal('0')
                    if weight > 0:
                        new_holdings[asset_id] = weight

            if normalize:
                new_holdings = PortfolioService.normalize_weights(new_holdings)

            try:
                PortfolioService.update_allocations(
                    portfolio.id, current_user.id, new_holdings
                )
                flash('Portfolio updated successfully.', 'success')
            except PortfolioError as e:
                flash(str(e), 'error')

            return redirect(url_for('portfolio.analysis', portfolio_id=portfolio.id))

    # GET: if user has portfolios, redirect to unified analysis page
    portfolios = PortfolioService.get_user_portfolios(current_user.id)
    if portfolios:
        return redirect(url_for('portfolio.analysis'))

    templates = get_portfolio_templates()
    return render_template(
        'portfolio/adjustments.html',
        portfolios=portfolios,
        templates=templates,
    )
