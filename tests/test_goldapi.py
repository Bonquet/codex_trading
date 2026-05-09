import unittest
from urllib.parse import parse_qs, urlparse

from xauusd_scalp_master.goldapi import GoldApiClient, GoldApiNetClient, GoldQuote, StooqQuoteClient


class GoldApiTests(unittest.TestCase):
    def test_quote_from_mapping(self):
        quote = GoldQuote.from_mapping(
            {
                "timestamp": 1685846292,
                "metal": "XAU",
                "currency": "USD",
                "price": 1948.01,
                "bid": 1947.56,
                "ask": 1948.47,
                "ch": -29.61,
                "chp": -1.5,
            }
        )
        self.assertEqual(quote.price, 1948.01)
        self.assertEqual(quote.bid, 1947.56)
        self.assertEqual(quote.timestamp.year, 2023)

    def test_client_uses_goldapi_endpoint_and_token_header(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["headers"] = {key.lower(): value for key, value in request.header_items()}
            return b'{"timestamp":1685846292,"metal":"XAU","currency":"USD","price":1948.01}'

        quote = GoldApiClient(api_key="test-key", opener=opener).latest_quote(timeout=3)

        self.assertEqual(quote.price, 1948.01)
        self.assertEqual(seen["url"], "https://www.goldapi.io/api/XAU/USD")
        self.assertEqual(seen["timeout"], 3)
        self.assertEqual(seen["headers"]["x-access-token"], "test-key")

    def test_goldapi_net_client_uses_header_key_endpoint(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["headers"] = {key.lower(): value for key, value in request.header_items()}
            return b'{"symbol":"XAUUSD","metal":"gold","currency":"USD","price":1948.01,"high":1950.0,"low":1940.0}'

        quote = GoldApiNetClient(api_key="net-key", opener=opener).latest_quote(timeout=5)
        parsed = urlparse(seen["url"])

        self.assertEqual(quote.price, 1948.01)
        self.assertEqual(quote.metal, "XAU")
        self.assertEqual(quote.high_price, 1950.0)
        self.assertEqual(quote.low_price, 1940.0)
        self.assertEqual(quote.exchange, "GoldAPI.net")
        self.assertEqual(parsed.netloc, "app.goldapi.net")
        self.assertEqual(parsed.path, "/api/price/XAU/USD")
        self.assertEqual(seen["headers"]["x-api-key"], "net-key")
        self.assertEqual(seen["timeout"], 5)

    def test_stooq_client_parses_spot_quote(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            return (
                b"Symbol,Date,Time,Open,High,Low,Close,Volume\r\n"
                b"XAUUSD,2026-05-07,18:21:16,4693.85,4764.72,4685.46,4713.09,\r\n"
            )

        quote = StooqQuoteClient(opener=opener).latest_quote(timeout=2)
        parsed = urlparse(seen["url"])
        query = parse_qs(parsed.query)

        self.assertEqual(quote.price, 4713.09)
        self.assertEqual(quote.symbol, "XAUUSD")
        self.assertEqual(quote.exchange, "Stooq")
        self.assertEqual(parsed.netloc, "stooq.com")
        self.assertEqual(query["s"], ["xauusd"])
        self.assertEqual(seen["timeout"], 2)


if __name__ == "__main__":
    unittest.main()
