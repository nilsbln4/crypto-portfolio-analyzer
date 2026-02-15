# Crypto Risk Portfolio Analyzer (CRPA)

A professional-grade web application for cryptocurrency portfolio management and risk analysis. Built with Flask, it provides institutional-style risk metrics, return tracking, and interactive visualizations for crypto portfolios.

## Features

- **Portfolio Management** -- Create, rename, delete, and version portfolios with full change history
- **Risk Analytics** -- Concentration (Top-1, Top-3, HHI), Sharpe ratio, Beta vs BTC, Value at Risk, diversification scoring, correlation matrix, and volatility decomposition
- **Return Tracking** -- 1D, 7D, 30D, and 90D portfolio returns with BTC benchmark comparison
- **Interactive Charts** -- Portfolio performance index, per-asset price lines, allocation treemap, sector exposure, correlation heatmap, and returns bar chart (Plotly.js)
- **Version History** -- Side-by-side comparison of portfolio versions with risk metric deltas and improvement indicators
- **50-Asset Universe** -- Layer 1, DeFi, Layer 2, Oracle, Stablecoin, Meme, Infrastructure, Exchange, and Gaming categories
- **Dark/Light Mode** -- Toggle between professional light and dark themes with smooth transitions
- **Admin Console** -- User management, system reports, and audit logging
- **Live Risk Preview** -- Debounced AJAX risk metric updates as weights are adjusted in real time

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL (production) or SQLite (development/testing)
- CoinGecko API key ([free demo tier](https://www.coingecko.com/en/api))

### Installation

```bash
cd crypto-portfolio-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for testing
```

### Configuration

Copy `.env.example` to `.env` and configure:

```
DATABASE_URL=postgresql://user:password@localhost:5432/crpa
COINGECKO_API_KEY=your_api_key_here
SECRET_KEY=your_random_secret_key
```

For local development without PostgreSQL, SQLite works out of the box:

```
DATABASE_URL=sqlite:///crpa.db
```

### Database Setup

```bash
# Create tables and seed 50 crypto assets
flask seed

# Fetch 90-day price history for all assets (requires API key)
flask seed-history
```

### Run

```bash
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser. Register an account, then load a predefined portfolio template to get started.

### Run Tests

```bash
pytest tests/ -v
```

145 tests covering unit, integration, and system layers.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | System design, service layers, and data flow |
| [API Reference](API.md) | All HTTP endpoints, parameters, and JSON responses |
| [Risk Metrics](RISK_METRICS.md) | Methodology for every risk and return calculation |
| [Database Schema](DATABASE.md) | Models, relationships, and constraints |
| [Deployment](DEPLOYMENT.md) | Production setup, CLI commands, and operations |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask 3.1.2, SQLAlchemy, Flask-Login, Flask-WTF |
| Database | PostgreSQL (production), SQLite (testing) |
| Market Data | CoinGecko API with rate limiting and DB caching |
| Charts | Plotly.js 2.35 (CDN-loaded) |
| Authentication | bcrypt password hashing, session-based login |
| Styling | CSS custom properties, light/dark theme toggle |
| Fonts | IBM Plex Sans (UI), JetBrains Mono (data) |
| Testing | pytest (145 tests), pytest-flask, responses (mock HTTP) |
| Deployment | Gunicorn, Heroku-compatible |

## Project Structure

```
crypto-portfolio-analyzer/
    app/
        __init__.py          # App factory (create_app)
        config.py            # Dev / Test / Prod configurations
        extensions.py        # db, login_manager, csrf
        seeds.py             # flask seed / flask seed-history CLI
        models/              # User, Portfolio, Asset, MarketData, Transaction
        routes/              # 8 Flask blueprints
        services/            # Business logic (risk, portfolio, market data, auth, admin)
        templates/           # Jinja2 templates organized by section
        static/css/          # style.css with CSS custom properties
    seeds/
        assets.json          # 50 cryptocurrency definitions
        portfolios.json      # 5 starter portfolio templates
    tests/
        conftest.py          # Shared fixtures (app, db_session, client)
        unit/                # Service-level tests
        integration/         # Route and model tests
    docs/                    # This documentation
    run.py                   # python run.py entry point
    requirements.txt         # Production dependencies
    requirements-dev.txt     # Dev/test dependencies
    Procfile                 # Gunicorn for Heroku
```

## Predefined Portfolio Templates

| Template | Assets | Description |
|----------|--------|-------------|
| BTC/ETH Core | 3 | Conservative 60/30/10 split with USDC |
| Balanced Crypto Exposure | 7 | Multi-category diversification |
| High-Risk Speculative | 6 | Alt-heavy, no BTC exposure |
| Top 10 Market Cap | 11 | Market-cap-weighted across majors |
| DeFi Focused | 9 | Pure DeFi protocol exposure |

## User Roles

| Role | Capabilities |
|------|-------------|
| Normal | Create/manage portfolios, view analytics, track history |
| Admin | All normal capabilities + user management, system reports, audit logs |

## License

Private -- for academic and demonstration purposes.
