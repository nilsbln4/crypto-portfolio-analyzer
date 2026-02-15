# CRPA API Reference

> Crypto Portfolio Analyzer (CRPA) -- Complete endpoint reference for the Flask web application.

---

## Table of Contents

- [Public Routes](#public-routes)
- [Authentication](#authentication)
- [Dashboard](#dashboard)
  - [Chart API Endpoints](#chart-api-endpoints-json)
- [Portfolio](#portfolio)
  - [Risk Preview API](#risk-preview-api-json)
- [Asset](#asset)
- [History](#history)
- [Reporting](#reporting)
- [Admin](#admin)
- [Authentication and Authorization](#authentication-and-authorization)
- [Error Handling](#error-handling)

---

## Public Routes

Blueprint: `public_bp`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/`  | None | Landing page. Renders `public/home.html`. |

---

## Authentication

Blueprint: `auth_bp`

### `GET /login`

Render the login form.

- **Auth:** None
- **Response:** HTML login page

### `POST /login`

Authenticate a user and start a session.

- **Auth:** None
- **Parameters:**

| Field      | Type   | Required | Description          |
|------------|--------|----------|----------------------|
| `email`    | string | Yes      | User email address   |
| `password` | string | Yes      | User password        |

- **Success:** Redirect to `/dashboard`
- **Failure:** Re-render login form with flash message

### `GET /register`

Render the registration form.

- **Auth:** None
- **Response:** HTML registration page

### `POST /register`

Create a new user account.

- **Auth:** None
- **Parameters:**

| Field      | Type   | Required | Description          |
|------------|--------|----------|----------------------|
| `email`    | string | Yes      | User email address   |
| `password` | string | Yes      | User password        |

- **Success:** Redirect to `/login`
- **Failure:** Re-render registration form with flash message

### `GET /logout`

Clear the current session and log the user out.

- **Auth:** `@login_required`
- **Response:** Redirect to `/`

---

## Dashboard

Blueprint: `dashboard_bp` -- All routes require `@login_required`.

### `GET /dashboard`

Main dashboard view displaying portfolio metrics, returns, and chart placeholders.

- **Auth:** `@login_required`
- **Query Parameters:**

| Param          | Type | Required | Description                        |
|----------------|------|----------|------------------------------------|
| `portfolio_id` | int  | No       | Select a specific portfolio to view |

- **Response:** HTML dashboard page

---

### Chart API Endpoints (JSON)

All chart endpoints require `@login_required` and return JSON responses.

#### `GET /api/chart/allocation`

Asset allocation breakdown by weight.

- **Query Parameters:**

| Param          | Type | Required | Description                        |
|----------------|------|----------|------------------------------------|
| `portfolio_id` | int  | No       | Target portfolio (defaults to active) |

- **Response:**

```json
{
  "labels": ["BTC", "ETH", "SOL"],
  "values": [50.0, 30.0, 20.0],
  "categories": ["Layer 1", "Layer 1", "Layer 1"]
}
```

#### `GET /api/chart/sector`

Sector exposure aggregated by asset category.

- **Response:**

```json
{
  "labels": ["Layer 1", "DeFi", "Stablecoin"],
  "values": [60.0, 30.0, 10.0]
}
```

#### `GET /api/chart/historical`

Historical price series per asset, rebased to 100.

- **Response:**

```json
{
  "series": [
    {
      "name": "BTC",
      "dates": ["2025-01-01", "2025-01-02"],
      "values": [100.0, 102.3]
    },
    {
      "name": "ETH",
      "dates": ["2025-01-01", "2025-01-02"],
      "values": [100.0, 98.7]
    }
  ]
}
```

#### `GET /api/chart/performance`

Weighted portfolio performance index, rebased to 100.

- **Response:**

```json
{
  "dates": ["2025-01-01", "2025-01-02", "2025-01-03"],
  "values": [100.0, 101.5, 99.8]
}
```

#### `GET /api/chart/correlation`

NxN Pearson correlation matrix across portfolio assets.

- **Response:**

```json
{
  "symbols": ["BTC", "ETH", "SOL"],
  "matrix": [
    [1.0, 0.85, 0.72],
    [0.85, 1.0, 0.68],
    [0.72, 0.68, 1.0]
  ]
}
```

#### `GET /api/chart/returns`

Per-asset period returns over 7-day and 30-day windows.

- **Response:**

```json
{
  "symbols": ["BTC", "ETH", "SOL"],
  "returns_7d": [2.5, -1.3, 5.8],
  "returns_30d": [8.1, 3.4, 12.6]
}
```

---

## Portfolio

Blueprint: `portfolio_bp` -- All routes require `@login_required`.

### `GET /portfolio/analysis`

Portfolio analysis page with weight editor and risk panel.

- **Response:** HTML analysis page

### `GET /portfolio/analysis/<portfolio_id>`

Analysis view for a specific portfolio.

- **Path Parameters:**

| Param          | Type | Description          |
|----------------|------|----------------------|
| `portfolio_id` | int  | Target portfolio ID  |

- **Response:** HTML analysis page for the specified portfolio

### `POST /portfolio/create`

Create a new empty portfolio.

- **Parameters:**

| Field  | Type   | Required | Description        |
|--------|--------|----------|--------------------|
| `name` | string | Yes      | Portfolio name     |

- **Success:** Redirect to the new portfolio's analysis page

### `POST /portfolio/<portfolio_id>/rename`

Rename an existing portfolio.

- **Path Parameters:**

| Param          | Type | Description          |
|----------------|------|----------------------|
| `portfolio_id` | int  | Target portfolio ID  |

- **Parameters:**

| Field  | Type   | Required | Description        |
|--------|--------|----------|--------------------|
| `name` | string | Yes      | New portfolio name |

- **Success:** Redirect back with flash confirmation

### `POST /portfolio/<portfolio_id>/delete`

Soft-delete a portfolio (marks as deleted without removing data).

- **Path Parameters:**

| Param          | Type | Description          |
|----------------|------|----------------------|
| `portfolio_id` | int  | Target portfolio ID  |

- **Success:** Redirect to `/dashboard` with flash confirmation

### `GET /portfolio/adjustments`

Entry point for portfolio adjustments. Redirects to the analysis page if the user has existing portfolios; otherwise renders the template loader.

- **Response:** Redirect or HTML template loader page

### `POST /portfolio/adjustments`

Perform a portfolio adjustment action. The `action` field determines behavior.

- **Parameters (common):**

| Field    | Type   | Required | Description                              |
|----------|--------|----------|------------------------------------------|
| `action` | string | Yes      | `load_predefined` or `update_allocations` |

**Action: `load_predefined`**

Load a starter template portfolio.

| Field           | Type   | Required | Description              |
|-----------------|--------|----------|--------------------------|
| `template_name` | string | Yes      | Name of the template     |

**Action: `update_allocations`**

Update asset weights for a portfolio. Creates a new version.

| Field                  | Type   | Required | Description                                  |
|------------------------|--------|----------|----------------------------------------------|
| `portfolio_id`         | int    | Yes      | Target portfolio ID                          |
| `weight_<asset_id>`    | float  | Yes      | Weight for each asset (one field per asset)  |
| `normalize`            | bool   | No       | Normalize weights to sum to 100%             |

- **Success:** Redirect to analysis page with the updated portfolio

---

### Risk Preview API (JSON)

#### `POST /api/portfolio/risk-preview`

Compute risk metrics for a hypothetical set of holdings without persisting changes. This endpoint is **CSRF exempt**.

- **Auth:** `@login_required`
- **Content-Type:** `application/json`
- **Request Body:**

```json
{
  "holdings": {
    "1": 50.0,
    "2": 30.0,
    "3": 20.0
  }
}
```

Each key is an `asset_id` (string) and each value is the portfolio weight (float).

- **Response:**

```json
{
  "top1_concentration": 60.0,
  "top3_concentration": 95.0,
  "hhi": 4600.0,
  "stablecoin_exposure": 10.0,
  "sharpe_ratio": 0.4521,
  "var_95": 3.21,
  "portfolio_beta": 0.8734,
  "diversification_score": 42.5,
  "interpretations": [
    "Portfolio is highly concentrated in a single asset.",
    "Stablecoin exposure is within normal range."
  ],
  "sector_exposure": {
    "Layer 1": 60.0,
    "DeFi": 30.0
  },
  "portfolio_return_1d": 1.23,
  "portfolio_return_7d": -2.45,
  "portfolio_return_30d": 8.12,
  "portfolio_return_90d": 15.67
}
```

**Response Fields:**

| Field                    | Type          | Description                                           |
|--------------------------|---------------|-------------------------------------------------------|
| `top1_concentration`     | float         | Weight of the largest single holding (%)              |
| `top3_concentration`     | float         | Combined weight of the top 3 holdings (%)             |
| `hhi`                    | float         | Herfindahl-Hirschman Index (0--10000)                 |
| `stablecoin_exposure`    | float         | Total weight allocated to stablecoins (%)             |
| `sharpe_ratio`           | float         | Risk-adjusted return (annualized)                     |
| `var_95`                 | float         | Value at Risk at 95% confidence (%)                   |
| `portfolio_beta`         | float         | Beta relative to BTC benchmark                        |
| `diversification_score`  | float         | Composite diversification score (0--100)              |
| `interpretations`        | array[string] | Human-readable risk commentary                        |
| `sector_exposure`        | object        | Weight breakdown by sector category                   |
| `portfolio_return_1d`    | float         | Weighted portfolio return over 1 day (%)              |
| `portfolio_return_7d`    | float         | Weighted portfolio return over 7 days (%)             |
| `portfolio_return_30d`   | float         | Weighted portfolio return over 30 days (%)            |
| `portfolio_return_90d`   | float         | Weighted portfolio return over 90 days (%)            |

---

## Asset

Blueprint: `asset_bp`

### `GET /asset/<asset_id>`

Asset detail page. The identifier can be a numeric ID, a ticker symbol, or a CoinGecko ID.

- **Auth:** `@login_required`
- **Path Parameters:**

| Param      | Type       | Description                                |
|------------|------------|--------------------------------------------|
| `asset_id` | int/string | Asset ID, ticker symbol, or coingecko_id   |

- **Response:** HTML asset detail page

---

## History

Blueprint: `history_bp` -- All routes require `@login_required`.

### `GET /history`

List all transactions for the current user, ordered by date descending.

- **Response:** HTML transaction history page

### `GET /history/version/<version_id>`

View the details of a specific portfolio version.

- **Path Parameters:**

| Param        | Type | Description             |
|--------------|------|-------------------------|
| `version_id` | int  | Portfolio version ID    |

- **Response:** HTML version detail page

### `GET /history/compare/<version_a_id>/<version_b_id>`

Side-by-side comparison of two portfolio versions showing weight differences and risk metric deltas.

- **Path Parameters:**

| Param          | Type | Description                  |
|----------------|------|------------------------------|
| `version_a_id` | int  | First portfolio version ID   |
| `version_b_id` | int  | Second portfolio version ID  |

- **Response:** HTML comparison page

### `POST /history/revert/<version_id>`

Revert a portfolio to a previous version. This creates a new version with the holdings from the target version rather than overwriting history.

- **Path Parameters:**

| Param        | Type | Description                          |
|--------------|------|--------------------------------------|
| `version_id` | int  | Version ID to revert to              |

- **Success:** Redirect to the analysis page with flash confirmation

---

## Reporting

Blueprint: `reporting_bp`

### `GET /reports`

User report page showing portfolio summaries. If the current user has admin privileges, the page also includes system-wide statistics.

- **Auth:** `@login_required`
- **Response:** HTML reports page

---

## Admin

Blueprint: `admin_bp` -- All routes require `@login_required` and **ADMIN** role.

### `GET /admin`

Admin console displaying the user list and system statistics.

- **Response:** HTML admin console page
- **Error:** `403 Forbidden` if the user is not an admin

### `POST /admin/disable/<user_id>`

Disable a user account.

- **Path Parameters:**

| Param     | Type | Description   |
|-----------|------|---------------|
| `user_id` | int  | Target user   |

- **Success:** Redirect to `/admin` with flash confirmation
- **Error:** `403 Forbidden` if the user is not an admin

### `POST /admin/enable/<user_id>`

Enable a previously disabled user account.

- **Path Parameters:**

| Param     | Type | Description   |
|-----------|------|---------------|
| `user_id` | int  | Target user   |

- **Success:** Redirect to `/admin` with flash confirmation
- **Error:** `403 Forbidden` if the user is not an admin

### `POST /admin/reset-password/<user_id>`

Reset a user's password.

- **Path Parameters:**

| Param     | Type | Description   |
|-----------|------|---------------|
| `user_id` | int  | Target user   |

- **Success:** Redirect to `/admin` with flash confirmation
- **Error:** `403 Forbidden` if the user is not an admin

---

## Authentication and Authorization

| Rule | Detail |
|------|--------|
| Public routes | `/`, `/login`, `/register` are accessible without authentication. |
| Login required | All other routes are protected by the `@login_required` decorator. Unauthenticated requests are redirected to `/login`. |
| Admin guard | Admin routes verify `current_user.is_admin()` and return **403 Forbidden** if the check fails. |
| Portfolio ownership | Portfolio operations verify `portfolio.user_id == current_user.id` before proceeding. Unauthorized access returns **403**. |
| CSRF protection | All `POST` form submissions require a valid CSRF token. The sole exception is the `/api/portfolio/risk-preview` JSON endpoint, which is CSRF exempt. |

---

## Error Handling

### HTML Routes

- Invalid or unauthorized portfolio/version lookups produce a flash message and redirect the user to a safe page (typically `/dashboard` or `/portfolio/analysis`).

### JSON API Endpoints

API endpoints return structured error responses with appropriate HTTP status codes.

| Status Code | Condition                  | Response Body                          |
|-------------|----------------------------|----------------------------------------|
| `400`       | Missing or invalid data    | `{"error": "Description of the issue"}` |
| `403`       | Unauthorized access        | `{"error": "Description of the issue"}` |
