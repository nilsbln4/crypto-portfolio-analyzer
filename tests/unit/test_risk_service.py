from decimal import Decimal

from app.services.risk_service import RiskService, Holding, RiskMetrics, VolContribution, ReturnMetrics


def _h(symbol, weight, category='Layer 1', asset_id=1):
    return Holding(asset_id=asset_id, symbol=symbol,
                   weight_pct=Decimal(str(weight)), category=category)


class TestConcentration:

    def test_top1_single_asset_returns_100(self):
        holdings = [_h('BTC', 100)]
        assert RiskService.concentration_top_n(holdings, 1) == Decimal('100')

    def test_top1_equal_weights(self):
        holdings = [_h('BTC', 25, asset_id=1), _h('ETH', 25, asset_id=2),
                    _h('SOL', 25, asset_id=3), _h('ADA', 25, asset_id=4)]
        assert RiskService.concentration_top_n(holdings, 1) == Decimal('25')

    def test_top3_sums_top_3_weights(self):
        holdings = [_h('BTC', 40, asset_id=1), _h('ETH', 30, asset_id=2),
                    _h('SOL', 20, asset_id=3), _h('ADA', 10, asset_id=4)]
        assert RiskService.concentration_top_n(holdings, 3) == Decimal('90')

    def test_top3_with_fewer_than_3_assets(self):
        holdings = [_h('BTC', 60, asset_id=1), _h('ETH', 40, asset_id=2)]
        assert RiskService.concentration_top_n(holdings, 3) == Decimal('100')


class TestHHI:

    def test_perfect_concentration_returns_10000(self):
        holdings = [_h('BTC', 100)]
        assert RiskService.hhi(holdings) == Decimal('10000.00')

    def test_two_assets_50_50_returns_5000(self):
        holdings = [_h('BTC', 50, asset_id=1), _h('ETH', 50, asset_id=2)]
        assert RiskService.hhi(holdings) == Decimal('5000.00')

    def test_equal_distribution_4_assets(self):
        holdings = [_h('BTC', 25, asset_id=i) for i in range(4)]
        assert RiskService.hhi(holdings) == Decimal('2500.00')


class TestVolatilityContribution:

    def test_zero_weight_produces_zero_contribution(self):
        holdings = [_h('BTC', 0)]
        prices = {1: [Decimal('100'), Decimal('105'), Decimal('102'), Decimal('108')]}
        results = RiskService.volatility_contributions(holdings, prices)
        assert len(results) == 1
        assert results[0].contribution == Decimal('0.0000')

    def test_contribution_proportional_to_weight(self):
        h1 = _h('BTC', 60, asset_id=1)
        h2 = _h('ETH', 30, asset_id=2)
        prices = {
            1: [Decimal(str(p)) for p in [100, 105, 102, 108, 110, 107]],
            2: [Decimal(str(p)) for p in [100, 105, 102, 108, 110, 107]],
        }
        results = RiskService.volatility_contributions([h1, h2], prices)
        assert results[0].contribution > results[1].contribution

    def test_insufficient_data_returns_empty(self):
        holdings = [_h('BTC', 100)]
        prices = {1: [Decimal('100')]}
        results = RiskService.volatility_contributions(holdings, prices)
        assert len(results) == 0

    def test_volatility_calculated_from_daily_returns(self):
        holdings = [_h('BTC', 100)]
        prices = {1: [Decimal(str(p)) for p in [100, 105, 102, 108, 110, 107, 112]]}
        results = RiskService.volatility_contributions(holdings, prices)
        assert len(results) == 1
        assert results[0].volatility > Decimal('0')


class TestStablecoinExposure:

    def test_no_stablecoins_returns_zero(self):
        holdings = [_h('BTC', 60, 'Layer 1'), _h('ETH', 40, 'Layer 1')]
        assert RiskService.stablecoin_exposure(holdings) == Decimal('0')

    def test_all_stablecoins_returns_100(self):
        holdings = [_h('USDT', 50, 'Stablecoin', 1), _h('USDC', 50, 'Stablecoin', 2)]
        assert RiskService.stablecoin_exposure(holdings) == Decimal('100')

    def test_mixed_portfolio(self):
        holdings = [
            _h('BTC', 60, 'Layer 1', 1),
            _h('ETH', 30, 'Layer 1', 2),
            _h('USDC', 10, 'Stablecoin', 3),
        ]
        assert RiskService.stablecoin_exposure(holdings) == Decimal('10')


