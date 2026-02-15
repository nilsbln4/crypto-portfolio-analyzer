# System Specification

## Digital Asset Portfolio Risk & Exposure Analyzer

## 1. Purpose

Build a web application that helps users understand **portfolio risk drivers** for digital-asset allocations (without executing trades). The system analyzes predefined portfolios and user-modified allocations to explain risk through concentration, volatility contribution, stablecoin exposure, and sector/narrative exposure.

## 2. Scope

### In scope

* Predefined starter portfolios (3+) that users can load
* Portfolio editing via **allocation adjustments** (add/remove assets, change weights)
* Risk analytics and interactive charting
* Portfolio version history + reporting
* Admin management + system-wide analytics
* Deployment to Duke VCM; containerization; CI/CD; security/logging artifacts

### Out of scope (explicit)

* Wallet connections, signing, smart contracts
* Real trade execution or brokerage integration
* Predictive models (“AI signals”) or performance promises
* High-frequency data or intraday candles (daily resolution is sufficient)

---

## 3. Users and Roles

### Normal user

* Registers/authenticates
* Selects a predefined portfolio
* Modifies allocations and saves new versions
* Views risk analytics, history, and reports

### Administrative user

* Views all users
* Disables user accounts
* Resets user passwords
* Views system “transactions” (portfolio changes)
* Performs analysis across all accounts (aggregate exposure/risk)

(Required by rubric.) 

---

## 4. Core Concepts and Definitions

### Portfolio

A named set of assets and target weights (sum to 100%).

### Portfolio adjustment event (system “transaction”)

A logged change to a portfolio (e.g., “BTC weight 60% → 45%”), used to satisfy transaction + history requirements.

### Risk dimensions computed

* **Concentration risk**: top-1/top-3 weights; optional HHI
* **Volatility contribution (approx.)**: weight × asset volatility over window
* **Stablecoin dependence**: sum stablecoin weights; optional peg deviation time series
* **Sector/narrative exposure**: weights aggregated by category (L1/DeFi/RWA/etc.)
* **Historical drawdown (optional but recommended)**: max drawdown over window

---

## 5. External Data Integration

### Primary REST/JSON API (required)

* **CoinGecko API** (recommended): prices, market cap, volume, categories
  (Alternatively, AlphaVantage/Finnhub for crypto if you prefer; CoinGecko is simplest for digital assets.)

### Data caching

* Cache API responses (e.g., daily prices) in DB to reduce rate limit risk and improve performance.

(Rubric: must integrate at least one REST/JSON source.) 

---

## 6. System Features and Functional Requirements

### FR-1: Authentication and Accounts

1. Users can register with email/password.
2. Users can log in/out.
3. Users have roles: NORMAL or ADMIN.
4. Session management with secure cookies.

### FR-2: Predefined Portfolios

1. System provides at least 3 starter portfolios:

   * BTC/ETH Core
   * Balanced Crypto Exposure
   * High-Risk Speculative
2. User can load a predefined portfolio into “My Portfolio”.

### FR-3: Portfolio Editing (Allocation Adjustments)

1. User can add an asset (from supported universe) and assign weight.
2. User can remove an asset.
3. User can adjust weights.
4. System validates weights sum to 100% (or provides “auto-normalize”).
5. User can save a new portfolio version.

### FR-4: Risk Analytics

1. System computes risk metrics for the active portfolio:

   * concentration metrics
   * volatility contribution (window selectable, e.g., 30d/90d)
   * stablecoin exposure
   * sector exposure
2. System explains “what’s driving risk” in plain language (short interpretation blocks).

### FR-5: Visual Dashboard and Charting

1. Provide at least three chart types (Plotly recommended): 

   * Pie/Donut: allocation (concentration)
   * Bar: volatility contribution or sector exposure
   * Line: price index or drawdown over time
2. Provide at least one custom interaction:

   * time-range slider / brush zoom on line chart **or**
   * toggles to compare “Before vs After” adjustment overlays

