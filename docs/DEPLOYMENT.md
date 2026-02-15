# CRPA Deployment and Operations Guide

This guide covers the full deployment lifecycle for the Crypto Portfolio Analyzer (CRPA), from local development setup through production deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Environment Variables](#environment-variables)
4. [Configuration Classes](#configuration-classes)
5. [Database Setup](#database-setup)
6. [Seed Data](#seed-data)
7. [Running Tests](#running-tests)
8. [Production Deployment](#production-deployment)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before proceeding, ensure the following software is installed on the target system:

- **Python 3.10 or higher** -- Required for language feature compatibility and dependency support.
- **pip** -- Python package manager (ships with Python 3.10+).
- **PostgreSQL 14+** -- Required for production deployments. SQLite may be used for local development and testing.
- **Git** -- For cloning the repository.
- **virtualenv or venv** -- For creating isolated Python environments.

Optional but recommended:

- **Gunicorn 23.0.0** -- Production-grade WSGI server (included in `requirements.txt`).

---

## Local Development Setup

Follow these steps to set up a local development environment.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd crypto-portfolio-analyzer
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the virtual environment:

- **Linux / macOS:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The following packages and their pinned versions will be installed:

| Package             | Version  | Purpose                              |
|---------------------|----------|--------------------------------------|
| Flask               | 3.1.2    | Web framework                        |
| Flask-SQLAlchemy    | 3.1.1    | ORM and database integration         |
| Flask-Login         | 0.6.3    | User session and authentication      |
| Flask-WTF           | 1.2.2    | Form handling and CSRF protection    |
| psycopg2-binary     | 2.9.11   | PostgreSQL adapter                   |
| python-dotenv       | 1.2.1    | Environment variable loading         |
| requests            | 2.32.5   | HTTP client for API calls            |
| plotly              | 6.5.2    | Interactive chart rendering          |
| pandas              | 3.0.0    | Data analysis and manipulation       |
| bcrypt              | 5.0.0    | Password hashing                     |
| gunicorn            | 23.0.0   | Production WSGI server               |

### 4. Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
cp .env.example .env
```

If no `.env.example` file exists, create `.env` manually. See the [Environment Variables](#environment-variables) section for the full list of required values.

### 5. Initialize the Database

```bash
flask db upgrade
```

Or, if using raw initialization:

```bash
flask init-db
```

### 6. Seed the Database

```bash
flask seed
flask seed-history
```

### 7. Run the Development Server

```bash
python run.py
```

The application entry point is `run.py`, which calls `create_app()` from the `app` package and starts the Flask development server with `debug=True` enabled. The server will be available at `http://127.0.0.1:5000` by default.

---

## Environment Variables

All environment variables are loaded via `python-dotenv` from a `.env` file at application startup (see `app/config.py`). The following variables are recognized:

| Variable            | Required | Default            | Description                                                                 |
|---------------------|----------|--------------------|-----------------------------------------------------------------------------|
| `DATABASE_URL`      | Yes      | None               | Full database connection URI. PostgreSQL for production; SQLite for dev.     |
| `SECRET_KEY`        | Yes      | `dev-secret-key`   | Flask secret key for session signing and CSRF tokens. Must be unique and unpredictable in production. |
| `COINGECKO_API_KEY` | No       | None               | API key for CoinGecko cryptocurrency data. Required for live price feeds.   |
| `FLASK_ENV`         | No       | `production`       | Flask environment mode. Set to `development` for local work.                |

### Example `.env` File

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/crpa_db
SECRET_KEY=your-secure-random-secret-key-here
COINGECKO_API_KEY=CG-your-api-key-here
FLASK_ENV=development
```

**Security notice:** Never commit the `.env` file to version control. Ensure it is listed in `.gitignore`.

---

## Configuration Classes

The application uses a class-based configuration hierarchy defined in `app/config.py`. All configuration classes inherit from the base `Config` class.

### Base Config

```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
```

- `SECRET_KEY` -- Loaded from the environment with a fallback default. The default value is insecure and must be overridden in production.
- `SQLALCHEMY_TRACK_MODIFICATIONS` -- Disabled to reduce memory overhead and suppress deprecation warnings.
- `WTF_CSRF_ENABLED` -- CSRF protection is enabled globally.

### DevelopmentConfig

```python
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
```

- Enables Flask debug mode with auto-reload and interactive debugger.
- Database URI is read from the `DATABASE_URL` environment variable.

### TestConfig

```python
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False
```

- Uses an **in-memory SQLite database** (`sqlite://`) so tests run in isolation without requiring an external database server.
- CSRF protection is disabled to simplify form submission in test cases.

### ProductionConfig

```python
class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
```

- Debug mode is explicitly disabled.
- Database URI must be set via `DATABASE_URL` in the environment. A PostgreSQL connection string is expected.

---

## Database Setup

### PostgreSQL (Production)

1. Install PostgreSQL and ensure the service is running.

2. Create a database and user:

   ```sql
   CREATE USER crpa_user WITH PASSWORD 'secure_password';
   CREATE DATABASE crpa_db OWNER crpa_user;
   GRANT ALL PRIVILEGES ON DATABASE crpa_db TO crpa_user;
   ```

3. Set the `DATABASE_URL` environment variable:

   ```dotenv
   DATABASE_URL=postgresql://crpa_user:secure_password@localhost:5432/crpa_db
   ```

4. Run database migrations:

   ```bash
   flask db upgrade
   ```

### SQLite (Development and Testing)

For local development, you may use SQLite by setting `DATABASE_URL` to a file-based URI:

```dotenv
DATABASE_URL=sqlite:///crpa_dev.db
```

For testing, no configuration is needed. The `TestConfig` class automatically uses an in-memory SQLite database (`sqlite://`), which is created and destroyed with each test run.

---

## Seed Data

The application provides Flask CLI commands to populate the database with initial data.

### Seed Core Data

```bash
flask seed
```

This command loads foundational data such as supported cryptocurrencies, default portfolio templates, or reference values required for the application to function.

### Seed Historical Data

```bash
flask seed-history
```

This command loads historical price data for cryptocurrencies. This is useful for populating charts and analytics features during development without relying on live API calls.

### Notes

- Run `flask seed` before `flask seed-history`, as historical data may depend on core seed records.
- Seed commands are idempotent where possible, but re-running them on a populated database should be done with caution.
- In production, seed commands should only be run during initial deployment or as part of a controlled migration process.

---

## Running Tests

The project uses `pytest` as its test framework. Install it if it is not already available:

```bash
pip install pytest
```

### Run the Full Test Suite

```bash
pytest
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run a Specific Test File

```bash
pytest tests/test_portfolio.py
```

### Run Tests with Coverage

```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

### Test Configuration

Tests automatically use the `TestConfig` class, which provides:

- An in-memory SQLite database for complete isolation.
- `TESTING = True` for Flask test behavior adjustments.
- `WTF_CSRF_ENABLED = False` to allow form submissions without CSRF tokens.

---

## Production Deployment (Render)

The recommended deployment target is [Render](https://render.com). The repository includes all necessary configuration files.

### Deployment Files

| File           | Purpose                                                    |
|----------------|------------------------------------------------------------|
| `Procfile`     | Tells Render how to start the app via Gunicorn             |
| `build.sh`     | Build script: installs deps, seeds database, fetches prices |
| `runtime.txt`  | Pins the Python version (3.13.3)                           |

### Step-by-Step Render Deployment

#### 1. Push Code to GitHub

Create a GitHub repository and push the project code. Ensure `.env` is in `.gitignore`.

#### 2. Create a Render Account

Sign up at [render.com](https://render.com) and connect your GitHub account.

#### 3. Create a PostgreSQL Database

1. In Render dashboard, click **New** > **PostgreSQL**.
2. Choose a name (e.g., `crpa-db`) and the **Free** plan.
3. Click **Create Database**.
4. Copy the **Internal Database URL** from the database info page -- you will need it in step 5.

#### 4. Create a Web Service

1. Click **New** > **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:

| Setting          | Value                           |
|------------------|---------------------------------|
| **Name**         | `crpa` (or your choice)         |
| **Runtime**      | Python                          |
| **Build Command**| `chmod +x build.sh && ./build.sh` |
| **Start Command**| (leave blank -- uses `Procfile`) |
| **Plan**         | Free                            |

#### 5. Set Environment Variables

In the web service settings, add these environment variables:

| Variable            | Value                                        |
|---------------------|----------------------------------------------|
| `DATABASE_URL`      | *(paste the Internal Database URL from step 3)* |
| `SECRET_KEY`        | *(generate a random string, e.g., `python -c "import secrets; print(secrets.token_hex(32))"`)* |
| `COINGECKO_API_KEY` | *(your CoinGecko API key)*                   |
| `FLASK_ENV`         | `production`                                 |

**Note:** Render may provide `DATABASE_URL` starting with `postgres://`. The application automatically converts this to `postgresql://` for SQLAlchemy compatibility.

#### 6. Deploy

Click **Create Web Service**. Render will:
1. Clone the repository
2. Run `build.sh` (installs dependencies, seeds 50 assets, fetches 90-day price history)
3. Start Gunicorn via `Procfile`

The first deploy takes a few minutes due to price data fetching.

#### 7. Register and Promote Admin

1. Visit your Render URL and register a new account.
2. In Render dashboard, go to your web service > **Shell** tab.
3. Run:

```bash
flask promote-admin your-email@example.com
```

This promotes your account to ADMIN, giving you access to the admin console and user management.

#### 8. Share the URL

Your app is live. Share the Render URL with classmates -- they can register their own accounts and start building portfolios.

### Render Free Tier Notes

- The free tier spins down after 15 minutes of inactivity. The first request after a spin-down takes ~30 seconds to cold-start.
- Free PostgreSQL databases expire after 90 days. Upgrade to a paid plan for persistence.
- The `build.sh` script is idempotent -- redeployments will not duplicate seed data.

---

## Troubleshooting

### Application fails to start with "ModuleNotFoundError"

**Cause:** The virtual environment is not activated, or dependencies are not installed.

**Solution:**

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "OperationalError: could not connect to server"

**Cause:** PostgreSQL is not running or the `DATABASE_URL` is incorrect.

**Solution:**

1. Verify PostgreSQL is running:
   ```bash
   sudo systemctl status postgresql
   ```
2. Confirm the `DATABASE_URL` in `.env` matches the actual database host, port, user, and password.
3. Test the connection manually:
   ```bash
   psql -U crpa_user -h localhost -d crpa_db
   ```

### "CSRF token missing" errors in forms

**Cause:** The `SECRET_KEY` is not set or changes between requests, invalidating CSRF tokens.

**Solution:**

- Ensure `SECRET_KEY` is set to a stable value in `.env`.
- Do not use the default `dev-secret-key` in production, but ensure the value does not change between application restarts.

### "psycopg2" installation fails

**Cause:** System-level PostgreSQL development libraries are missing.

**Solution:**

- On Debian/Ubuntu:
  ```bash
  sudo apt-get install libpq-dev python3-dev
  ```
- On macOS:
  ```bash
  brew install postgresql
  ```
- Alternatively, the project uses `psycopg2-binary` (version 2.9.11), which bundles its own libraries and should not require system packages in most cases.

### Gunicorn workers timing out

**Cause:** Long-running requests, typically from CoinGecko API calls, exceed the default 30-second worker timeout.

**Solution:**

Increase the Gunicorn timeout:

```bash
gunicorn run:app --timeout 120
```

If specific API calls are consistently slow, consider implementing background task processing or caching.

### Database migration errors

**Cause:** Migration scripts are out of sync with the current database state.

**Solution:**

1. Check the current migration status:
   ```bash
   flask db current
   ```
2. If the database is empty or in an inconsistent state, reset and reapply:
   ```bash
   flask db downgrade base
   flask db upgrade
   flask seed
   flask seed-history
   ```

### Port 5000 already in use (macOS)

**Cause:** On macOS Monterey and later, AirPlay Receiver listens on port 5000 by default.

**Solution:**

- Disable AirPlay Receiver in System Settings, or
- Run the development server on a different port:
  ```bash
  flask run --port 5001
  ```

---

*This guide was written for the Crypto Portfolio Analyzer (CRPA) project. For questions or issues not covered here, consult the project maintainers or open an issue in the repository.*
