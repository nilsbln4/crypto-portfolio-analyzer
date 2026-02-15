# CRPA System Architecture

This document describes the architecture of the Crypto Portfolio Analyzer (CRPA), a Flask-based web application for managing and analyzing cryptocurrency portfolios.

---

## App Factory Pattern

The application is constructed using Flask's app factory pattern in `app/__init__.py`. The entry point is `create_app(config_class)`, which performs the following initialization sequence:

1. Loads environment variables via `python-dotenv`.
2. Initializes extensions: SQLAlchemy (`db`), Flask-Login (`login_manager`), and Flask-WTF (`csrf`).
3. Configures logging to stdout for `app.services` and `app.routes`.
4. Registers eight blueprints: `public`, `auth`, `dashboard`, `portfolio`, `asset`, `history`, `reporting`, and `admin`.
5. Registers the seed module via `seeds.init_app(app)`.

---

## Three-Layer Architecture

CRPA follows a strict three-layer separation of concerns:

```
Routes (Blueprints)  -->  Services  -->  Models (SQLAlchemy)
       |                      |                |
  HTTP handling         Business logic     Database ORM
  Template rendering    Pure calculations  Relationships
  JSON responses        No DB access       Constraints
                        (RiskService)
```

- **Routes** handle HTTP request/response cycles, template rendering, and JSON serialization. They contain no business logic.
- **Services** encapsulate all business logic, calculations, and orchestration. `RiskService` is fully pure -- it receives data as arguments and performs no database or API access.
- **Models** define the SQLAlchemy ORM layer, including table schemas, relationships, and database constraints.

---

## Blueprints

All route modules live under `app/routes/`.

| Blueprint | URL Prefix | Purpose |
|-----------|-----------|---------|
| `public_bp` | `/` | Landing page. No authentication required. |
| `auth_bp` | `/login`, `/register`, `/logout` | Session-based authentication with bcrypt password hashing. |
| `dashboard_bp` | `/dashboard`, `/api/chart/*` | Main dashboard view with six chart API endpoints. |
| `portfolio_bp` | `/portfolio/*`, `/api/portfolio/risk-preview` | Portfolio CRUD, weight editing, and live risk preview. |
| `asset_bp` | `/asset/<id>` | Individual asset detail pages. |
| `history_bp` | `/history`, `/history/compare/*`, `/history/revert/*` | Version history browsing, comparison, and revert. |
| `reporting_bp` | `/reports` | User-facing and admin reports. |
| `admin_bp` | `/admin` | Admin console and user management. |

---

## Services

All service modules live under `app/services/`.

### RiskService

Pure mathematical computation with no database or API dependencies. All data is passed in as function arguments.

Computes:
- Concentration metrics and Herfindahl-Hirschman Index (HHI)
- Volatility contributions per asset
- Sharpe ratio
- Beta versus BTC
- Value at Risk (VaR)
- Diversification score
- Correlation matrix
- Portfolio returns
- Human-readable risk interpretations

### PortfolioService

Manages the full portfolio lifecycle:
- CRUD operations on portfolios
- Version management (create, increment, diff, revert)
- Weight normalization (ensures weights sum to 100%)
- Predefined template loading
- Diff computation between versions

### MarketDataService

Implements a smart caching layer in front of external price APIs:
- Caches current prices in the database with a 1-day TTL
- Caches historical prices with an 80% data completeness threshold
- Falls back to CoinGecko API when cached data is stale or missing

### CoinGeckoClient

Thin HTTP wrapper around the CoinGecko API with built-in rate limiting (25 requests per minute, sliding window).

Endpoints:
- `get_prices` -- current spot prices
- `get_coin_markets` -- market metadata and rankings
- `get_market_chart` -- historical price series

### AuthService

Handles user authentication workflows:
- Registration with email and password validation
- Password hashing via bcrypt
- Login authentication
- Disabled account detection and rejection

### AdminService

Provides administrative operations:
- User listing and search
- Account enable/disable toggling
- Password reset
- Audit action logging

### ReportingService

Generates analytical reports:
- Per-portfolio summary reports for individual users
- System-wide aggregate reports for administrators

---

## Data Flow Examples

### Dashboard Load

```
Browser GET /dashboard
    |
    v
dashboard route
    |-- PortfolioService.get_user_portfolios()
    |-- Build Holding objects from active version
    |-- MarketDataService.get_cached_prices()
    |-- RiskService.compute_all_metrics(price_histories)
    |-- RiskService.compute_all_returns(price_histories)
    |-- Render template with metrics, returns, portfolio data
    |
    v
Browser receives HTML
    |-- Fires 6 async requests to /api/chart/* endpoints
    |-- Plotly.js renders interactive charts from JSON responses
```

### Live Risk Preview (AJAX)

```
User adjusts weights in portfolio editor
    |
    v
JavaScript debounces input (500ms)
    |-- POST /api/portfolio/risk-preview (JSON payload)
    |
    v
portfolio route
    |-- Build Holding objects from JSON payload
    |-- Fetch prices from PriceDataDaily table
    |-- RiskService.compute_all_metrics()
    |-- RiskService.compute_all_returns()
    |-- Return JSON response
    |
    v
JavaScript updates DOM in real time
```

### Portfolio Update

```
User submits new weights via form POST
    |
    v
portfolio route
    |-- PortfolioService.update_portfolio()
        |-- Validate weights sum to 100%
        |-- Create new PortfolioVersion (incremented version_num)
        |-- Save PortfolioHolding records for each asset
        |-- Compute diff from previous version
        |-- Save Transaction record
    |
    v
Redirect to analysis page
```

---

## Configuration

Three configuration classes are defined in `app/config.py`:

| Class | Key Settings |
|-------|-------------|
| `DevelopmentConfig` | `DEBUG=True`, `DATABASE_URL` from environment |
| `TestConfig` | `TESTING=True`, SQLite in-memory database, CSRF disabled |
| `ProductionConfig` | `DEBUG=False`, `DATABASE_URL` from environment |

---

## Extensions

Shared extension instances are declared in `app/extensions.py` and initialized in the app factory:

```python
db = SQLAlchemy()
login_manager = LoginManager()   # login_view = 'auth.login'
csrf = CSRFProtect()
```

---

## Frontend Architecture

- **Templating**: Jinja2 templates extending a shared `base.html` layout.
- **Theming**: CSS custom properties enable light and dark theme switching.
- **Charts**: Plotly.js (loaded via CDN) renders all interactive charts.
- **Interactivity**: Vanilla JavaScript handles AJAX risk preview requests and weight management.
- **Build tools**: None required. No frontend framework or bundler is used.

---

## Security

| Concern | Implementation |
|---------|---------------|
| Password storage | bcrypt hashing with default cost factor |
| CSRF protection | Flask-WTF CSRFProtect on all form submissions |
| CSRF exemptions | JSON API endpoints only (e.g., risk-preview) |
| Session management | Flask-Login with server-side sessions |
| Access control | Role-based (NORMAL vs ADMIN) with decorator enforcement |
| Resource authorization | Portfolio ownership verification on all operations |
| SQL injection | Prevented via SQLAlchemy parameterized queries |
