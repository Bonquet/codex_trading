import unittest
from datetime import datetime

from xauusd_scalp_master.engine import (
    MarketSnapshot,
    TradeRecord,
    analyze_setup,
    calculate_win_rate_24h,
    in_london_ny_overlap,
    record_trade,
    to_eastern,
)


class EngineTests(unittest.TestCase):
    def prime_snapshot(self):
        return MarketSnapshot(
            timestamp=datetime.fromisoformat("2026-05-05T09:17:00-04:00"),
            price=2652.10,
            htf_below_200ema=True,
            htf_lower_high=True,
            bearish_structure=True,
            ema50_rejection=True,
            ema50_slope_negative=True,
            rsi=58,
            rsi_previous=62,
            macd_bearish_cross=True,
            volume_spike_rejection=True,
            atr_pips=11,
            bearish_engulfing_resistance=True,
            shooting_star_rejection=True,
            dxy_strengthening=True,
            cot_commercial_shorts_increasing=True,
            swing_high=2652.20,
        )

    def test_prime_setup_produces_short_plan(self):
        decision = analyze_setup({}, self.prime_snapshot())
        self.assertTrue(decision.should_trade)
        self.assertEqual(decision.market_state, "PRIME")
        self.assertTrue(decision.memory_check.startswith("MEMORY CHECK:"))
        self.assertIsNotNone(decision.plan)
        self.assertEqual(decision.plan.entry, 2652.10)
        self.assertEqual(decision.plan.stop_loss, 2653.00)
        self.assertEqual(decision.plan.tp1, 2651.10)

    def test_three_losses_blocks_trading(self):
        memory = {"consecutive_losses": 3}
        decision = analyze_setup(memory, self.prime_snapshot())
        self.assertFalse(decision.should_trade)
        self.assertEqual(decision.market_state, "NO_TRADE")
        self.assertIn("3 consecutive losses", " ".join(decision.blockers))

    def test_atr_filter_blocks_chop(self):
        snapshot = self.prime_snapshot()
        snapshot = MarketSnapshot(**{**snapshot.__dict__, "atr_pips": 5})
        decision = analyze_setup({}, snapshot)
        self.assertFalse(decision.should_trade)
        self.assertEqual(decision.market_state, "NO_TRADE")

    def test_unverified_news_blocks_prime(self):
        snapshot = self.prime_snapshot()
        snapshot = MarketSnapshot(**{**snapshot.__dict__, "news_checked_30m": False})
        decision = analyze_setup({}, snapshot)
        self.assertFalse(decision.should_trade)
        self.assertEqual(decision.market_state, "CAUTION")
        self.assertIn("News calendar not verified", " ".join(decision.blockers))

    def test_record_trade_updates_memory(self):
        trade = TradeRecord(
            timestamp=datetime.fromisoformat("2026-05-05T09:30:00-04:00"),
            entry=2652.10,
            exit=2650.40,
            pips=17,
            success=True,
            reason="RSI rejection",
            state="PRIME",
            pnl_percent=0.4,
        )
        memory = record_trade({}, trade)
        self.assertEqual(memory["last_trade_result"], "SUCCESS")
        self.assertEqual(memory["success_streak"], 1)
        self.assertEqual(memory["consecutive_losses"], 0)
        self.assertEqual(memory["win_rate_24h"], 100.0)

    def test_loss_adds_avoidance_pattern(self):
        trade = TradeRecord(
            timestamp=datetime.fromisoformat("2026-05-05T09:45:00-04:00"),
            entry=2652.10,
            exit=2653.00,
            pips=-9,
            success=False,
            reason="news spike reversal",
            state="PRIME",
            pnl_percent=-0.3,
        )
        memory = record_trade({}, trade)
        self.assertEqual(memory["last_trade_result"], "FAILURE")
        self.assertEqual(memory["consecutive_losses"], 1)
        self.assertTrue(any(pattern.startswith("news_spike") for pattern in memory["avoidance_patterns"]))

    def test_win_rate_24h(self):
        now = datetime.fromisoformat("2026-05-05T10:00:00-04:00")
        trades = [
            {"timestamp": "2026-05-05T09:00:00-04:00", "success": True},
            {"timestamp": "2026-05-05T09:30:00-04:00", "success": False},
            {"timestamp": "2026-05-03T09:30:00-04:00", "success": True},
        ]
        self.assertEqual(calculate_win_rate_24h(trades, now), 50.0)

    def test_eastern_session_uses_daylight_saving_time(self):
        early_overlap = datetime.fromisoformat("2026-05-07T12:30:00+00:00")
        after_overlap = datetime.fromisoformat("2026-05-07T16:27:00+00:00")

        self.assertEqual(to_eastern(early_overlap).hour, 8)
        self.assertTrue(in_london_ny_overlap(early_overlap))
        self.assertFalse(in_london_ny_overlap(after_overlap))


if __name__ == "__main__":
    unittest.main()
