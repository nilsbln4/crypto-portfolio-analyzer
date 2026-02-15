import pytest
import responses

from app.services.coingecko_client import (
    CoinGeckoClient, CoinGeckoClientError, RateLimiter,
)

BASE = 'https://api.coingecko.com/api/v3'
TEST_KEY = 'test-api-key'


@pytest.fixture
def client():
    limiter = RateLimiter(max_calls=100, period=1)
    return CoinGeckoClient(api_key=TEST_KEY, rate_limiter=limiter)


class TestGetPrices:

    @responses.activate
    def test_returns_prices_for_multiple_coins(self, client):
        responses.add(
            responses.GET, f'{BASE}/simple/price',
            json={'bitcoin': {'usd': 70000}, 'ethereum': {'usd': 2000}},
            status=200,
        )
        result = client.get_prices(['bitcoin', 'ethereum'])
        assert result['bitcoin']['usd'] == 70000
        assert result['ethereum']['usd'] == 2000

    @responses.activate
    def test_api_key_sent_in_header(self, client):
        responses.add(responses.GET, f'{BASE}/simple/price', json={}, status=200)
        client.get_prices(['bitcoin'])
        assert responses.calls[0].request.headers['x-cg-demo-api-key'] == TEST_KEY


class TestGetCoinMarkets:

    @responses.activate
    def test_returns_batch_market_data(self, client):
        responses.add(
            responses.GET, f'{BASE}/coins/markets',
            json=[
                {'id': 'bitcoin', 'current_price': 70000, 'market_cap': 1.3e12, 'total_volume': 4e10},
                {'id': 'ethereum', 'current_price': 2000, 'market_cap': 2.5e11, 'total_volume': 1.8e10},
            ],
            status=200,
        )
        result = client.get_coin_markets(['bitcoin', 'ethereum'])
        assert len(result) == 2
        assert result[0]['id'] == 'bitcoin'


class TestGetMarketChart:

    @responses.activate
    def test_returns_historical_data(self, client):
        responses.add(
            responses.GET, f'{BASE}/coins/bitcoin/market_chart',
            json={
                'prices': [[1700000000000, 70000], [1700086400000, 71000]],
                'market_caps': [[1700000000000, 1.3e12], [1700086400000, 1.35e12]],
                'total_volumes': [[1700000000000, 4e10], [1700086400000, 4.1e10]],
            },
            status=200,
        )
        result = client.get_market_chart('bitcoin', days=90)
        assert len(result['prices']) == 2


class TestErrorHandling:

    @responses.activate
    def test_handles_429_rate_limit(self, client):
        responses.add(
            responses.GET, f'{BASE}/simple/price',
            json={'error': 'rate limit'}, status=429,
        )
        with pytest.raises(CoinGeckoClientError, match='Rate limit'):
            client.get_prices(['bitcoin'])

    @responses.activate
    def test_handles_server_error(self, client):
        responses.add(
            responses.GET, f'{BASE}/simple/price',
            json={'error': 'internal'}, status=500,
        )
        with pytest.raises(CoinGeckoClientError, match='API error 500'):
            client.get_prices(['bitcoin'])

    @responses.activate
    def test_handles_network_error(self, client):
        import requests as req
        responses.add(
            responses.GET, f'{BASE}/simple/price',
            body=req.ConnectionError('connection refused'),
        )
        with pytest.raises(CoinGeckoClientError, match='Network error'):
            client.get_prices(['bitcoin'])


class TestRateLimiter:

    def test_allows_calls_within_limit(self):
        limiter = RateLimiter(max_calls=5, period=1)
        for _ in range(5):
            limiter.acquire()
