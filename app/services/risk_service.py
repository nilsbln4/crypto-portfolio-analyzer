from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass
class Holding:
    asset_id: int
    symbol: str
    weight_pct: Decimal
    category: str


@dataclass
class VolContribution:
    asset_id: int
    symbol: str
    weight_pct: Decimal
    volatility: Decimal
    contribution: Decimal


@dataclass
class RiskMetrics:
    top1_concentration: Decimal
    top3_concentration: Decimal
    hhi: Decimal
    volatility_contributions: list[VolContribution]
    stablecoin_exposure: Decimal
    sector_exposure: dict[str, Decimal]
    max_drawdown: Optional[Decimal]
    interpretations: list[str] = field(default_factory=list)
    # Phase 3: Extended Risk Metrics
    correlation_matrix: Optional[dict] = None
    portfolio_beta: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    var_95: Optional[Decimal] = None
    diversification_score: Optional[Decimal] = None


@dataclass
class ReturnMetrics:
    portfolio_return_1d: Optional[Decimal]
    portfolio_return_7d: Optional[Decimal]
    portfolio_return_30d: Optional[Decimal]
    portfolio_return_90d: Optional[Decimal]
    benchmark_return_30d: Optional[Decimal]
    per_asset_returns: list[dict] = field(default_factory=list)


