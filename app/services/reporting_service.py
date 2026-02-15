from app.extensions import db
from app.models import (
    User, Portfolio, PortfolioVersion, PortfolioHolding,
    Transaction, Asset,
)
from app.services.risk_service import RiskService, Holding
from collections import Counter


class ReportingService:

    @staticmethod
    def generate_user_report(user_id):
        portfolios = Portfolio.query.filter_by(user_id=user_id, is_active=True).all()
        if not portfolios:
            return {'has_portfolio': False}

        portfolio = portfolios[0]
        version = (
            PortfolioVersion.query
            .filter_by(portfolio_id=portfolio.id)
            .order_by(PortfolioVersion.version_num.desc())
            .first()
        )
        if not version:
            return {'has_portfolio': False}

        holdings = [
            Holding(
                asset_id=h.asset_id, symbol=h.asset.symbol,
                weight_pct=h.weight_pct, category=h.asset.category,
            )
            for h in version.holdings
        ]
        metrics = RiskService.compute_all_metrics(holdings)

        transactions = (
            Transaction.query
            .filter_by(user_id=user_id)
            .order_by(Transaction.created_at.desc())
            .limit(10)
            .all()
        )

        return {
            'has_portfolio': True,
            'portfolio_name': portfolio.name,
            'version_num': version.version_num,
            'holdings': [
                {'symbol': h.symbol, 'weight': float(h.weight_pct), 'category': h.category}
                for h in holdings
            ],
            'metrics': metrics,
            'recent_transactions': [
                {
                    'date': t.created_at.strftime('%Y-%m-%d %H:%M'),
                    'type': t.type,
                    'diff': t.diff_json,
                }
                for t in transactions
            ],
        }

    @staticmethod
    def generate_admin_report():
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_portfolios = Portfolio.query.count()

        sector_totals = {}
        template_counter = Counter()

        portfolios = Portfolio.query.all()
        for p in portfolios:
            version = (
                PortfolioVersion.query
                .filter_by(portfolio_id=p.id)
                .order_by(PortfolioVersion.version_num.desc())
                .first()
            )
            if not version:
                continue

            create_txn = Transaction.query.filter_by(
                portfolio_id=p.id, type='CREATE'
            ).first()
            if create_txn and create_txn.diff_json and 'template' in create_txn.diff_json:
                template_counter[create_txn.diff_json['template']] += 1

            for h in version.holdings:
                cat = h.asset.category
                sector_totals[cat] = sector_totals.get(cat, 0) + float(h.weight_pct)

        total_weight = sum(sector_totals.values()) or 1
        sector_pcts = {k: round(v / total_weight * 100, 1) for k, v in sector_totals.items()}

        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_portfolios': total_portfolios,
            'sector_exposure': sector_pcts,
            'popular_templates': template_counter.most_common(5),
        }
