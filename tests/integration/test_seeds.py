from app.extensions import db
from app.models import Asset
from app.seeds import load_assets, get_portfolio_templates


class TestSeedData:

    def test_load_assets_creates_all_assets(self, app):
        with app.app_context():
            load_assets()
            total = Asset.query.count()
            assert total >= 15

            btc = Asset.query.filter_by(symbol='BTC').first()
            assert btc is not None
            assert btc.coingecko_id == 'bitcoin'
            assert btc.category == 'Layer 1'

            usdc = Asset.query.filter_by(symbol='USDC').first()
            assert usdc is not None
            assert usdc.category == 'Stablecoin'

    def test_load_assets_is_idempotent(self, app):
        with app.app_context():
            load_assets()
            second_count = load_assets()
            assert second_count == 0

    def test_portfolio_templates_load_correctly(self):
        templates = get_portfolio_templates()
        assert len(templates) == 5

        names = [t['name'] for t in templates]
        assert 'BTC/ETH Core' in names
        assert 'Balanced Crypto Exposure' in names
        assert 'High-Risk Speculative' in names
        assert 'Top 10 Market Cap' in names
        assert 'DeFi Focused' in names

    def test_portfolio_template_weights_sum_to_100(self):
        templates = get_portfolio_templates()
        for template in templates:
            total = sum(h['weight_pct'] for h in template['holdings'])
            assert total == 100.0, f"{template['name']} weights sum to {total}"