class RiskService:
    """Pure calculation functions for portfolio risk metrics. No DB, no API."""

    @staticmethod
    def concentration_top_n(holdings, n):
        weights = sorted(
            [h.weight_pct for h in holdings], reverse=True
        )
        return sum(weights[:n], Decimal('0'))

    @staticmethod
    def hhi(holdings):
        return sum(
            (h.weight_pct ** 2) for h in holdings
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def volatility_contributions(holdings, price_histories):
        results = []
        for h in holdings:
            prices = price_histories.get(h.asset_id, [])
            vol = RiskService._calculate_volatility(prices)
            if vol is None:
                continue
            contribution = h.weight_pct * vol / Decimal('100')
            results.append(VolContribution(
                asset_id=h.asset_id,
                symbol=h.symbol,
                weight_pct=h.weight_pct,
                volatility=vol.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                contribution=contribution.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
            ))
        return results

    @staticmethod
    def stablecoin_exposure(holdings):
        stablecoin_categories = {'Stablecoin'}
        return sum(
            (h.weight_pct for h in holdings if h.category in stablecoin_categories),
            Decimal('0'),
        )

    @staticmethod
    def sector_exposure(holdings):
        sectors = {}
        for h in holdings:
            sectors[h.category] = sectors.get(h.category, Decimal('0')) + h.weight_pct
        return sectors

    @staticmethod
    def max_drawdown(prices):
        if not prices or len(prices) < 2:
            return Decimal('0')

        peak = prices[0]
        max_dd = Decimal('0')

        for price in prices[1:]:
            if price > peak:
                peak = price
            dd = (peak - price) / peak * Decimal('100')
            if dd > max_dd:
                max_dd = dd

        return max_dd.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def interpret_risk(metrics):
        interpretations = []

        if metrics.top1_concentration >= Decimal('50'):
            interpretations.append(
                'High concentration risk: a single asset makes up '
                f'{metrics.top1_concentration}% of the portfolio.'
            )

        if metrics.hhi >= Decimal('5000'):
            interpretations.append(
                'Portfolio is highly concentrated (HHI >= 5000). '
                'Consider diversifying across more assets.'
            )

        if metrics.stablecoin_exposure >= Decimal('50'):
            interpretations.append(
                f'Stablecoin exposure is {metrics.stablecoin_exposure}%. '
                'This limits growth potential but reduces volatility.'
            )
        elif metrics.stablecoin_exposure == Decimal('0'):
            interpretations.append(
                'No stablecoin allocation. The portfolio is fully exposed to market volatility.'
            )

        high_vol = [v for v in metrics.volatility_contributions
                    if v.volatility >= Decimal('80')]
        if high_vol:
            symbols = ', '.join(v.symbol for v in high_vol)
            interpretations.append(
                f'High annualized volatility detected in: {symbols}. '
                'These assets are major risk drivers.'
            )

        if metrics.max_drawdown and metrics.max_drawdown >= Decimal('30'):
            interpretations.append(
                f'Historical max drawdown of {metrics.max_drawdown}% observed. '
                'The portfolio has experienced significant downturns.'
            )

        # Phase 3: Extended metric interpretations
        if metrics.portfolio_beta is not None and metrics.portfolio_beta > Decimal('1.2'):
            interpretations.append(
                f'Portfolio beta of {metrics.portfolio_beta} vs BTC indicates '
                'amplified market exposure.'
            )

        if metrics.sharpe_ratio is not None and metrics.sharpe_ratio < Decimal('0'):
            interpretations.append(
                'Negative Sharpe ratio suggests returns are below the risk-free rate.'
            )

        if metrics.diversification_score is not None and metrics.diversification_score < Decimal('30'):
            interpretations.append(
                f'Diversification score of {metrics.diversification_score}/100 is low. '
                'Consider adding uncorrelated assets.'
            )

        if metrics.var_95 is not None and metrics.var_95 > Decimal('5'):
            interpretations.append(
                f'Daily Value at Risk of {metrics.var_95}% at 95% confidence '
                'indicates significant downside potential.'
            )

        if not interpretations:
            interpretations.append(
                'Portfolio risk metrics are within moderate ranges.'
            )

        return interpretations

    @staticmethod
    def compute_all_metrics(holdings, price_histories=None, portfolio_prices=None,
                            btc_asset_id=None):
        if price_histories is None:
            price_histories = {}

        top1 = RiskService.concentration_top_n(holdings, 1)
        top3 = RiskService.concentration_top_n(holdings, 3)
        hhi_val = RiskService.hhi(holdings)
        vol_contribs = RiskService.volatility_contributions(holdings, price_histories)
        stable_exp = RiskService.stablecoin_exposure(holdings)
        sector_exp = RiskService.sector_exposure(holdings)
        drawdown = RiskService.max_drawdown(portfolio_prices) if portfolio_prices else None

        # Phase 3: Extended risk metrics
        corr_matrix = None
        beta = None
        sharpe = None
        var_95 = None
        div_score = None

        if price_histories:
            corr_matrix = RiskService.compute_correlation_matrix(price_histories)
            sharpe = RiskService.compute_sharpe_ratio(holdings, price_histories)
            var_95 = RiskService.compute_value_at_risk(holdings, price_histories)
            div_score = RiskService.compute_diversification_score(holdings, price_histories)

            if btc_asset_id is not None:
                beta = RiskService.portfolio_beta_vs_btc(
                    holdings, price_histories, btc_asset_id
                )

        metrics = RiskMetrics(
            top1_concentration=top1,
            top3_concentration=top3,
            hhi=hhi_val,
            volatility_contributions=vol_contribs,
            stablecoin_exposure=stable_exp,
            sector_exposure=sector_exp,
            max_drawdown=drawdown,
            correlation_matrix=corr_matrix,
            portfolio_beta=beta,
            sharpe_ratio=sharpe,
            var_95=var_95,
            diversification_score=div_score,
        )
        metrics.interpretations = RiskService.interpret_risk(metrics)
        return metrics

    @staticmethod
    def _daily_returns(prices):
        """Convert price series to daily returns."""
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] == 0:
                continue
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
        return returns

    @staticmethod
    def _calculate_volatility(prices):
        if len(prices) < 2:
            return None

        returns = RiskService._daily_returns(prices)

        if len(returns) < 2:
            return None

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = variance.sqrt()
        annualized = daily_vol * Decimal('365').sqrt()

        return annualized * Decimal('100')

    @staticmethod
    def compute_correlation_matrix(price_histories):
        """
        Compute pairwise Pearson correlation from daily returns.
        price_histories: dict {asset_id: [Decimal prices]}
        Returns: dict {(asset_id_a, asset_id_b): Decimal correlation} or None
        """
        if len(price_histories) < 2:
            return None

        # Convert each to daily returns
        returns_map = {}
        for aid, prices in price_histories.items():
            rets = RiskService._daily_returns(prices)
            if len(rets) >= 10:
                returns_map[aid] = rets

        if len(returns_map) < 2:
            return None

        result = {}
        ids = sorted(returns_map.keys())
        for i, aid_a in enumerate(ids):
            for aid_b in ids[i:]:
                if aid_a == aid_b:
                    result[(aid_a, aid_b)] = Decimal('1.0')
                    continue
                rets_a = returns_map[aid_a]
                rets_b = returns_map[aid_b]
                min_len = min(len(rets_a), len(rets_b))
                if min_len < 10:
                    continue
                # Use last min_len returns
                ra = [float(r) for r in rets_a[-min_len:]]
                rb = [float(r) for r in rets_b[-min_len:]]
                # Pearson correlation
                n = min_len
                sum_a = sum(ra)
                sum_b = sum(rb)
                sum_ab = sum(a * b for a, b in zip(ra, rb))
                sum_a2 = sum(a * a for a in ra)
                sum_b2 = sum(b * b for b in rb)
                num = n * sum_ab - sum_a * sum_b
                den = ((n * sum_a2 - sum_a**2) * (n * sum_b2 - sum_b**2)) ** 0.5
                if den == 0:
                    corr = Decimal('0')
                else:
                    corr = Decimal(str(round(num / den, 4)))
                result[(aid_a, aid_b)] = corr
                result[(aid_b, aid_a)] = corr
        return result

    @staticmethod
    def portfolio_beta_vs_btc(holdings, price_histories, btc_asset_id):
        """
        Portfolio beta = Cov(portfolio_returns, btc_returns) / Var(btc_returns)
        """
        if btc_asset_id not in price_histories:
            return None

        btc_prices = price_histories[btc_asset_id]
        btc_returns = RiskService._daily_returns(btc_prices)
        if len(btc_returns) < 10:
            return None

        # Compute weighted portfolio daily returns
        # Need all holdings to have price data with same length
        portfolio_returns = []
        n = len(btc_returns)

        for day_idx in range(n):
            daily_portfolio_return = Decimal('0')
            total_weight = Decimal('0')
            for h in holdings:
                if h.asset_id not in price_histories:
                    continue
                rets = RiskService._daily_returns(price_histories[h.asset_id])
                if day_idx < len(rets):
                    daily_portfolio_return += (h.weight_pct / 100) * rets[day_idx]
                    total_weight += h.weight_pct / 100
            if total_weight > 0:
                portfolio_returns.append(float(daily_portfolio_return))
            else:
                portfolio_returns.append(0.0)

        if len(portfolio_returns) < 10:
            return None

        btc_r = [float(r) for r in btc_returns[-len(portfolio_returns):]]
        port_r = portfolio_returns[-len(btc_r):]

        n = len(btc_r)
        mean_btc = sum(btc_r) / n
        mean_port = sum(port_r) / n
        cov = sum((p - mean_port) * (b - mean_btc) for p, b in zip(port_r, btc_r)) / n
        var_btc = sum((b - mean_btc) ** 2 for b in btc_r) / n

        if var_btc == 0:
            return None

        beta = cov / var_btc
        return Decimal(str(round(beta, 4)))

    @staticmethod
    def compute_sharpe_ratio(holdings, price_histories, risk_free_rate=Decimal('0.04')):
        """
        Annualized Sharpe = (annualized_return - risk_free_rate) / annualized_vol
        """
        if not price_histories:
            return None

        # Compute weighted portfolio daily returns
        all_returns = []
        max_days = max(len(RiskService._daily_returns(p)) for p in price_histories.values())

        for day_idx in range(max_days):
            daily_return = Decimal('0')
            total_weight = Decimal('0')
            for h in holdings:
                if h.asset_id not in price_histories:
                    continue
                rets = RiskService._daily_returns(price_histories[h.asset_id])
                if day_idx < len(rets):
                    daily_return += (h.weight_pct / 100) * rets[day_idx]
                    total_weight += h.weight_pct / 100
            if total_weight > 0:
                all_returns.append(daily_return)

        if len(all_returns) < 20:
            return None

        # Annualize
        daily_mean = sum(all_returns) / len(all_returns)
        daily_var = sum((r - daily_mean) ** 2 for r in all_returns) / len(all_returns)
        # Use float for sqrt
        daily_vol = Decimal(str(float(daily_var) ** 0.5))

        annualized_return = daily_mean * 365
        annualized_vol = daily_vol * Decimal(str(365 ** 0.5))

        if annualized_vol == 0:
            return None

        sharpe = (annualized_return - risk_free_rate) / annualized_vol
        return Decimal(str(round(float(sharpe), 4)))

    @staticmethod
    def compute_value_at_risk(holdings, price_histories, confidence=Decimal('0.95')):
        """
        Parametric VaR: VaR = -(mean - z * vol) as a daily percentage.
        z for 95% = 1.645
        Returns a positive Decimal representing the potential daily loss percentage.
        """
        if not price_histories:
            return None

        all_returns = []
        max_days = max(len(RiskService._daily_returns(p)) for p in price_histories.values())

        for day_idx in range(max_days):
            daily_return = Decimal('0')
            total_weight = Decimal('0')
            for h in holdings:
                if h.asset_id not in price_histories:
                    continue
                rets = RiskService._daily_returns(price_histories[h.asset_id])
                if day_idx < len(rets):
                    daily_return += (h.weight_pct / 100) * rets[day_idx]
                    total_weight += h.weight_pct / 100
            if total_weight > 0:
                all_returns.append(daily_return)

        if len(all_returns) < 20:
            return None

        daily_mean = sum(all_returns) / len(all_returns)
        daily_var = sum((r - daily_mean) ** 2 for r in all_returns) / len(all_returns)
        daily_vol = Decimal(str(float(daily_var) ** 0.5))

        z_score = Decimal('1.645')  # 95% confidence
        var = -(daily_mean - z_score * daily_vol)
        # Return as percentage, positive value
        return Decimal(str(round(float(var * 100), 4)))

    @staticmethod
    def compute_diversification_score(holdings, price_histories):
        """
        Composite score 0-100 based on:
        - Number of assets (0-30 points, diminishing after 5)
        - Average pairwise correlation (0-40 points, lower = better)
        - Weight entropy (0-30 points, more equal = better)
        """
        import math

        if not holdings:
            return Decimal('0')

        n_assets = len([h for h in holdings if h.weight_pct > 0])

        # Asset count score (0-30): min(n, 10) / 10 * 30
        asset_score = min(n_assets, 10) / 10 * 30

        # Correlation score (0-40): need price data
        corr_score = 20  # default if no correlation data
        if price_histories and len(price_histories) >= 2:
            corr_matrix = RiskService.compute_correlation_matrix(price_histories)
            if corr_matrix:
                # Average absolute correlation (excluding self-correlation)
                pairs = [(k, v) for k, v in corr_matrix.items() if k[0] < k[1]]
                if pairs:
                    avg_corr = sum(abs(float(v)) for _, v in pairs) / len(pairs)
                    # Lower correlation = higher score
                    corr_score = (1 - avg_corr) * 40

        # Weight entropy score (0-30)
        weights = [float(h.weight_pct) / 100 for h in holdings if h.weight_pct > 0]
        if weights and n_assets > 1:
            entropy = -sum(w * math.log(w) for w in weights if w > 0)
            max_entropy = math.log(n_assets)
            entropy_ratio = entropy / max_entropy if max_entropy > 0 else 0
            entropy_score = entropy_ratio * 30
        else:
            entropy_score = 0

        total = asset_score + corr_score + entropy_score
        return Decimal(str(round(min(max(total, 0), 100), 1)))

    @staticmethod
    def compute_period_return(prices, days):
        """Compute simple return over the last N prices: (last - first) / first * 100."""
        if not prices or len(prices) < 2:
            return None
        subset = prices[-days:] if len(prices) >= days else prices
        if len(subset) < 2 or subset[0] == 0:
            return None
        ret = (subset[-1] - subset[0]) / subset[0] * Decimal('100')
        return ret.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def compute_portfolio_return(holdings, price_histories, days):
        """Weighted sum of per-asset period returns."""
        total_return = Decimal('0')
        total_weight = Decimal('0')
        for h in holdings:
            prices = price_histories.get(h.asset_id)
            if not prices:
                continue
            asset_return = RiskService.compute_period_return(prices, days)
            if asset_return is None:
                continue
            total_return += (h.weight_pct / 100) * asset_return
            total_weight += h.weight_pct / 100
        if total_weight == 0:
            return None
        return total_return.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def compute_all_returns(holdings, price_histories, btc_asset_id=None):
        """Compute portfolio returns, benchmark return, and per-asset returns."""
        ret_1d = RiskService.compute_portfolio_return(holdings, price_histories, 2)
        ret_7d = RiskService.compute_portfolio_return(holdings, price_histories, 7)
        ret_30d = RiskService.compute_portfolio_return(holdings, price_histories, 30)
        ret_90d = RiskService.compute_portfolio_return(holdings, price_histories, 90)

        benchmark_30d = None
        if btc_asset_id and btc_asset_id in price_histories:
            benchmark_30d = RiskService.compute_period_return(
                price_histories[btc_asset_id], 30
            )

        per_asset = []
        for h in holdings:
            prices = price_histories.get(h.asset_id)
            if not prices:
                per_asset.append({
                    'symbol': h.symbol, 'return_7d': None, 'return_30d': None,
                })
                continue
            per_asset.append({
                'symbol': h.symbol,
                'return_7d': RiskService.compute_period_return(prices, 7),
                'return_30d': RiskService.compute_period_return(prices, 30),
            })

        return ReturnMetrics(
            portfolio_return_1d=ret_1d,
            portfolio_return_7d=ret_7d,
            portfolio_return_30d=ret_30d,
            portfolio_return_90d=ret_90d,
            benchmark_return_30d=benchmark_30d,
            per_asset_returns=per_asset,
        )