class TestSectorExposure:

    def test_aggregates_weights_by_category(self):
        holdings = [
            _h('BTC', 40, 'Layer 1', 1),
            _h('ETH', 30, 'Layer 1', 2),
            _h('UNI', 20, 'DeFi', 3),
            _h('USDC', 10, 'Stablecoin', 4),
        ]
        result = RiskService.sector_exposure(holdings)
        assert result['Layer 1'] == Decimal('70')
        assert result['DeFi'] == Decimal('20')
        assert result['Stablecoin'] == Decimal('10')

    def test_sums_to_100(self):
        holdings = [
            _h('BTC', 50, 'Layer 1', 1),
            _h('UNI', 30, 'DeFi', 2),
            _h('USDC', 20, 'Stablecoin', 3),
        ]
        result = RiskService.sector_exposure(holdings)
        assert sum(result.values()) == Decimal('100')


class TestMaxDrawdown:

    def test_flat_prices_is_zero(self):
        prices = [Decimal('100')] * 10
        assert RiskService.max_drawdown(prices) == Decimal('0.00')

    def test_monotonic_increase_is_zero(self):
        prices = [Decimal(str(i)) for i in range(100, 111)]
        assert RiskService.max_drawdown(prices) == Decimal('0.00')

    def test_50pct_drop(self):
        prices = [Decimal('100'), Decimal('80'), Decimal('50'), Decimal('60')]
        assert RiskService.max_drawdown(prices) == Decimal('50.00')

    def test_recovery_after_drop(self):
        prices = [Decimal('100'), Decimal('70'), Decimal('120'), Decimal('60')]
        dd = RiskService.max_drawdown(prices)
        assert dd == Decimal('50.00')


class TestInterpretRisk:

    def test_high_concentration_warns(self):
        metrics = RiskMetrics(
            top1_concentration=Decimal('60'),
            top3_concentration=Decimal('90'),
            hhi=Decimal('4000'),
            volatility_contributions=[],
            stablecoin_exposure=Decimal('10'),
            sector_exposure={},
            max_drawdown=None,
        )
        result = RiskService.interpret_risk(metrics)
        assert any('concentration risk' in i.lower() for i in result)

    def test_high_stablecoin_notes_low_growth(self):
        metrics = RiskMetrics(
            top1_concentration=Decimal('30'),
            top3_concentration=Decimal('70'),
            hhi=Decimal('2000'),
            volatility_contributions=[],
            stablecoin_exposure=Decimal('60'),
            sector_exposure={},
            max_drawdown=None,
        )
        result = RiskService.interpret_risk(metrics)
        assert any('growth potential' in i.lower() for i in result)

    def test_high_volatility_warns(self):
        vol = VolContribution(
            asset_id=1, symbol='DOGE', weight_pct=Decimal('20'),
            volatility=Decimal('120'), contribution=Decimal('24'),
        )
        metrics = RiskMetrics(
            top1_concentration=Decimal('30'),
            top3_concentration=Decimal('70'),
            hhi=Decimal('2000'),
            volatility_contributions=[vol],
            stablecoin_exposure=Decimal('10'),
            sector_exposure={},
            max_drawdown=None,
        )
        result = RiskService.interpret_risk(metrics)
        assert any('volatility' in i.lower() for i in result)

    def test_moderate_portfolio_gets_neutral_message(self):
        metrics = RiskMetrics(
            top1_concentration=Decimal('30'),
            top3_concentration=Decimal('70'),
            hhi=Decimal('2000'),
            volatility_contributions=[],
            stablecoin_exposure=Decimal('10'),
            sector_exposure={},
            max_drawdown=Decimal('15'),
        )
        result = RiskService.interpret_risk(metrics)
        assert any('moderate' in i.lower() for i in result)


