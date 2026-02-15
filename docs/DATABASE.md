# CRPA Database Schema

> **Crypto Portfolio Analyzer** -- Flask-SQLAlchemy ORM
> All models are defined using SQLAlchemy declarative base via `flask_sqlalchemy.SQLAlchemy`.
> Column types, constraints, and relationships documented below reflect the Python model
> definitions in `app/models/`. The underlying database engine is configurable (SQLite for
> development, PostgreSQL recommended for production).

---

## Table of Contents

1. [User](#1-user)
2. [Asset](#2-asset)
3. [Portfolio](#3-portfolio)
4. [PortfolioVersion](#4-portfolioversion)
5. [PortfolioHolding](#5-portfolioholding)
6. [MarketDataDaily](#6-marketdatadaily)
7. [RiskSnapshot](#7-risksnapshot)
8. [Transaction](#8-transaction)
9. [AdminAction](#9-adminaction)
10. [Entity Relationship Diagram](#10-entity-relationship-diagram)
11. [Design Decisions](#11-design-decisions)

---

## 1. User

**Table name:** `users`
**Source file:** `app/models/user.py`
**Mixins:** `flask_login.UserMixin`

Represents an authenticated user of the platform. Supports two roles -- `NORMAL` and `ADMIN`.
Soft-delete semantics are achieved via the `is_active` flag; deactivated accounts remain in the
database for audit continuity.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique user identifier. |
| `email` | `String(255)` | `UNIQUE`, `NOT NULL`, `INDEX` | -- | User login email address. |
| `password_hash` | `String(255)` | `NOT NULL` | -- | Bcrypt / werkzeug-hashed password. |
| `role` | `String(10)` | `NOT NULL` | `'NORMAL'` | Authorization role. One of `NORMAL` or `ADMIN`. |
| `is_active` | `Boolean` | `NOT NULL` | `True` | Soft-delete flag. `False` disables login without removing the row. |
| `created_at` | `DateTime` | `NOT NULL` | `datetime.now(timezone.utc)` | Timestamp of account creation (UTC). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy |
|---|---|---|---|---|
| `portfolios` | `Portfolio` | One-to-Many | `owner` | `dynamic` |
| `transactions` | `Transaction` | One-to-Many | (via `Transaction.user`) | default |

### Key Constraints

- **Primary Key:** `id`
- **Unique:** `email`
- **Index:** `email` (explicit B-tree index for login lookups)

---

## 2. Asset

**Table name:** `assets`
**Source file:** `app/models/asset.py`

Reference table for all supported cryptocurrency assets. Each row maps a ticker symbol to its
CoinGecko API identifier. Assets are shared across all users and portfolios.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique asset identifier. |
| `symbol` | `String(20)` | `NOT NULL` | -- | Ticker symbol (e.g. `BTC`, `ETH`). |
| `name` | `String(100)` | `NOT NULL` | -- | Full display name (e.g. `Bitcoin`, `Ethereum`). |
| `coingecko_id` | `String(100)` | `UNIQUE`, `NOT NULL` | -- | CoinGecko API slug used for data fetching. |
| `category` | `String(50)` | `NOT NULL` | -- | Asset classification (e.g. `layer-1`, `defi`, `stablecoin`). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy |
|---|---|---|---|---|
| `market_data` | `MarketDataDaily` | One-to-Many | `asset` | `dynamic` |

### Key Constraints

- **Primary Key:** `id`
- **Unique:** `coingecko_id`

---

## 3. Portfolio

**Table name:** `portfolios`
**Source file:** `app/models/portfolio.py`

Top-level container owned by a single user. A portfolio does not directly store holdings; instead,
it references an ordered chain of `PortfolioVersion` snapshots. This supports immutable versioning
of allocation changes over time.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique portfolio identifier. |
| `user_id` | `Integer` | `FOREIGN KEY (users.id)`, `NOT NULL` | -- | Owning user. |
| `name` | `String(100)` | `NOT NULL` | -- | User-defined portfolio label. |
| `is_active` | `Boolean` | `NOT NULL` | `True` | Soft-delete flag. `False` hides the portfolio without removing data. |
| `created_at` | `DateTime` | `NOT NULL` | `datetime.now(timezone.utc)` | Timestamp of portfolio creation (UTC). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy | Cascade |
|---|---|---|---|---|---|
| `versions` | `PortfolioVersion` | One-to-Many | `portfolio` | `dynamic` | `all, delete-orphan` |
| `transactions` | `Transaction` | One-to-Many | (via `Transaction.portfolio`) | default | -- |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `user_id` --> `users.id`

---

## 4. PortfolioVersion

**Table name:** `portfolio_versions`
**Source file:** `app/models/portfolio.py`

An immutable point-in-time snapshot of a portfolio's composition. Each time a user modifies their
allocation, a new version is created with an incremented `version_num`. Previous versions are never
modified, preserving a complete edit history.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique version identifier. |
| `portfolio_id` | `Integer` | `FOREIGN KEY (portfolios.id)`, `NOT NULL` | -- | Parent portfolio. |
| `version_num` | `Integer` | `NOT NULL` | -- | Monotonically increasing version counter within a portfolio. |
| `created_at` | `DateTime` | `NOT NULL` | `datetime.now(timezone.utc)` | Timestamp of version creation (UTC). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy | Cascade |
|---|---|---|---|---|---|
| `holdings` | `PortfolioHolding` | One-to-Many | `version` | `joined` | `all, delete-orphan` |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `portfolio_id` --> `portfolios.id`
- **Unique Composite:** `(portfolio_id, version_num)` -- constraint name `uq_portfolio_version`

---

## 5. PortfolioHolding

**Table name:** `portfolio_holdings`
**Source file:** `app/models/portfolio.py`

A single asset allocation line within a portfolio version. The `weight_pct` field represents the
percentage weight of the asset in the version's overall composition. The sum of all `weight_pct`
values within a version should equal 100.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique holding identifier. |
| `version_id` | `Integer` | `FOREIGN KEY (portfolio_versions.id)`, `NOT NULL` | -- | Parent version snapshot. |
| `asset_id` | `Integer` | `FOREIGN KEY (assets.id)`, `NOT NULL` | -- | Referenced cryptocurrency asset. |
| `weight_pct` | `Numeric(6,3)` | `NOT NULL`, `CHECK (0 <= weight_pct <= 100)` | -- | Allocation weight as a percentage (e.g. `25.500` = 25.5%). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy |
|---|---|---|---|---|
| `asset` | `Asset` | Many-to-One | -- | `joined` |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `version_id` --> `portfolio_versions.id`
- **Foreign Key:** `asset_id` --> `assets.id`
- **Unique Composite:** `(version_id, asset_id)` -- constraint name `uq_version_asset`
- **Check:** `weight_pct >= 0 AND weight_pct <= 100` -- constraint name `ck_weight_range`

---

## 6. MarketDataDaily

**Table name:** `market_data_daily`
**Source file:** `app/models/market_data.py`

Stores end-of-day price and volume data for each asset, sourced from the CoinGecko API. One row
per asset per calendar date. This table powers historical performance charts, return calculations,
and risk analytics.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique record identifier. |
| `asset_id` | `Integer` | `FOREIGN KEY (assets.id)`, `NOT NULL` | -- | Asset this data point belongs to. |
| `date` | `Date` | `NOT NULL` | -- | Calendar date of the observation. |
| `price` | `Numeric(20,8)` | `NOT NULL` | -- | Closing price in USD. Eight decimal places accommodate low-value tokens. |
| `market_cap` | `Numeric(24,2)` | `NULLABLE` | `NULL` | Total market capitalization in USD at close. |
| `volume` | `Numeric(24,2)` | `NULLABLE` | `NULL` | 24-hour trading volume in USD. |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy |
|---|---|---|---|---|
| -- | `Asset` | Many-to-One | `market_data` | -- |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `asset_id` --> `assets.id`
- **Unique Composite:** `(asset_id, date)` -- constraint name `uq_asset_date`

---

## 7. RiskSnapshot

**Table name:** `risk_snapshots`
**Source file:** `app/models/risk_snapshot.py`

Persists computed risk metrics for a specific portfolio version. The `metrics_json` column stores
a flexible JSON payload containing volatility, VaR, Sharpe ratio, correlation matrices, and any
other analytics produced by the risk engine. Snapshots are append-only; recomputation creates a
new row rather than updating an existing one.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique snapshot identifier. |
| `version_id` | `Integer` | `FOREIGN KEY (portfolio_versions.id)`, `NOT NULL` | -- | The portfolio version these metrics apply to. |
| `computed_at` | `DateTime` | `NOT NULL` | `datetime.now(timezone.utc)` | Timestamp of computation (UTC). |
| `metrics_json` | `JSON` | `NOT NULL` | -- | Serialized risk metrics payload (structure defined by the risk service). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy |
|---|---|---|---|---|
| -- | `PortfolioVersion` | Many-to-One | -- | default |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `version_id` --> `portfolio_versions.id`

---

## 8. Transaction

**Table name:** `transactions`
**Source file:** `app/models/transaction.py`

Immutable audit log of every user-initiated change to a portfolio. Each row records who made the
change, which portfolio was affected, the resulting version (if applicable), the operation type,
and a JSON diff describing exactly what changed.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique transaction identifier. |
| `user_id` | `Integer` | `FOREIGN KEY (users.id)`, `NOT NULL` | -- | User who initiated the action. |
| `portfolio_id` | `Integer` | `FOREIGN KEY (portfolios.id)`, `NOT NULL` | -- | Affected portfolio. |
| `version_id` | `Integer` | `FOREIGN KEY (portfolio_versions.id)`, `NULLABLE` | `NULL` | Resulting portfolio version (NULL for delete operations). |
| `type` | `String(10)` | `NOT NULL` | -- | Operation type (e.g. `CREATE`, `UPDATE`, `DELETE`). |
| `diff_json` | `JSON` | `NULLABLE` | `NULL` | JSON payload describing the change delta. |
| `created_at` | `DateTime` | `NOT NULL` | `datetime.now(timezone.utc)` | Timestamp of the action (UTC). |

### Relationships

| Relationship | Target Model | Type | Back-reference | Lazy Strategy |
|---|---|---|---|---|
| `user` | `User` | Many-to-One | `transactions` | default |
| `portfolio` | `Portfolio` | Many-to-One | `transactions` | default |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `user_id` --> `users.id`
- **Foreign Key:** `portfolio_id` --> `portfolios.id`
- **Foreign Key:** `version_id` --> `portfolio_versions.id` (nullable)

---

## 9. AdminAction

**Table name:** `admin_actions`
**Source file:** `app/models/transaction.py`

Immutable audit trail of administrative operations performed on user accounts. Records both the
administrator performing the action and the target user, enabling compliance review and
accountability tracking.

### Columns

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY` | Auto-increment | Unique action identifier. |
| `admin_user_id` | `Integer` | `FOREIGN KEY (users.id)`, `NOT NULL` | -- | Administrator who performed the action. |
| `action_type` | `String(20)` | `NOT NULL` | -- | Describes the administrative action (e.g. `DEACTIVATE`, `REACTIVATE`, `PROMOTE`). |
| `target_user_id` | `Integer` | `FOREIGN KEY (users.id)`, `NOT NULL` | -- | User account the action was performed upon. |
| `created_at` | `DateTime` | `NOT NULL` | `datetime.now(timezone.utc)` | Timestamp of the action (UTC). |

### Relationships

| Relationship | Target Model | Type | Foreign Keys | Lazy Strategy |
|---|---|---|---|---|
| `admin` | `User` | Many-to-One | `admin_user_id` | default |
| `target` | `User` | Many-to-One | `target_user_id` | default |

### Key Constraints

- **Primary Key:** `id`
- **Foreign Key:** `admin_user_id` --> `users.id`
- **Foreign Key:** `target_user_id` --> `users.id`

---

## 10. Entity Relationship Diagram

```
 +-----------------+          +-----------------+
 |     users       |          |     assets      |
 |-----------------|          |-----------------|
 | PK id           |          | PK id           |
 |    email        |          |    symbol        |
 |    password_hash|          |    name          |
 |    role         |          |    coingecko_id  |
 |    is_active    |          |    category      |
 |    created_at   |          +---------+-------+
 +----+-----+------+                    |
      |     |                           |
      |     |  +------------------------+---------------------------+
      |     |  |                        |                           |
      |     |  |  +------------------+  |  +---------------------+  |
      |     |  |  | market_data_daily|  |  | portfolio_holdings  |  |
      |     |  |  |------------------|  |  |---------------------|  |
      |     |  |  | PK id            |  |  | PK id               |  |
      |     |  |  | FK asset_id  ----+--+  | FK version_id  -----+--+--+
      |     |  |  |    date          |     | FK asset_id  -------+  |  |
      |     |  |  |    price         |     |    weight_pct       |  |  |
      |     |  |  |    market_cap    |     +---------------------+  |  |
      |     |  |  |    volume        |                              |  |
      |     |  |  +------------------+                              |  |
      |     |  |                                                    |  |
      |     |  |                                                    |  |
      |  +--+--+----------+        +--------------------+           |  |
      |  |  portfolios    |        | portfolio_versions |           |  |
      |  |----------------|        |--------------------|           |  |
      |  | PK id          |        | PK id              +-----------+  |
      |  | FK user_id ----+--+     | FK portfolio_id ---+--+           |
      |  |    name        |  |     |    version_num     |  |           |
      |  |    is_active   |  |     |    created_at      |  |           |
      |  |    created_at  |  |     +--------+-----------+  |           |
      |  +-------+--------+  |              |              |           |
      |          |            |              |              |           |
      |          +------+     +--------------+              |           |
      |                 |                                   |           |
      |  +--------------+---+        +------------------+  |           |
      |  |  transactions    |        | risk_snapshots   |  |           |
      |  |------------------|        |------------------|  |           |
      |  | PK id            |        | PK id            |  |           |
      +--+ FK user_id       |        | FK version_id ---+--+-----------+
         | FK portfolio_id -+--+     |    computed_at   |
         | FK version_id ---+--+--+  |    metrics_json  |
         |    type          |     |  +------------------+
         |    diff_json     |     |
         |    created_at    |     |
         +------------------+     |
                                  |
 +-------------------+            |
 |  admin_actions    |            |
 |-------------------|            |
 | PK id             |            |
 | FK admin_user_id -+-- users.id |
 | FK target_user_id +-- users.id |
 |    action_type    |
 |    created_at     |
 +-------------------+
```

### Relationship Summary

```
users              1 ---< N   portfolios             (user_id)
portfolios         1 ---< N   portfolio_versions     (portfolio_id)
portfolio_versions 1 ---< N   portfolio_holdings     (version_id)
assets             1 ---< N   portfolio_holdings     (asset_id)
assets             1 ---< N   market_data_daily      (asset_id)
portfolio_versions 1 ---< N   risk_snapshots         (version_id)
users              1 ---< N   transactions           (user_id)
portfolios         1 ---< N   transactions           (portfolio_id)
portfolio_versions 1 ---< N   transactions           (version_id, nullable)
users              1 ---< N   admin_actions           (admin_user_id)
users              1 ---< N   admin_actions           (target_user_id)
```

---

## 11. Design Decisions

### 11.1 Immutable Portfolio Versioning

Portfolio compositions are never edited in place. Instead, each modification creates a new
`PortfolioVersion` with an incremented `version_num`, along with a fresh set of
`PortfolioHolding` rows. This design provides several advantages:

- **Complete history.** Every past allocation is preserved and queryable.
- **Reproducible analytics.** Risk snapshots are permanently bound to a specific version, ensuring
  that historical metric computations remain meaningful even after the user changes their portfolio.
- **Conflict avoidance.** Concurrent reads never observe partially-updated allocation data because
  writes target a new version row rather than mutating existing rows.

The `(portfolio_id, version_num)` unique constraint guarantees version ordering integrity.

### 11.2 Soft Deletes

Both the `User` and `Portfolio` models include an `is_active` boolean flag rather than supporting
physical row deletion. This approach:

- Preserves referential integrity for foreign keys in `transactions`, `admin_actions`, and
  `risk_snapshots`.
- Maintains a complete audit trail even after an entity is logically removed.
- Enables account/portfolio reactivation without data loss.

Application-layer queries should filter on `is_active = True` for user-facing views while
administrative and audit views may access inactive records.

### 11.3 Audit Trail (Transactions and AdminActions)

Two dedicated append-only tables record all meaningful state changes:

- **`transactions`** logs every portfolio-level operation (`CREATE`, `UPDATE`, `DELETE`) with a
  JSON diff payload capturing exactly what changed. The nullable `version_id` accommodates delete
  operations where no new version is produced.
- **`admin_actions`** logs administrative user-management operations with explicit
  `admin_user_id` / `target_user_id` separation, supporting compliance and accountability review.

Both tables are insert-only by convention; rows should never be updated or deleted.

### 11.4 Flexible Risk Metrics via JSON Column

The `RiskSnapshot.metrics_json` column uses a native `JSON` type rather than a fixed set of
numeric columns. This decision reflects the evolving nature of the risk engine:

- New metrics (e.g., CVaR, maximum drawdown, Sortino ratio) can be added without schema migrations.
- The risk service defines and documents the JSON structure independently of the database schema.
- Multiple snapshots per version are permitted, allowing metric recomputation with updated market
  data without overwriting prior results.

### 11.5 Decimal Precision

Monetary and percentage values use `Numeric` (Python `Decimal`) rather than floating-point types
to avoid rounding errors in financial calculations:

| Column | Precision | Rationale |
|---|---|---|
| `weight_pct` | `Numeric(6,3)` | Supports weights from `0.000` to `100.000` with millesimal precision. |
| `price` | `Numeric(20,8)` | Eight decimal places accommodate micro-cap tokens with sub-cent prices. |
| `market_cap` | `Numeric(24,2)` | Up to 22 integer digits covers multi-trillion USD valuations. |
| `volume` | `Numeric(24,2)` | Same scale as market cap for consistency. |

### 11.6 Check Constraints

The `ck_weight_range` constraint on `portfolio_holdings.weight_pct` enforces that allocation
weights remain within the valid `[0, 100]` range at the database level, providing a safety net
independent of application-layer validation.

### 11.7 Composite Unique Constraints

Three composite unique constraints enforce data integrity rules that cannot be expressed with
single-column uniqueness:

| Constraint Name | Table | Columns | Purpose |
|---|---|---|---|
| `uq_portfolio_version` | `portfolio_versions` | `(portfolio_id, version_num)` | Prevents duplicate version numbers within a portfolio. |
| `uq_version_asset` | `portfolio_holdings` | `(version_id, asset_id)` | Prevents duplicate asset entries within a single version. |
| `uq_asset_date` | `market_data_daily` | `(asset_id, date)` | Prevents duplicate price records for the same asset on the same date. |

### 11.8 Cascade Behavior

- `Portfolio.versions` is configured with `cascade='all, delete-orphan'`, meaning that if a
  portfolio row is deleted, all associated versions (and transitively their holdings) are removed.
- `PortfolioVersion.holdings` uses the same cascade policy.
- In practice, soft deletes (setting `is_active = False`) are preferred over hard deletes to
  preserve audit integrity. The cascade configuration serves as a safety net for development and
  testing scenarios.

### 11.9 Lazy Loading Strategies

Relationship loading strategies are chosen to balance query performance with convenience:

| Relationship | Strategy | Rationale |
|---|---|---|
| `User.portfolios` | `dynamic` | Users may own many portfolios; dynamic returns a query object for further filtering. |
| `Asset.market_data` | `dynamic` | Market data grows unboundedly; eager loading would be prohibitive. |
| `Portfolio.versions` | `dynamic` | Portfolios may accumulate many versions over time. |
| `PortfolioVersion.holdings` | `joined` | Holdings are few per version and almost always needed; eager join avoids N+1 queries. |
| `PortfolioHolding.asset` | `joined` | Asset metadata (symbol, name) is almost always displayed alongside holdings. |
