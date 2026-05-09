import os
import json
import tempfile
import unittest
from pathlib import Path

from xauusd_scalp_master.goldapi import GoldQuote
from xauusd_scalp_master.signals import SignalRequest, resolve_quote, run_signal, snapshot_from_quote


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

    def test_snapshot_quote_source_can_produce_short_alert(self):
        payload = {
            "timestamp": "2026-05-05T09:17:00-04:00",
            "price": 2652.10,
            "htf_below_200ema": True,
            "htf_lower_high": True,
            "bearish_structure": True,
            "ema50_rejection": True,
            "ema50_slope_negative": True,
            "rsi": 58,
            "rsi_previous": 62,
            "macd_bearish_cross": True,
            "volume_spike_rejection": True,
            "atr_pips": 11,
            "bearish_engulfing_resistance": True,
            "shooting_star_rejection": True,
            "dxy_strengthening": True,
            "cot_commercial_shorts_increasing": True,
            "swing_high": 2652.20,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.json"
            memory_path = Path(tmpdir) / "memory.json"
            snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

            result = run_signal(
                SignalRequest(
                    memory_path=memory_path,
                    snapshot_path=snapshot_path,
                    quote_source="snapshot",
                    news_clear_30m=True,
                    news_clear_2h=True,
                )
            )

        self.assertTrue(result.decision.should_trade)
        self.assertEqual(result.alert, "XAUUSD SELL 2652.10 | SL 2653.00 | TP1 2651.10 | TP2 2650.30 | PRIME | Risk 1.00%")

    def test_resolve_quote_uses_injected_client(self):
        class FakeClient:
            def latest_quote(self, metal, currency, timeout):
                self.args = (metal, currency, timeout)
                return GoldQuote.from_mapping(
                    {
                        "timestamp": 1685846292,
                        "metal": metal,
                        "currency": currency,
                        "price": 1948.01,
                        "exchange": "test",
                    }
                )

        client = FakeClient()
        quote, notes = resolve_quote(SignalRequest(quote_source="goldapi-net", quote_timeout=4), {}, client)

        self.assertEqual(quote.price, 1948.01)
        self.assertEqual(client.args, ("XAU", "USD", 4))
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