class TestComputeAllMetrics:

    def test_returns_complete_metrics(self):
        holdings = [
            _h('BTC', 60, 'Layer 1', 1),
            _h('ETH', 30, 'Layer 1', 2),
            _h('USDC', 10, 'Stablecoin', 3),
        ]
        prices = {
            1: [Decimal(str(p)) for p in [100, 105, 102, 108, 110, 107, 112]],
            2: [Decimal(str(p)) for p in [50, 52, 48, 55, 53, 51, 54]],
        }
        metrics = RiskService.compute_all_metrics(holdings, price_histories=prices)
        assert metrics.top1_concentration == Decimal('60')
        assert metrics.top3_concentration == Decimal('100')
        assert metrics.stablecoin_exposure == Decimal('10')
        assert 'Layer 1' in metrics.sector_exposure
        assert len(metrics.interpretations) > 0


class TestCorrelationMatrix:
    def test_identical_series_returns_1(self):
        prices = {1: [Decimal(str(x)) for x in [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 112]],
                  2: [Decimal(str(x)) for x in [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 110, 112]]}
        result = RiskService.compute_correlation_matrix(prices)
        assert result is not None
        assert result[(1, 2)] == Decimal('1.0')

    def test_single_asset_returns_none(self):
        prices = {1: [Decimal(str(x)) for x in range(100, 200)]}
        result = RiskService.compute_correlation_matrix(prices)
        assert result is None

    def test_insufficient_data_skips_pair(self):
        prices = {1: [Decimal('100'), Decimal('101')],
                  2: [Decimal('200'), Decimal('201')]}
        result = RiskService.compute_correlation_matrix(prices)
        assert result is None


class TestPortfolioBeta:
    def test_btc_only_returns_approx_1(self):
        prices = [Decimal(str(x)) for x in [100, 102, 99, 103, 101, 105, 100, 104, 98, 106, 103, 107]]
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.portfolio_beta_vs_btc(holdings, {1: prices}, btc_asset_id=1)
        assert result is not None
        assert abs(result - Decimal('1.0')) < Decimal('0.01')

    def test_no_btc_data_returns_none(self):
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.portfolio_beta_vs_btc(holdings, {}, btc_asset_id=1)
        assert result is None


class TestSharpeRatio:
    def test_returns_decimal(self):
        # Steadily increasing prices -> positive returns
        prices = {1: [Decimal(str(100 + i * 0.5)) for i in range(60)]}
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.compute_sharpe_ratio(holdings, prices)
        assert result is not None
        assert isinstance(result, Decimal)

    def test_insufficient_data_returns_none(self):
        prices = {1: [Decimal('100'), Decimal('101'), Decimal('102')]}
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.compute_sharpe_ratio(holdings, prices)
        assert result is None


class TestValueAtRisk:
    def test_returns_positive_decimal(self):
        # Volatile prices
        import random
        random.seed(42)
        prices = {1: [Decimal(str(100 + random.gauss(0, 5))) for _ in range(60)]}
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.compute_value_at_risk(holdings, prices)
        assert result is not None
        assert isinstance(result, Decimal)

    def test_insufficient_data_returns_none(self):
        prices = {1: [Decimal('100'), Decimal('101')]}
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.compute_value_at_risk(holdings, prices)
        assert result is None


class TestDiversificationScore:
    def test_single_asset_scores_low(self):
        holdings = [Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('100'), category='Layer 1')]
        result = RiskService.compute_diversification_score(holdings, {})
        assert result is not None
        assert result < Decimal('35')

    def test_many_equal_assets_scores_higher(self):
        holdings = [
            Holding(asset_id=i, symbol=f'A{i}', weight_pct=Decimal('10'), category='Layer 1')
            for i in range(1, 11)
        ]
        result = RiskService.compute_diversification_score(holdings, {})
        assert result > Decimal('50')

    def test_score_between_0_and_100(self):
        holdings = [
            Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('60'), category='Layer 1'),
            Holding(asset_id=2, symbol='ETH', weight_pct=Decimal('40'), category='Layer 1'),
        ]
        result = RiskService.compute_diversification_score(holdings, {})
        assert Decimal('0') <= result <= Decimal('100')


