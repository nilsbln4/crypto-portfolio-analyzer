# CRPA Risk Metrics Reference

> Comprehensive documentation for the risk analysis engine in the Crypto Portfolio Analyzer (CRPA).
> Source: `app/services/risk_service.py`

---

## Table of Contents

1. [Overview](#overview)
2. [Concentration Metrics](#concentration-metrics)
   - [Top-1 Concentration](#top-1-concentration)
   - [Top-3 Concentration](#top-3-concentration)
   - [Herfindahl-Hirschman Index (HHI)](#herfindahl-hirschman-index-hhi)
3. [Volatility Contributions](#volatility-contributions)
4. [Exposure Metrics](#exposure-metrics)
   - [Stablecoin Exposure](#stablecoin-exposure)
   - [Sector Exposure](#sector-exposure)
5. [Extended Risk Metrics (Phase 3)](#extended-risk-metrics-phase-3)
   - [Sharpe Ratio](#sharpe-ratio)
   - [Portfolio Beta](#portfolio-beta)
   - [Value at Risk (VaR)](#value-at-risk-var)
   - [Diversification Score](#diversification-score)
6. [Drawdown Analysis](#drawdown-analysis)
   - [Max Drawdown](#max-drawdown)
7. [Correlation Matrix](#correlation-matrix)
8. [Return Metrics](#return-metrics)
   - [Period Returns (1D / 7D / 30D / 90D)](#period-returns)
   - [Portfolio Return](#portfolio-return)
   - [Benchmark Return](#benchmark-return)
   - [Per-Asset Returns](#per-asset-returns)
9. [Risk Interpretations](#risk-interpretations)
10. [Data Classes](#data-classes)
    - [Holding](#holding)
    - [VolContribution](#volcontribution)
    - [RiskMetrics](#riskmetrics)
    - [ReturnMetrics](#returnmetrics)
11. [Usage Examples](#usage-examples)
12. [Minimum Data Requirements Summary](#minimum-data-requirements-summary)

---

## Overview

`RiskService` is a stateless, pure-calculation class that contains only `@staticmethod` methods. It has **no database dependencies and no API calls**. All market data is passed in as arguments, making the service fully testable in isolation.

The primary entry points are:

| Method | Purpose |
|---|---|
| `compute_all_metrics()` | Computes every risk metric and returns a `RiskMetrics` dataclass |
| `compute_all_returns()` | Computes portfolio and per-asset returns across multiple time horizons, returning a `ReturnMetrics` dataclass |

All numeric values use Python's `decimal.Decimal` for precision. Rounding uses `ROUND_HALF_UP` throughout.

### Execution Flow of `compute_all_metrics`

```
holdings ----+---> concentration_top_n(1)  ----> top1_concentration
             |---> concentration_top_n(3)  ----> top3_concentration
             |---> hhi()                   ----> hhi
             |---> stablecoin_exposure()   ----> stablecoin_exposure
             |---> sector_exposure()       ----> sector_exposure
             |
             +--- (with price_histories) ---+--> volatility_contributions() ---> vol_contribs
                                            +--> compute_correlation_matrix() -> correlation_matrix
                                            +--> compute_sharpe_ratio()       -> sharpe_ratio
                                            +--> compute_value_at_risk()      -> var_95
                                            +--> compute_diversification_score() -> div_score
                                            +--> portfolio_beta_vs_btc()      -> portfolio_beta
                                                 (requires btc_asset_id)

portfolio_prices ---> max_drawdown() ---> max_drawdown

All metrics ---> interpret_risk() ---> interpretations
```

---

## Concentration Metrics

### Top-1 Concentration

**What it measures:** The portfolio weight of the single largest holding. Identifies single-asset dominance risk.

**Method:** `RiskService.concentration_top_n(holdings, 1)`

**Algorithm:**

1. Extract `weight_pct` from every `Holding`.
2. Sort weights in descending order.
3. Return the first element.

```
Top1 = max(w_i) for all holdings i
```

**Input:** `list[Holding]` where each holding has a `weight_pct` (Decimal, percentage).

**Output:** `Decimal` in range `[0, 100]` representing a percentage.

**Interpretation:**

| Value | Meaning |
|---|---|
| < 30% | Well-distributed; no single-asset dominance |
| 30% -- 50% | Moderate concentration in one asset |
| >= 50% | High concentration risk -- triggers interpretation warning |

---

### Top-3 Concentration

**What it measures:** The combined portfolio weight of the three largest holdings. Captures whether risk is clustered in a small number of positions.

**Method:** `RiskService.concentration_top_n(holdings, 3)`

**Algorithm:**

1. Extract and sort all `weight_pct` values descending.
2. Sum the top 3 (or fewer, if the portfolio has < 3 assets).

```
Top3 = sum(w_i) for the 3 largest weights
```

**Input:** `list[Holding]`

**Output:** `Decimal` in range `[0, 100]`.

**Interpretation:**

| Value | Meaning |
|---|---|
| < 60% | Reasonable dispersion across the portfolio |
| 60% -- 80% | Moderately top-heavy |
| >= 80% | Heavily concentrated in 3 assets |

---

### Herfindahl-Hirschman Index (HHI)

**What it measures:** A standard measure of market concentration adapted for portfolio analysis. Accounts for both the number of holdings and the inequality of their weights.

**Method:** `RiskService.hhi(holdings)`

**Formula:**

```
HHI = sum(w_i ^ 2) for all holdings i
```

Where `w_i` is the weight percentage (not the decimal fraction). The result is quantized to two decimal places.

**Input:** `list[Holding]`

**Output:** `Decimal` in range `[0, 10000]`, rounded to 2 decimal places.

**Reference values:**

| HHI | Portfolio Composition |
|---|---|
| 10000 | Single asset (100^2) |
| 5000 | Two assets at 50/50 (50^2 + 50^2) |
| 2500 | Four equal assets (4 x 25^2) |
| 1000 | Ten equal assets (10 x 10^2) |

**Interpretation:**

| HHI Range | Meaning |
|---|---|
| < 1500 | Unconcentrated; well-diversified |
| 1500 -- 2500 | Moderately concentrated |
| 2500 -- 5000 | Highly concentrated |
| >= 5000 | Extremely concentrated -- triggers interpretation warning |

---

## Volatility Contributions

**What it measures:** Each asset's contribution to overall portfolio volatility, computed as the product of its weight and its individual annualized volatility.

**Method:** `RiskService.volatility_contributions(holdings, price_histories)`

**Algorithm:**

For each holding with sufficient price data (>= 2 data points yielding >= 2 daily returns):

1. Compute daily returns:
   ```
   r_t = (P_t - P_{t-1}) / P_{t-1}
   ```
2. Compute sample variance of daily returns (using Bessel's correction, dividing by `n - 1`):
   ```
   variance = sum((r_t - mean_r)^2) / (n - 1)
   ```
3. Daily volatility:
   ```
   sigma_daily = sqrt(variance)
   ```
4. Annualize (crypto markets trade 365 days/year):
   ```
   sigma_annual = sigma_daily * sqrt(365)
   ```
5. Express as percentage:
   ```
   volatility = sigma_annual * 100
   ```
6. Weighted contribution:
   ```
   contribution = weight_pct * volatility / 100
   ```

**Input:**
- `holdings`: `list[Holding]`
- `price_histories`: `dict[int, list[Decimal]]` mapping `asset_id` to chronologically ordered price series

**Output:** `list[VolContribution]` where each entry contains:
- `asset_id`: int
- `symbol`: str
- `weight_pct`: Decimal (portfolio weight percentage)
- `volatility`: Decimal (annualized volatility %, rounded to 2 decimal places)
- `contribution`: Decimal (weighted contribution, rounded to 4 decimal places)

Assets with fewer than 2 price points are **excluded** from the result list.

**Interpretation:**

| Volatility (annualized) | Meaning |
|---|---|
| < 30% | Low volatility (typical for stablecoins or large-caps in calm markets) |
| 30% -- 80% | Moderate volatility |
| >= 80% | High volatility -- triggers interpretation warning listing the asset symbols |

---

## Exposure Metrics

### Stablecoin Exposure

**What it measures:** The aggregate portfolio weight allocated to stablecoin assets. Indicates how much of the portfolio is shielded from crypto market volatility but also excluded from upside potential.

**Method:** `RiskService.stablecoin_exposure(holdings)`

**Algorithm:**

Sum the `weight_pct` of all holdings whose `category` matches `'Stablecoin'` (exact string match, case-sensitive).

```
stablecoin_exposure = sum(w_i) where category_i == 'Stablecoin'
```

**Input:** `list[Holding]`

**Output:** `Decimal` in range `[0, 100]`.

**Interpretation:**

| Value | Meaning |
|---|---|
| 0% | Fully exposed to market volatility -- triggers interpretation note |
| 1% -- 20% | Light hedge |
| 20% -- 50% | Significant defensive allocation |
| >= 50% | Limits growth potential -- triggers interpretation warning |

---

### Sector Exposure

**What it measures:** The distribution of portfolio weight across asset categories (sectors). Provides a breakdown of thematic or functional exposure.

**Method:** `RiskService.sector_exposure(holdings)`

**Algorithm:**

Aggregate `weight_pct` by `category`:

```python
sectors = {}
for each holding h:
    sectors[h.category] += h.weight_pct
```

**Input:** `list[Holding]`

**Output:** `dict[str, Decimal]` mapping category name to aggregate weight percentage. All values sum to 100 (assuming input weights sum to 100).

**Common categories:** `Layer 1`, `Layer 2`, `DeFi`, `Stablecoin`, `Meme`, `Infrastructure`, etc.

**Example output:**
```python
{
    "Layer 1": Decimal("55.00"),
    "DeFi": Decimal("25.00"),
    "Stablecoin": Decimal("20.00"),
}
```

---

## Extended Risk Metrics (Phase 3)

These metrics require price history data and are computed only when `price_histories` is provided to `compute_all_metrics()`.

### Sharpe Ratio

**What it measures:** Risk-adjusted return. Quantifies how much excess return the portfolio earns per unit of volatility. A higher Sharpe ratio indicates better risk-adjusted performance.

**Method:** `RiskService.compute_sharpe_ratio(holdings, price_histories, risk_free_rate=Decimal('0.04'))`

**Algorithm:**

1. Compute weighted daily portfolio returns across all available days:
   ```
   R_portfolio_t = sum(w_i * r_i_t) for all holdings i with data on day t
   ```
   where `w_i = weight_pct / 100`.

2. Require at least 20 daily return observations; otherwise return `None`.

3. Compute daily mean and daily volatility (population standard deviation):
   ```
   mean_daily = sum(R_t) / n
   var_daily  = sum((R_t - mean_daily)^2) / n
   vol_daily  = sqrt(var_daily)
   ```

4. Annualize:
   ```
   annualized_return = mean_daily * 365
   annualized_vol    = vol_daily * sqrt(365)
   ```

5. Compute Sharpe ratio:
   ```
   Sharpe = (annualized_return - risk_free_rate) / annualized_vol
   ```

**Input:**
- `holdings`: `list[Holding]`
- `price_histories`: `dict[int, list[Decimal]]`
- `risk_free_rate`: `Decimal` (default `0.04`, i.e., 4% annual)

**Output:** `Decimal` rounded to 4 decimal places, or `None` if insufficient data (< 20 daily returns) or zero volatility.

**Notes:**
- The default risk-free rate of 4% represents a typical annual yield on low-risk fixed-income instruments.
- Uses population standard deviation (divides by `n`, not `n-1`) for the Sharpe calculation, unlike the sample variance used in individual asset volatility.

**Interpretation:**

| Sharpe Ratio | Meaning |
|---|---|
| < 0 | Returns below risk-free rate -- triggers interpretation warning |
| 0 -- 1 | Subpar to adequate risk-adjusted returns |
| 1 -- 2 | Good risk-adjusted returns |
| > 2 | Excellent risk-adjusted returns |

---

### Portfolio Beta

**What it measures:** The sensitivity of portfolio returns to Bitcoin (BTC) returns. Beta quantifies systematic (market) risk relative to the dominant crypto benchmark.

**Method:** `RiskService.portfolio_beta_vs_btc(holdings, price_histories, btc_asset_id)`

**Algorithm:**

1. Compute BTC daily returns from its price series. Require >= 10 data points.

2. For each trading day, compute the weighted portfolio return:
   ```
   R_portfolio_t = sum((w_i / 100) * r_i_t) for all holdings with data on day t
   ```

3. Require at least 10 portfolio return observations.

4. Compute beta using the covariance / variance formula (population formulas, dividing by `n`):
   ```
   beta = Cov(R_portfolio, R_btc) / Var(R_btc)
   ```

   Where:
   ```
   Cov = (1/n) * sum((R_p_t - mean_p) * (R_b_t - mean_b))
   Var = (1/n) * sum((R_b_t - mean_b)^2)
   ```

**Input:**
- `holdings`: `list[Holding]`
- `price_histories`: `dict[int, list[Decimal]]` (must include `btc_asset_id` key)
- `btc_asset_id`: `int` (database ID of Bitcoin)

**Output:** `Decimal` rounded to 4 decimal places, or `None` if BTC data is missing or insufficient.

**Note:** BTC price data is always fetched independently by the calling route (even if BTC is not in the portfolio) to ensure beta can be computed.

**Interpretation:**

| Beta | Meaning |
|---|---|
| ~0 | Uncorrelated to BTC |
| < 1.0 | Dampened market exposure (more defensive) |
| ~1.0 | Moves in lockstep with BTC |
| > 1.0 | Amplifies BTC movements |
| > 1.2 | Amplified market exposure -- triggers interpretation warning |
| < 0 | Inversely correlated with BTC (rare in crypto) |

---

### Value at Risk (VaR)

**What it measures:** The estimated maximum daily portfolio loss at a given confidence level. Uses the parametric (variance-covariance) method assuming normally distributed returns.

**Method:** `RiskService.compute_value_at_risk(holdings, price_histories, confidence=Decimal('0.95'))`

**Algorithm:**

1. Compute weighted daily portfolio returns (same approach as Sharpe ratio).
2. Require at least 20 observations; otherwise return `None`.
3. Compute daily mean return and daily volatility (population standard deviation).
4. Apply the parametric VaR formula at 95% confidence (z = 1.645):
   ```
   VaR_daily = -(mean_daily - 1.645 * vol_daily)
   ```
5. Convert to percentage:
   ```
   VaR_95 = VaR_daily * 100
   ```

The result is expressed as a **positive number** representing the potential loss.

**Input:**
- `holdings`: `list[Holding]`
- `price_histories`: `dict[int, list[Decimal]]`
- `confidence`: `Decimal` (default `0.95`)

**Output:** `Decimal` (positive percentage, rounded to 4 decimal places), or `None` if insufficient data.

**Limitations:**
- Assumes returns are normally distributed (parametric method).
- Does not capture tail risk or extreme events beyond the confidence level.
- Crypto returns often exhibit fat tails, so actual losses can exceed VaR.

**Interpretation:**

| VaR (95%, daily) | Meaning |
|---|---|
| < 2% | Low daily risk |
| 2% -- 5% | Moderate daily risk |
| > 5% | Significant downside potential -- triggers interpretation warning |

**Example:** A VaR of 3.5% means: "On 95% of days, the portfolio is expected to lose no more than 3.5%. On the worst 5% of days, losses may exceed 3.5%."

---

### Diversification Score

**What it measures:** A composite score (0--100) that evaluates how well-diversified the portfolio is, combining asset count, correlation structure, and weight distribution.

**Method:** `RiskService.compute_diversification_score(holdings, price_histories)`

**Algorithm:**

The score is the sum of three sub-scores:

#### Sub-score 1: Asset Count (0--30 points)

```
asset_score = min(n_assets, 10) / 10 * 30
```

Where `n_assets` is the count of holdings with `weight_pct > 0`. Maxes out at 10 assets (30 points).

#### Sub-score 2: Average Pairwise Correlation (0--40 points)

If at least 2 assets have sufficient price data for correlation computation:

```
avg_abs_corr = mean(|corr(i, j)|) for all unique pairs where i < j
corr_score   = (1 - avg_abs_corr) * 40
```

Lower average correlation yields a higher score. If correlation data is unavailable, defaults to 20 points (mid-range).

#### Sub-score 3: Weight Entropy (0--30 points)

Uses Shannon entropy to measure how evenly distributed the weights are:

```
H = -sum(w_i * ln(w_i)) for all holdings with w_i > 0
```

Where `w_i` is the decimal weight (`weight_pct / 100`). Normalized against maximum possible entropy:

```
H_max         = ln(n_assets)
entropy_ratio = H / H_max
entropy_score = entropy_ratio * 30
```

Equal weights yield maximum entropy (30 points). A single-asset portfolio yields 0 points.

#### Final Score

```
diversification_score = clamp(asset_score + corr_score + entropy_score, 0, 100)
```

Rounded to 1 decimal place.

**Component Breakdown:**

| Component | Max Points | Best Score When |
|---|---|---|
| Asset Count | 30 | 10 or more assets with nonzero weight |
| Correlation | 40 | Low average absolute pairwise correlation (near 0) |
| Weight Entropy | 30 | Equal weights across all assets |

**Input:**
- `holdings`: `list[Holding]`
- `price_histories`: `dict[int, list[Decimal]]`

**Output:** `Decimal` in range `[0, 100]`, rounded to 1 decimal place.

**Interpretation:**

| Score | Meaning |
|---|---|
| < 30 | Low diversification -- triggers interpretation warning |
| 30 -- 60 | Moderate diversification |
| 60 -- 80 | Good diversification |
| > 80 | Excellent diversification |

---

## Drawdown Analysis

### Max Drawdown

**What it measures:** The largest peak-to-trough decline in the portfolio price series, expressed as a percentage. Captures the worst historical loss scenario.

**Method:** `RiskService.max_drawdown(prices)`

**Algorithm:**

1. Initialize `peak` as the first price and `max_dd` as 0.
2. Iterate through the price series starting from the second element:
   - If current price exceeds `peak`, update `peak`.
   - Compute drawdown: `dd = (peak - price) / peak * 100`
   - If `dd > max_dd`, update `max_dd`.
3. Return `max_dd` rounded to 2 decimal places.

```
max_drawdown = max((peak_t - P_t) / peak_t * 100) for all t
where peak_t = max(P_0, P_1, ..., P_t)
```

**Input:** `list[Decimal]` -- chronologically ordered portfolio price series. Requires at least 2 data points; returns `Decimal('0')` otherwise.

**Output:** `Decimal` in range `[0, 100]`, rounded to 2 decimal places. A value of 0 means prices only went up.

**Interpretation:**

| Max Drawdown | Meaning |
|---|---|
| < 10% | Minor pullback |
| 10% -- 30% | Moderate correction |
| >= 30% | Significant downturn -- triggers interpretation warning |
| >= 50% | Severe crash (common in crypto bear markets) |

---

## Correlation Matrix

**What it measures:** Pairwise Pearson correlation coefficients between all assets' daily returns. Identifies which assets move together and which provide genuine diversification.

**Method:** `RiskService.compute_correlation_matrix(price_histories)`

**Algorithm:**

1. Convert each asset's price series to daily returns.
2. Filter to assets with at least 10 daily return observations.
3. For each unique pair `(a, b)`:
   - Align to the shorter series (use the last `min_len` returns from each).
   - Require at least 10 overlapping observations.
   - Compute Pearson correlation coefficient:
     ```
     r = (n * sum(x_i * y_i) - sum(x_i) * sum(y_i)) /
         sqrt((n * sum(x_i^2) - (sum(x_i))^2) * (n * sum(y_i^2) - (sum(y_i))^2))
     ```
4. Self-correlation is always `Decimal('1.0')`.
5. The matrix is symmetric: `corr(a, b) = corr(b, a)`.

**Input:** `dict[int, list[Decimal]]` mapping `asset_id` to price series. Requires at least 2 assets with >= 10 daily return observations (i.e., >= 11 price points each).

**Output:** `dict[tuple[int, int], Decimal]` where keys are `(asset_id_a, asset_id_b)` tuples. Correlation values are rounded to 4 decimal places. Returns `None` if fewer than 2 qualifying assets.

**Interpretation:**

| Correlation | Meaning |
|---|---|
| +0.7 to +1.0 | Strong positive correlation (assets move together) |
| +0.3 to +0.7 | Moderate positive correlation |
| -0.3 to +0.3 | Low correlation; good for diversification |
| -0.7 to -0.3 | Moderate negative correlation; hedging potential |
| -1.0 to -0.7 | Strong negative correlation |

Lower average absolute correlation across the portfolio indicates better diversification benefits.

---

## Return Metrics

### Period Returns

**What it measures:** Simple percentage return over a specific number of trailing price observations.

**Method:** `RiskService.compute_period_return(prices, days)`

**Algorithm:**

1. Take the last `days` prices from the series (or the full series if shorter than `days`).
2. Require at least 2 data points and a non-zero starting price.
3. Compute:
   ```
   return = (P_last - P_first) / P_first * 100
   ```
4. Round to 2 decimal places.

**Input:**
- `prices`: `list[Decimal]` -- chronologically ordered
- `days`: `int` -- number of trailing observations to consider

**Output:** `Decimal` (percentage, 2 decimal places) or `None` if data is insufficient.

---

### Portfolio Return

**What it measures:** The weight-adjusted aggregate return of the portfolio over a given time horizon.

**Method:** `RiskService.compute_portfolio_return(holdings, price_histories, days)`

**Algorithm:**

```
portfolio_return = sum((w_i / 100) * return_i) for all holdings with available data
```

Where `return_i` is computed via `compute_period_return()` for each asset. Assets without price data are excluded.

**Output:** `Decimal` (percentage, 2 decimal places) or `None` if no asset has sufficient data.

---

### Benchmark Return

The 30-day return of BTC, computed via `compute_period_return(btc_prices, 30)`. Used for relative performance comparison. Only available when `btc_asset_id` is provided and BTC price data exists in `price_histories`.

---

### Per-Asset Returns

Individual 7-day and 30-day returns for each holding, computed via `compute_period_return()`. Returned as a list of dictionaries with keys `symbol`, `return_7d`, and `return_30d`. If no price data is available for an asset, both return values are `None`.

---

### Aggregate Return Computation

**Method:** `RiskService.compute_all_returns(holdings, price_histories, btc_asset_id=None)`

Computes all return metrics in a single call:

| Field | Lookback | Method |
|---|---|---|
| `portfolio_return_1d` | Last 2 prices | `compute_portfolio_return(holdings, prices, 2)` |
| `portfolio_return_7d` | Last 7 prices | `compute_portfolio_return(holdings, prices, 7)` |
| `portfolio_return_30d` | Last 30 prices | `compute_portfolio_return(holdings, prices, 30)` |
| `portfolio_return_90d` | Last 90 prices | `compute_portfolio_return(holdings, prices, 90)` |
| `benchmark_return_30d` | BTC last 30 prices | `compute_period_return(btc_prices, 30)` |
| `per_asset_returns` | Per asset, 7D and 30D | `compute_period_return()` for each holding |

**Output:** `ReturnMetrics` dataclass.

---

## Risk Interpretations

**Method:** `RiskService.interpret_risk(metrics)`

Generates plain-English risk warnings based on metric thresholds. The interpretation engine evaluates the `RiskMetrics` dataclass and returns a `list[str]` of messages.

### Trigger Rules

| Condition | Interpretation Message |
|---|---|
| `top1_concentration >= 50` | "High concentration risk: a single asset makes up {X}% of the portfolio." |
| `hhi >= 5000` | "Portfolio is highly concentrated (HHI >= 5000). Consider diversifying across more assets." |
| `stablecoin_exposure >= 50` | "Stablecoin exposure is {X}%. This limits growth potential but reduces volatility." |
| `stablecoin_exposure == 0` | "No stablecoin allocation. The portfolio is fully exposed to market volatility." |
| Any asset with `volatility >= 80` | "High annualized volatility detected in: {symbols}. These assets are major risk drivers." |
| `max_drawdown >= 30` | "Historical max drawdown of {X}% observed. The portfolio has experienced significant downturns." |
| `portfolio_beta > 1.2` | "Portfolio beta of {X} vs BTC indicates amplified market exposure." |
| `sharpe_ratio < 0` | "Negative Sharpe ratio suggests returns are below the risk-free rate." |
| `diversification_score < 30` | "Diversification score of {X}/100 is low. Consider adding uncorrelated assets." |
| `var_95 > 5` | "Daily Value at Risk of {X}% at 95% confidence indicates significant downside potential." |
| No triggers fired | "Portfolio risk metrics are within moderate ranges." |

Interpretations are evaluated in the order listed above. Multiple warnings can be returned simultaneously. The stablecoin exposure checks are mutually exclusive (>= 50% vs == 0%).

---

## Data Classes

All data classes are defined using Python's `@dataclass` decorator and use `Decimal` for numeric precision.

### Holding

Represents a single portfolio position.

```python
@dataclass
class Holding:
    asset_id: int          # Database primary key for the asset
    symbol: str            # Ticker symbol (e.g., 'BTC', 'ETH')
    weight_pct: Decimal    # Portfolio weight as a percentage (0-100)
    category: str          # Asset category (e.g., 'Layer 1', 'Stablecoin', 'DeFi')
```

**Notes:**
- `weight_pct` is expressed as a percentage value (e.g., `Decimal('45.50')` means 45.50% of the portfolio).
- `category` is used by stablecoin exposure and sector exposure calculations. The stablecoin filter specifically matches the exact string `"Stablecoin"`.

---

### VolContribution

Represents a single asset's volatility contribution to the portfolio.

```python
@dataclass
class VolContribution:
    asset_id: int          # Database primary key
    symbol: str            # Ticker symbol
    weight_pct: Decimal    # Portfolio weight percentage
    volatility: Decimal    # Annualized volatility (%), rounded to 2 decimal places
    contribution: Decimal  # Weighted volatility contribution, rounded to 4 decimal places
```

**Notes:**
- `volatility` is the annualized volatility of the individual asset, expressed as a percentage.
- `contribution` equals `weight_pct * volatility / 100`. It approximates the asset's additive share of total portfolio volatility.

---

### RiskMetrics

Aggregates all risk metrics for a portfolio snapshot.

```python
@dataclass
class RiskMetrics:
    # Core metrics (always computed)
    top1_concentration: Decimal              # Largest single holding weight (%)
    top3_concentration: Decimal              # Sum of top 3 holding weights (%)
    hhi: Decimal                             # Herfindahl-Hirschman Index (0-10000)
    volatility_contributions: list[VolContribution]  # Per-asset vol contributions
    stablecoin_exposure: Decimal             # Total stablecoin weight (%)
    sector_exposure: dict[str, Decimal]      # Weight by category
    max_drawdown: Optional[Decimal]          # Peak-to-trough decline (%)
    interpretations: list[str]               # Plain-English risk warnings (default: [])

    # Phase 3: Extended metrics (None when price data is unavailable)
    correlation_matrix: Optional[dict]       # {(id_a, id_b): Decimal correlation}
    portfolio_beta: Optional[Decimal]        # Beta vs BTC
    sharpe_ratio: Optional[Decimal]          # Annualized Sharpe ratio
    var_95: Optional[Decimal]                # 95% daily VaR (%)
    diversification_score: Optional[Decimal] # Composite score (0-100)
```

---

### ReturnMetrics

Aggregates return calculations across multiple time horizons.

```python
@dataclass
class ReturnMetrics:
    portfolio_return_1d: Optional[Decimal]    # 1-day portfolio return (%)
    portfolio_return_7d: Optional[Decimal]    # 7-day portfolio return (%)
    portfolio_return_30d: Optional[Decimal]   # 30-day portfolio return (%)
    portfolio_return_90d: Optional[Decimal]   # 90-day portfolio return (%)
    benchmark_return_30d: Optional[Decimal]   # BTC 30-day return (%)
    per_asset_returns: list[dict]             # [{symbol, return_7d, return_30d}, ...]
```

**Notes:**
- All return values are percentages rounded to 2 decimal places.
- `per_asset_returns` is a list of dictionaries, each with keys `symbol` (str), `return_7d` (Optional[Decimal]), and `return_30d` (Optional[Decimal]).
- `benchmark_return_30d` is `None` when `btc_asset_id` is not provided or BTC has no price data.

---

## Usage Examples

### Basic Risk Analysis (No Price Data)

When only portfolio weights are available, core concentration and exposure metrics are still computed:

```python
from decimal import Decimal
from app.services.risk_service import RiskService, Holding

holdings = [
    Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('50'), category='Layer 1'),
    Holding(asset_id=2, symbol='ETH', weight_pct=Decimal('30'), category='Layer 1'),
    Holding(asset_id=3, symbol='UNI', weight_pct=Decimal('10'), category='DeFi'),
    Holding(asset_id=4, symbol='USDC', weight_pct=Decimal('10'), category='Stablecoin'),
]

metrics = RiskService.compute_all_metrics(holdings)

print(metrics.top1_concentration)   # Decimal('50')
print(metrics.top3_concentration)   # Decimal('90')
print(metrics.hhi)                  # Decimal('3400.00')
print(metrics.stablecoin_exposure)  # Decimal('10')
print(metrics.sector_exposure)
# {'Layer 1': Decimal('80'), 'DeFi': Decimal('10'), 'Stablecoin': Decimal('10')}
print(metrics.interpretations)
# ['High concentration risk: a single asset makes up 50% of the portfolio.']

# Extended metrics are None without price data
print(metrics.sharpe_ratio)          # None
print(metrics.portfolio_beta)        # None
print(metrics.var_95)                # None
print(metrics.diversification_score) # None (no price data for correlation)
```

### Full Analysis with Price Histories

When historical prices are provided, all extended metrics (Sharpe, Beta, VaR, diversification, correlations) are computed:

```python
from decimal import Decimal
from app.services.risk_service import RiskService, Holding

holdings = [
    Holding(asset_id=1, symbol='BTC', weight_pct=Decimal('60'), category='Layer 1'),
    Holding(asset_id=2, symbol='ETH', weight_pct=Decimal('30'), category='Layer 1'),
    Holding(asset_id=3, symbol='USDC', weight_pct=Decimal('10'), category='Stablecoin'),
]

# Price histories: dict mapping asset_id -> list of Decimal prices (chronological)
# Typically 90 daily price observations fetched from MarketDataDaily
price_histories = {
    1: [Decimal(str(p)) for p in [40000, 40500, 39800, 41000, ...]],  # 90 prices
    2: [Decimal(str(p)) for p in [2800, 2850, 2780, 2900, ...]],      # 90 prices
}

btc_asset_id = 1  # BTC's database ID

metrics = RiskService.compute_all_metrics(
    holdings,
    price_histories=price_histories,
    btc_asset_id=btc_asset_id,
)

# Core metrics
print(metrics.top1_concentration)         # Decimal('60')
print(metrics.hhi)                        # Decimal('4600.00')

# Extended metrics
print(metrics.sharpe_ratio)               # e.g., Decimal('1.2345')
print(metrics.portfolio_beta)             # e.g., Decimal('0.9512')
print(metrics.var_95)                     # e.g., Decimal('3.4521')
print(metrics.diversification_score)      # e.g., Decimal('45.2')
print(metrics.correlation_matrix[(1, 2)]) # e.g., Decimal('0.8234')

# Interpretations
for msg in metrics.interpretations:
    print(f"  - {msg}")
```

### Computing Returns

```python
returns = RiskService.compute_all_returns(
    holdings,
    price_histories,
    btc_asset_id=1,
)

print(returns.portfolio_return_1d)    # e.g., Decimal('1.25')
print(returns.portfolio_return_7d)    # e.g., Decimal('-2.30')
print(returns.portfolio_return_30d)   # e.g., Decimal('8.45')
print(returns.portfolio_return_90d)   # e.g., Decimal('15.67')
print(returns.benchmark_return_30d)   # e.g., Decimal('10.00') (BTC 30-day)

for asset_ret in returns.per_asset_returns:
    print(f"{asset_ret['symbol']}: 7D={asset_ret['return_7d']}, 30D={asset_ret['return_30d']}")
```

### Calling Individual Methods

Each metric can be computed independently:

```python
# Concentration
top1 = RiskService.concentration_top_n(holdings, 1)
top3 = RiskService.concentration_top_n(holdings, 3)

# HHI
hhi = RiskService.hhi(holdings)

# Stablecoin exposure
stable = RiskService.stablecoin_exposure(holdings)

# Sector breakdown
sectors = RiskService.sector_exposure(holdings)

# Volatility contributions (requires price data)
vol_contribs = RiskService.volatility_contributions(holdings, price_histories)

# Max drawdown (requires a single portfolio-level price series)
drawdown = RiskService.max_drawdown(portfolio_price_series)

# Correlation matrix
corr = RiskService.compute_correlation_matrix(price_histories)

# Sharpe ratio (with custom risk-free rate)
sharpe = RiskService.compute_sharpe_ratio(
    holdings, price_histories, risk_free_rate=Decimal('0.05')
)

# Portfolio beta vs BTC
beta = RiskService.portfolio_beta_vs_btc(holdings, price_histories, btc_asset_id=1)

# Value at Risk
var = RiskService.compute_value_at_risk(holdings, price_histories)

# Diversification score
div = RiskService.compute_diversification_score(holdings, price_histories)

# Single-asset period return
ret = RiskService.compute_period_return(price_series, days=30)
```

### Flask Route Integration

In the CRPA application, `RiskService` is called from route handlers after fetching price data from the database. The pattern used in both `portfolio.py` and `dashboard.py`:

```python
from app.services.risk_service import RiskService, Holding
from app.models import Asset
from app.models.market_data import MarketDataDaily

# Build Holding objects from a portfolio version's holdings
holding_objs = [
    Holding(
        asset_id=h.asset_id,
        symbol=h.asset.symbol,
        weight_pct=h.weight_pct,
        category=h.asset.category,
    )
    for h in version.holdings
]

# Fetch up to 90 days of price history per asset
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
btc_asset = Asset.query.filter_by(symbol='BTC').first()
btc_id = btc_asset.id if btc_asset else None
if btc_id and btc_id not in price_histories:
    btc_cached = (
        MarketDataDaily.query
        .filter(MarketDataDaily.asset_id == btc_id)
        .order_by(MarketDataDaily.date.desc())
        .limit(90)
        .all()
    )
    if btc_cached:
        price_histories[btc_id] = [row.price for row in reversed(btc_cached)]

# Compute all metrics and returns
metrics = RiskService.compute_all_metrics(
    holding_objs,
    price_histories=price_histories,
    btc_asset_id=btc_id,
)
returns = RiskService.compute_all_returns(
    holding_objs,
    price_histories,
    btc_asset_id=btc_id,
)

# Pass to template
return render_template(
    'portfolio/analysis.html',
    metrics=metrics,
    returns=returns,
)
```

### Risk Preview API Endpoint

The `/api/portfolio/risk-preview` endpoint accepts proposed holdings as JSON and returns computed metrics without saving to the database:

```python
# POST /api/portfolio/risk-preview
# Request body:
{
    "holdings": {
        "1": 60,   // asset_id: weight_pct
        "2": 30,
        "4": 10
    }
}

# Response includes all computed metrics as JSON floats:
{
    "top1_concentration": 60.0,
    "top3_concentration": 100.0,
    "hhi": 4600.0,
    "stablecoin_exposure": 10.0,
    "sharpe_ratio": 1.2345,
    "var_95": 3.45,
    "portfolio_beta": 0.95,
    "diversification_score": 45.2,
    "interpretations": ["High concentration risk: ..."],
    "sector_exposure": {"Layer 1": 90.0, "Stablecoin": 10.0},
    "portfolio_return_1d": 1.25,
    "portfolio_return_7d": -2.30,
    "portfolio_return_30d": 8.45,
    "portfolio_return_90d": 15.67
}
```

---

## Minimum Data Requirements Summary

| Metric | Min. Price Points per Asset | Min. Holdings | Notes |
|---|---|---|---|
| Concentration (Top-N) | 0 | 1 | Weight-only calculation |
| HHI | 0 | 1 | Weight-only calculation |
| Stablecoin Exposure | 0 | 1 | Weight-only calculation |
| Sector Exposure | 0 | 1 | Weight-only calculation |
| Volatility Contributions | 2 (yields >= 2 returns) | 1 | Assets below threshold excluded |
| Max Drawdown | 2 | N/A | Operates on portfolio-level price series |
| Correlation Matrix | 11 (yields >= 10 returns) | 2 qualifying assets | Returns `None` if unmet |
| Sharpe Ratio | 21 total (yields >= 20 returns) | 1 | Returns `None` if unmet |
| Portfolio Beta | 11 (yields >= 10 returns for BTC) | 1 + BTC data | Returns `None` if unmet |
| Value at Risk (VaR) | 21 total (yields >= 20 returns) | 1 | Returns `None` if unmet |
| Diversification Score | 0 (degrades gracefully) | 1 | Correlation sub-score defaults to 20/40 |
| Period Return | 2 | 1 | Returns `None` if unmet |
| Portfolio Return | 2 per asset | 1 with data | Assets without data excluded |

---

*This document describes the risk engine as implemented in `app/services/risk_service.py`. All calculations use Python `Decimal` arithmetic for precision. No database or API calls are made within the risk service; it operates as a pure computation layer.*
