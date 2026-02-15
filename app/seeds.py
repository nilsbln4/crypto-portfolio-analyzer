import json
import os

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Asset


SEEDS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'seeds')


def load_assets():
    with open(os.path.join(SEEDS_DIR, 'assets.json')) as f:
        assets_data = json.load(f)

    created = 0
    for item in assets_data:
        exists = Asset.query.filter_by(coingecko_id=item['coingecko_id']).first()
        if not exists:
            asset = Asset(**item)
            db.session.add(asset)
            created += 1

    db.session.commit()
    return created


def get_portfolio_templates():
    with open(os.path.join(SEEDS_DIR, 'portfolios.json')) as f:
        return json.load(f)


@click.command('seed')
@with_appcontext
def seed_command():
    """Seed the database with assets and portfolio templates."""
    db.create_all()
    count = load_assets()
    click.echo(f'Seeded {count} assets.')


@click.command('seed-history')
@with_appcontext
def seed_history_command():
    """Fetch 90-day historical price data for all assets."""
    import os
    from app.services.coingecko_client import CoinGeckoClient
    from app.services.market_data_service import MarketDataService

    client = CoinGeckoClient(api_key=os.environ.get('COINGECKO_API_KEY', ''))
    service = MarketDataService(client)
    assets = Asset.query.all()

    for i, asset in enumerate(assets):
        click.echo(f'[{i+1}/{len(assets)}] Fetching {asset.symbol}...')
        try:
            service.get_historical_prices(asset.id, days=90)
        except Exception as e:
            click.echo(f'  Error: {e}')

    click.echo('Done.')


@click.command('promote-admin')
@click.argument('email')
@with_appcontext
def promote_admin_command(email):
    """Promote a user to ADMIN role. Usage: flask promote-admin user@example.com"""
    from app.models.user import User
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        click.echo(f'Error: No user found with email "{email}".')
        return
    if user.role == 'ADMIN':
        click.echo(f'{email} is already an admin.')
        return
    user.role = 'ADMIN'
    db.session.commit()
    click.echo(f'Promoted {email} to ADMIN.')


def init_app(app):
    app.cli.add_command(seed_command)
    app.cli.add_command(seed_history_command)
    app.cli.add_command(promote_admin_command)