class TestComputePeriodReturn:
    def test_positive_return(self):
        prices = [Decimal('100'), Decimal('110'), Decimal('120')]
        result = RiskService.compute_period_return(prices, 3)
        assert result == Decimal('20.00')

    def test_negative_return(self):
        prices = [Decimal('100'), Decimal('90'), Decimal('80')]
        result = RiskService.compute_period_return(prices, 3)
        assert result == Decimal('-20.00')

    def test_flat_return(self):
        prices = [Decimal('100'), Decimal('100'), Decimal('100')]
        result = RiskService.compute_period_return(prices, 3)
        assert result == Decimal('0.00')

    def test_insufficient_data_returns_none(self):
        prices = [Decimal('100')]
        result = RiskService.compute_period_return(prices, 1)
        assert result is None

    def test_empty_prices_returns_none(self):
        result = RiskService.compute_period_return([], 7)
        assert result is None

    def test_subset_of_longer_series(self):
        prices = [Decimal('100'), Decimal('110'), Decimal('120'), Decimal('130'), Decimal('140')]
        result = RiskService.compute_period_return(prices, 3)
        # Last 3 prices: 120, 130, 140 -> (140-120)/120 * 100 = 16.67
        assert result == Decimal('16.67')


class TestComputePortfolioReturn:
    def test_weighted_return(self):
        holdings = [
            _h('BTC', 60, asset_id=1),
            _h('ETH', 40, asset_id=2),
        ]
        prices = {
            1: [Decimal('100'), Decimal('110')],  # +10%
            2: [Decimal('100'), Decimal('120')],   # +20%
        }
        result = RiskService.compute_portfolio_return(holdings, prices, 2)
        # 0.6 * 10 + 0.4 * 20 = 14
        assert result == Decimal('14.00')

    def test_missing_price_data(self):
        holdings = [
            _h('BTC', 60, asset_id=1),
            _h('ETH', 40, asset_id=2),
        ]
        prices = {1: [Decimal('100'), Decimal('110')]}
        result = RiskService.compute_portfolio_return(holdings, prices, 2)
        assert result is not None  # Still computes with available data

    def test_no_data_returns_none(self):
        holdings = [_h('BTC', 100, asset_id=1)]
        result = RiskService.compute_portfolio_return(holdings, {}, 7)
        assert result is None


class TestComputeAllReturns:
    def test_returns_all_periods(self):
        # Create enough price data points for 90 days
        prices_btc = [Decimal(str(100 + i * 0.5)) for i in range(91)]
        prices_eth = [Decimal(str(50 + i * 0.3)) for i in range(91)]
        holdings = [
            _h('BTC', 60, asset_id=1),
            _h('ETH', 40, asset_id=2),
        ]
        prices = {1: prices_btc, 2: prices_eth}
        result = RiskService.compute_all_returns(holdings, prices, btc_asset_id=1)
        assert isinstance(result, ReturnMetrics)
        assert result.portfolio_return_1d is not None
        assert result.portfolio_return_7d is not None
        assert result.portfolio_return_30d is not None
        assert result.portfolio_return_90d is not None

    def test_benchmark_return(self):
        prices_btc = [Decimal(str(100 + i)) for i in range(31)]
        holdings = [_h('BTC', 100, asset_id=1)]
        prices = {1: prices_btc}
        result = RiskService.compute_all_returns(holdings, prices, btc_asset_id=1)
        assert result.benchmark_return_30d is not None
        assert result.benchmark_return_30d > Decimal('0')

    def test_per_asset_returns_populated(self):
        prices = {
            1: [Decimal(str(100 + i)) for i in range(31)],
            2: [Decimal(str(50 + i * 0.5)) for i in range(31)],
        }
        holdings = [
            _h('BTC', 60, asset_id=1),
            _h('ETH', 40, asset_id=2),
        ]
        result = RiskService.compute_all_returns(holdings, prices, btc_asset_id=1)
        assert len(result.per_asset_returns) == 2
        assert result.per_asset_returns[0]['symbol'] == 'BTC'
        assert result.per_asset_returns[0]['return_30d'] is not None

    def test_no_price_data(self):
        holdings = [_h('BTC', 100, asset_id=1)]
        result = RiskService.compute_all_returns(holdings, {})
        assert result.portfolio_return_1d is None
        assert result.portfolio_return_30d is None
        assert result.benchmark_return_30d is None
