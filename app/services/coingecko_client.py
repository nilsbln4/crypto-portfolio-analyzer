import time
import threading
import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://api.coingecko.com/api/v3'
MAX_CALLS_PER_MINUTE = 25  # 5-call buffer below the 30/min demo limit


class RateLimiter:
    """Sliding-window rate limiter for API calls."""

    def __init__(self, max_calls, period=60):
        self._max_calls = max_calls
        self._period = period
        self._timestamps = []
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < self._period]
            if len(self._timestamps) >= self._max_calls:
                sleep_time = self._period - (now - self._timestamps[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._timestamps = [
                    t for t in self._timestamps if time.monotonic() - t < self._period
                ]
            self._timestamps.append(time.monotonic())


class CoinGeckoClientError(Exception):
    pass


class CoinGeckoClient:
    """Thin HTTP wrapper for CoinGecko API. Handles auth, rate limiting, errors."""

    def __init__(self, api_key, base_url=BASE_URL, rate_limiter=None):
        self._api_key = api_key
        self._base_url = base_url
        self._rate_limiter = rate_limiter or RateLimiter(MAX_CALLS_PER_MINUTE)
        self._session = requests.Session()
        self._session.headers.update({'x-cg-demo-api-key': api_key})

    def _get(self, endpoint, params=None):
        self._rate_limiter.acquire()
        url = f'{self._base_url}{endpoint}'
        try:
            resp = self._session.get(url, params=params, timeout=15)
        except requests.RequestException as exc:
            logger.error('CoinGecko network error: %s', exc)
            raise CoinGeckoClientError(f'Network error: {exc}') from exc

        if resp.status_code == 429:
            logger.warning('CoinGecko rate limit hit (429)')
            raise CoinGeckoClientError('Rate limit exceeded')

        if resp.status_code != 200:
            logger.error('CoinGecko error %d: %s', resp.status_code, resp.text[:200])
            raise CoinGeckoClientError(
                f'API error {resp.status_code}: {resp.text[:200]}'
            )

        return resp.json()

    def get_prices(self, coin_ids, vs_currency='usd'):
        ids_str = ','.join(coin_ids)
        return self._get('/simple/price', params={
            'ids': ids_str,
            'vs_currencies': vs_currency,
        })

    def get_coin_markets(self, coin_ids, vs_currency='usd'):
        ids_str = ','.join(coin_ids)
        return self._get('/coins/markets', params={
            'ids': ids_str,
            'vs_currency': vs_currency,
            'order': 'market_cap_desc',
            'per_page': 250,
            'page': 1,
            'sparkline': 'false',
        })

    def get_market_chart(self, coin_id, days, vs_currency='usd'):
        return self._get(f'/coins/{coin_id}/market_chart', params={
            'vs_currency': vs_currency,
            'days': str(days),
        })
