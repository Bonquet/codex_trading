import unittest

from xauusd_scalp_master.goldapi import GoldApiClient, GoldQuote


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


if __name__ == "__main__":
    unittest.main()
