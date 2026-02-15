from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.models import Transaction
from app.models.market_data import MarketDataDaily
from app.services.portfolio_service import PortfolioService, PortfolioError
from app.services.risk_service import RiskService, Holding

history_bp = Blueprint('history', __name__)


def _compute_version_metrics(version):
    """Build holdings, fetch prices, compute risk + return metrics for a version."""
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

    btc_id = next((h.asset_id for h in holding_objs if h.symbol == 'BTC'), None)
    metrics = RiskService.compute_all_metrics(
        holding_objs, price_histories=price_histories, btc_asset_id=btc_id,
    )
    returns = RiskService.compute_all_returns(
        holding_objs, price_histories, btc_asset_id=btc_id,
    )
    return metrics, returns


@history_bp.route('/history')
@login_required
def index():
    transactions = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return render_template('history/index.html', transactions=transactions)


@history_bp.route('/history/version/<int:version_id>')
@login_required
def view_version(version_id):
    version = PortfolioService.get_version(version_id, current_user.id)
    if not version:
        flash('Version not found.', 'error')
        return redirect(url_for('history.index'))

    holdings = [{
        'symbol': h.asset.symbol,
        'name': h.asset.name,
        'weight': h.weight_pct,
        'category': h.asset.category,
    } for h in version.holdings]

    return render_template(
        'history/version.html', version=version, holdings=holdings,
    )


@history_bp.route('/history/compare/<int:version_a_id>/<int:version_b_id>')
@login_required
def compare(version_a_id, version_b_id):
    version_a = PortfolioService.get_version(version_a_id, current_user.id)
    version_b = PortfolioService.get_version(version_b_id, current_user.id)

    if not version_a or not version_b:
        flash('One or both versions not found.', 'error')
        return redirect(url_for('history.index'))

    map_a = {h.asset.symbol: {'weight': h.weight_pct, 'name': h.asset.name, 'category': h.asset.category}
             for h in version_a.holdings}
    map_b = {h.asset.symbol: {'weight': h.weight_pct, 'name': h.asset.name, 'category': h.asset.category}
             for h in version_b.holdings}

    all_symbols = sorted(set(map_a.keys()) | set(map_b.keys()))
    comparison = []
    for sym in all_symbols:
        a = map_a.get(sym)
        b = map_b.get(sym)
        w_a = float(a['weight']) if a else 0
        w_b = float(b['weight']) if b else 0
        delta = w_b - w_a
        status = 'unchanged'
        if w_a == 0:
            status = 'added'
        elif w_b == 0:
            status = 'removed'
        elif delta != 0:
            status = 'changed'
        comparison.append({
            'symbol': sym,
            'name': (a or b)['name'],
            'category': (a or b)['category'],
            'weight_a': w_a,
            'weight_b': w_b,
            'delta': delta,
            'status': status,
        })

    # Compute risk metrics for both versions
    metrics_a, returns_a = _compute_version_metrics(version_a)
    metrics_b, returns_b = _compute_version_metrics(version_b)

    def _metric_row(label, val_a, val_b, fmt='{}', lower_better=False):
        if val_a is None and val_b is None:
            return None
        a_str = fmt.format(float(val_a)) if val_a is not None else '---'
        b_str = fmt.format(float(val_b)) if val_b is not None else '---'
        delta = None
        improvement = None
        if val_a is not None and val_b is not None:
            delta = float(val_b) - float(val_a)
            if lower_better:
                improvement = 'better' if delta < 0 else ('worse' if delta > 0 else 'same')
            else:
                improvement = 'better' if delta > 0 else ('worse' if delta < 0 else 'same')
        return {'label': label, 'val_a': a_str, 'val_b': b_str,
                'delta': delta, 'improvement': improvement}

    risk_comparison = [r for r in [
        _metric_row('Top-1 Conc.', metrics_a.top1_concentration, metrics_b.top1_concentration, '{:.1f}%', lower_better=True),
        _metric_row('HHI', metrics_a.hhi, metrics_b.hhi, '{:.0f}', lower_better=True),
        _metric_row('Sharpe Ratio', metrics_a.sharpe_ratio, metrics_b.sharpe_ratio, '{:.4f}'),
        _metric_row('Beta vs BTC', metrics_a.portfolio_beta, metrics_b.portfolio_beta, '{:.4f}'),
        _metric_row('VaR (95%)', metrics_a.var_95, metrics_b.var_95, '{:.2f}%', lower_better=True),
        _metric_row('Diversification', metrics_a.diversification_score, metrics_b.diversification_score, '{:.1f}'),
        _metric_row('30D Return', returns_a.portfolio_return_30d if returns_a else None,
                     returns_b.portfolio_return_30d if returns_b else None, '{:.2f}%'),
    ] if r is not None]

    return render_template(
        'history/compare.html',
        version_a=version_a, version_b=version_b,
        comparison=comparison, risk_comparison=risk_comparison,
    )


@history_bp.route('/history/revert/<int:version_id>', methods=['POST'])
@login_required
def revert(version_id):
    version = PortfolioService.get_version(version_id, current_user.id)
    if not version:
        flash('Version not found.', 'error')
        return redirect(url_for('history.index'))

    try:
        new_version = PortfolioService.revert_to_version(
            version.portfolio_id, current_user.id, version_id
        )
        flash(f'Reverted to version {version.version_num}. New version: v{new_version.version_num}', 'success')
    except PortfolioError as e:
        flash(str(e), 'error')

    return redirect(url_for('portfolio.analysis', portfolio_id=version.portfolio_id))