### FR-6: Transaction History (Portfolio Change Log)

1. Each saved portfolio change creates a transaction event record:

   * who, when, what changed (diff)
2. Users can view their history and click into a specific revision.

### FR-7: Reporting

1. User can generate a portfolio report containing:

   * current metrics
   * charts snapshots/links
   * change over time (last N versions)
2. Admin can generate system-level reports:

   * top exposures by category
   * concentration distribution across users
   * most-used starter portfolios

### FR-8: Administrative Functions (required)

1. View all users
2. Disable user accounts
3. Reset user passwords
4. View system transactions (all portfolio changes)
5. Cross-account analysis dashboard (aggregate exposure/risk) 

---

## 7. User Interface Screens (minimum 9)

Mapped 1:1 to rubric items. 

1. **Public Home** (unauthenticated)
2. **Register**
3. **Login**
4. **User Dashboard** (authenticated home)
5. **Asset Analysis Page** (single asset: price, vol proxy, category, notes)
6. **Portfolio Analysis Page** (current portfolio risk metrics)
7. **Portfolio Adjustments Page** (modify weights; “save version”)
8. **History Page** (portfolio versions + change log)
9. **Reporting Page** (generate/download/view report)
10. (Admin) **Admin Console: Users & System Analytics** *(can be a separate screen; recommended)*

Paper prototypes required and TA review in first two sprints. 

---

## 8. Data Model (Database)

Use PostgreSQL for full points (recommended). 

### Tables (suggested)

* `users` (id, email, password_hash, role, status, created_at)
* `portfolios` (id, user_id, name, created_at, is_active)
* `portfolio_versions` (id, portfolio_id, version_num, created_at)
* `portfolio_holdings` (version_id, asset_id, weight_pct)
* `assets` (id, symbol, name, coingecko_id, category)
* `market_data_daily` (asset_id, date, price, market_cap, volume)
* `risk_snapshots` (version_id, computed_at, metrics_json)
* `transactions` (id, user_id, portfolio_id, version_id, type, diff_json, created_at)
* `admin_actions` (id, admin_user_id, action_type, target_user_id, created_at)

---

## 9. Architecture

### Pattern

* Flask MVC (routes/controllers, service layer, templates/views)
* Service layer modules:

  * `MarketDataService` (API fetch + cache)
  * `PortfolioService` (versioning, validation)
  * `RiskService` (risk calculations)
  * `ReportingService` (report generation)
  * `AdminService` (user mgmt + aggregate analytics)

### Deployment topology

* Docker container for app + Docker Compose for app + DB volume persistence 
* Hosted on Duke VCM; configured to auto-start on reboot 

---

## 10. Non-Functional Requirements

* **Performance:** dashboard loads < 2s with cached data; async refresh optional
* **Security:** hashed passwords, role-based access control, input validation, CSRF protection
* **Reliability:** graceful API failure handling (fallback to cached data + user message)
* **Maintainability:** modular services, clear interfaces, unit tests for RiskService
* **Scalability:** support 1k users (basic), cache to reduce API calls
* **Availability:** app restarts automatically after VM reboot 

---

## 11. Logging and Monitoring

Implement OWASP-aligned event logging: 

* auth events (login success/fail, logout)
* admin actions (disable/reset)
* portfolio version saves (transaction events)
* API fetch failures / rate limiting
* report generation events

Provide `log_design.md` per rubric instructions. 

---

## 12. Security Analysis Deliverables

* Data Flow Diagram + STRIDE analysis 
* Semgrep scan 
* OWASP ZAP scan 

---

## 13. Testing Strategy

* Unit tests: Risk calculations (concentration, stablecoin exposure, volatility contribution)
* Integration tests: API client with mocked responses; DB persistence
* System tests: key flows (register/login → load portfolio → adjust → view history → report)
* Include test cases per screen per rubric requirement. 

---

## 14. CI/CD

GitLab pipeline: 

* Build on every commit
* Run test suite
* Run GitLab SAST
* Deploy to VCM automatically

---


