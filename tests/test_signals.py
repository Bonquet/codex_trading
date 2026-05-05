import os
import unittest

from xauusd_scalp_master.goldapi import GoldQuote
from xauusd_scalp_master.signals import SignalRequest, snapshot_from_quote


class SignalTests(unittest.TestCase):
    def test_snapshot_can_load_from_env_json(self):
        original = os.environ.get("SIGNAL_SNAPSHOT_JSON")
        os.environ["SIGNAL_SNAPSHOT_JSON"] = '{"htf_below_200ema": true, "atr_pips": 9}'
        try:
            quote = GoldQuote.from_mapping({"timestamp": 1685846292, "price": 1948.01})
            snapshot = snapshot_from_quote(quote, SignalRequest(news_clear_30m=True, news_clear_2h=True))
            self.assertTrue(snapshot.htf_below_200ema)
            self.assertEqual(snapshot.atr_pips, 9)
            self.assertEqual(snapshot.price, 1948.01)
            self.assertTrue(snapshot.news_checked_30m)
            self.assertTrue(snapshot.news_checked_2h)
        finally:
            if original is None:
                os.environ.pop("SIGNAL_SNAPSHOT_JSON", None)
            else:
                os.environ["SIGNAL_SNAPSHOT_JSON"] = original


if __name__ == "__main__":
    unittest.main()
