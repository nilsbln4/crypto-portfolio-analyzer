import logging
from decimal import Decimal

from app.extensions import db
from app.models.asset import Asset
from app.models.portfolio import Portfolio, PortfolioVersion, PortfolioHolding
from app.models.transaction import Transaction
from app.seeds import get_portfolio_templates

logger = logging.getLogger(__name__)


class PortfolioError(Exception):
    pass


class PortfolioService:

    @staticmethod
    def load_predefined(user_id, template_name):
        templates = get_portfolio_templates()
        template = next((t for t in templates if t['name'] == template_name), None)
        if not template:
            raise PortfolioError(f'Unknown template: {template_name}')

        portfolio = Portfolio(user_id=user_id, name=template_name)
        db.session.add(portfolio)
        db.session.flush()

        version = PortfolioVersion(portfolio_id=portfolio.id, version_num=1)
        db.session.add(version)
        db.session.flush()

        for item in template['holdings']:
            asset = Asset.query.filter_by(symbol=item['symbol']).first()
            if not asset:
                raise PortfolioError(f'Unknown asset: {item["symbol"]}')
            holding = PortfolioHolding(
                version_id=version.id,
                asset_id=asset.id,
                weight_pct=Decimal(str(item['weight_pct'])),
            )
            db.session.add(holding)

        txn = Transaction(
            user_id=user_id, portfolio_id=portfolio.id,
            version_id=version.id, type='CREATE',
            diff_json={'action': 'load_predefined', 'template': template_name},
        )
        db.session.add(txn)
        db.session.commit()

        logger.info('User %d loaded predefined portfolio: %s', user_id, template_name)
        return portfolio

    @staticmethod
    def update_allocations(portfolio_id, user_id, new_holdings):
        portfolio = PortfolioService.get_portfolio_for_user(user_id, portfolio_id)

        total = sum(new_holdings.values())
        if total != Decimal('100'):
            raise PortfolioError(
                f'Weights must sum to 100%, got {total}%'
            )

        for weight in new_holdings.values():
            if weight < 0:
                raise PortfolioError('Weights cannot be negative')

        current_version = PortfolioService.get_active_version(portfolio_id)
        new_version_num = (current_version.version_num + 1) if current_version else 1

        new_version = PortfolioVersion(
            portfolio_id=portfolio_id, version_num=new_version_num
        )
        db.session.add(new_version)
        db.session.flush()

        for asset_id, weight in new_holdings.items():
            if weight > 0:
                holding = PortfolioHolding(
                    version_id=new_version.id,
                    asset_id=asset_id,
                    weight_pct=weight,
                )
                db.session.add(holding)

        diff = PortfolioService._compute_diff(current_version, new_holdings)
        txn = Transaction(
            user_id=user_id, portfolio_id=portfolio_id,
            version_id=new_version.id, type='MODIFY',
            diff_json=diff,
        )
        db.session.add(txn)
        db.session.commit()

        logger.info('Portfolio %d updated to version %d', portfolio_id, new_version_num)
        return new_version

    @staticmethod
    def normalize_weights(holdings):
        total = sum(holdings.values())
        if total == 0:
            return holdings
        factor = Decimal('100') / total
        return {
            asset_id: (weight * factor).quantize(Decimal('0.001'))
            for asset_id, weight in holdings.items()
        }

    @staticmethod
    def get_active_version(portfolio_id):
        return (
            PortfolioVersion.query
            .filter_by(portfolio_id=portfolio_id)
            .order_by(PortfolioVersion.version_num.desc())
            .first()
        )

    @staticmethod
    def get_portfolio_for_user(user_id, portfolio_id):
        portfolio = db.session.get(Portfolio, portfolio_id)
        if not portfolio or portfolio.user_id != user_id:
            raise PortfolioError('Portfolio not found')
        return portfolio

    @staticmethod
    def get_user_portfolios(user_id):
        return Portfolio.query.filter_by(user_id=user_id, is_active=True).all()

    @staticmethod
    def _compute_diff(old_version, new_holdings):
        old_map = {}
        if old_version:
            for h in old_version.holdings:
                old_map[h.asset_id] = h.weight_pct

        changes = []
        all_ids = set(old_map.keys()) | set(new_holdings.keys())
        for asset_id in all_ids:
            old_w = float(old_map.get(asset_id, 0))
            new_w = float(new_holdings.get(asset_id, 0))
            if old_w != new_w:
                asset = db.session.get(Asset, asset_id)
                changes.append({
                    'asset': asset.symbol if asset else str(asset_id),
                    'from_weight': old_w,
                    'to_weight': new_w,
                })

        return {'changes': changes}

    @staticmethod
    def create_portfolio(user_id, name):
        """Create an empty named portfolio."""
        if not name or not name.strip():
            raise PortfolioError('Portfolio name is required')
        if len(name.strip()) > 100:
            raise PortfolioError('Portfolio name must be 100 characters or fewer')
        portfolio = Portfolio(user_id=user_id, name=name.strip())
        db.session.add(portfolio)
        db.session.commit()
        return portfolio

    @staticmethod
    def rename_portfolio(portfolio_id, user_id, new_name):
        """Rename an existing portfolio."""
        portfolio = PortfolioService.get_portfolio_for_user(user_id, portfolio_id)
        if not new_name or not new_name.strip():
            raise PortfolioError('Portfolio name is required')
        portfolio.name = new_name.strip()
        db.session.commit()
        return portfolio

    @staticmethod
    def delete_portfolio(portfolio_id, user_id):
        """Soft-delete a portfolio."""
        portfolio = PortfolioService.get_portfolio_for_user(user_id, portfolio_id)
        portfolio.is_active = False
        txn = Transaction(
            user_id=user_id, portfolio_id=portfolio.id,
            version_id=None, type='DELETE',
            diff_json={'action': 'delete', 'portfolio_name': portfolio.name},
        )
        db.session.add(txn)
        db.session.commit()
        return portfolio

    @staticmethod
    def revert_to_version(portfolio_id, user_id, target_version_id):
        """Revert portfolio to a previous version by copying its holdings into a new version."""
        portfolio = PortfolioService.get_portfolio_for_user(user_id, portfolio_id)
        target_version = db.session.get(PortfolioVersion, target_version_id)
        if not target_version or target_version.portfolio_id != portfolio.id:
            raise PortfolioError('Version not found for this portfolio')

        current_version = PortfolioService.get_active_version(portfolio_id)
        new_version_num = (current_version.version_num + 1) if current_version else 1

        new_version = PortfolioVersion(
            portfolio_id=portfolio.id, version_num=new_version_num
        )
        db.session.add(new_version)
        db.session.flush()

        for h in target_version.holdings:
            holding = PortfolioHolding(
                version_id=new_version.id,
                asset_id=h.asset_id,
                weight_pct=h.weight_pct,
            )
            db.session.add(holding)

        txn = Transaction(
            user_id=user_id, portfolio_id=portfolio.id,
            version_id=new_version.id, type='REVERT',
            diff_json={
                'action': 'revert',
                'from_version': current_version.version_num if current_version else None,
                'to_version': target_version.version_num,
            },
        )
        db.session.add(txn)
        db.session.commit()

        logger.info(
            'Portfolio %d reverted to version %d (new version %d)',
            portfolio_id, target_version.version_num, new_version_num,
        )
        return new_version

    @staticmethod
    def get_version(version_id, user_id):
        """Get a specific version, verifying ownership."""
        version = db.session.get(PortfolioVersion, version_id)
        if not version or version.portfolio.user_id != user_id:
            return None
        return version
