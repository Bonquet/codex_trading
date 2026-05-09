from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta, tzinfo
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]


EASTERN_TZ_NAME = "America/New_York"


def _eastern_tz():
    if ZoneInfo is None:
        return EasternFallbackTz()
    try:
        return ZoneInfo(EASTERN_TZ_NAME)
    except Exception:
        return EasternFallbackTz()


class EasternFallbackTz(tzinfo):
    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(hours=-5) + self.dst(dt)

    def dst(self, dt: datetime | None) -> timedelta:
        if dt is None:
            return timedelta(0)
        local = dt.replace(tzinfo=None)
        start = self._dst_start(local.year)
        end = self._dst_end(local.year)
        return timedelta(hours=1) if start <= local < end else timedelta(0)

    def tzname(self, dt: datetime | None) -> str:
        return "EDT" if self.dst(dt) else "EST"

    def fromutc(self, dt: datetime) -> datetime:
        if dt.tzinfo is not self:
            raise ValueError("fromutc: dt.tzinfo is not self")
        utc_naive = dt.replace(tzinfo=None)
        standard = utc_naive + timedelta(hours=-5)
        daylight = standard + timedelta(hours=1)
        if self._dst_start(daylight.year) <= daylight < self._dst_end(daylight.year):
            return daylight.replace(tzinfo=self)
        return standard.replace(tzinfo=self)

    @staticmethod
    def _dst_start(year: int) -> datetime:
        return EasternFallbackTz._nth_weekday(year, 3, 6, 2).replace(hour=2)

    @staticmethod
    def _dst_end(year: int) -> datetime:
        return EasternFallbackTz._nth_weekday(year, 11, 6, 1).replace(hour=2)

    @staticmethod
    def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> datetime:
        first = datetime(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + (occurrence - 1) * 7)


EASTERN = _eastern_tz()


DEFAULT_MEMORY: dict[str, Any] = {
    "last_10_trades": [],
    "win_rate_24h": 0.0,
    "consecutive_losses": 0,
    "success_streak": 0,
    "daily_pnl": 0.0,
    "market_bias": "unknown",
    "optimal_session_today": False,
    "avoidance_patterns": [],
    "trade_count_today": 0,
    "session_date": "",
    "last_trade_result": "NONE",
    "updated_at": "",
}


FAILURE_COUNTERMEASURES = {
    "FAKEOUT": "Wait for the candle close and require rejection-volume confirmation.",
    "NEWS_SPIKE": "Block entries when high-impact news is within 30 minutes.",
    "OVEREXTENSION": "Skip shorts after an exhausted move, especially RSI below 30.",
    "CHOPS": "Treat ATR below 8 pips as no-trade chop.",
    "MANUAL_REVIEW": "Journal the setup and add a concrete avoidance pattern if it repeats.",
}


@dataclass(frozen=True)
class RiskProfile:
    risk_percent: float
    sl_pips: float
    tp1_pips: float
    tp2_pips: float
    max_trades_per_hour: int


STATE_PROFILES: dict[str, RiskProfile] = {
    "PRIME": RiskProfile(risk_percent=1.0, sl_pips=8, tp1_pips=10, tp2_pips=18, max_trades_per_hour=8),
    "CAUTION": RiskProfile(risk_percent=0.5, sl_pips=10, tp1_pips=12, tp2_pips=18, max_trades_per_hour=4),
    "RECOVERY": RiskProfile(risk_percent=0.3, sl_pips=12, tp1_pips=15, tp2_pips=24, max_trades_per_hour=3),
    "HYPER": RiskProfile(risk_percent=1.5, sl_pips=6, tp1_pips=8, tp2_pips=14, max_trades_per_hour=12),
    "NO_TRADE": RiskProfile(risk_percent=0.0, sl_pips=0, tp1_pips=0, tp2_pips=0, max_trades_per_hour=0),
}


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    price: float
    htf_below_200ema: bool = False
    htf_lower_high: bool = False
    bearish_structure: bool = False
    ema50_rejection: bool = False
    ema50_slope_negative: bool = False
    price_crossed_below_ema50: bool = False
    rsi: float | None = None
    rsi_previous: float | None = None
    macd_bearish_cross: bool = False
    macd_histogram_shrinking: bool = False
    volume_spike_rejection: bool = False
    atr_pips: float = 0.0
    bearish_engulfing_resistance: bool = False
    shooting_star_rejection: bool = False
    orderblock_rejection: bool = False
    dxy_strengthening: bool = False
    cot_commercial_shorts_increasing: bool = False
    news_within_30m: bool = False
    news_within_2h: bool = False
    news_checked_30m: bool = True
    news_checked_2h: bool = True
    resistance_price: float | None = None
    swing_high: float | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "MarketSnapshot":
        data = dict(payload)
        data["timestamp"] = parse_timestamp(data.get("timestamp"))
        return cls(**data)


@dataclass(frozen=True)
class TradeRecord:
    timestamp: datetime
    entry: float
    exit: float
    pips: float
    success: bool
    reason: str = ""
    state: str = ""
    pnl_percent: float = 0.0
    failure_mode: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "entry": round(self.entry, 2),
            "exit": round(self.exit, 2),
            "pips": round(self.pips, 1),
            "success": self.success,
            "reason": self.reason,
            "state": self.state,
            "pnl_percent": round(self.pnl_percent, 4),
            "failure_mode": self.failure_mode,
        }


@dataclass(frozen=True)
class TradePlan:
    side: str
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    risk_percent: float
    profile: RiskProfile


@dataclass(frozen=True)
class Decision:
    memory_check: str
    market_state: str
    should_trade: bool
    action: str
    checklist: dict[str, bool]
    confirmations: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    plan: TradePlan | None = None


def parse_timestamp(value: str | datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=EASTERN)
    clean = value.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    parsed = datetime.fromisoformat(clean)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=EASTERN)
    return parsed


def to_eastern(value: datetime) -> datetime:
    return value.astimezone(EASTERN) if value.tzinfo else value.replace(tzinfo=EASTERN)


def load_memory(path: str | Path = "data/memory_state.json") -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return copy.deepcopy(DEFAULT_MEMORY)
    with memory_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return normalize_memory(loaded)


def save_memory(memory: dict[str, Any], path: str | Path = "data/memory_state.json") -> None:
    memory_path = Path(path)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_memory(memory)
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
    with memory_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, sort_keys=True)
        handle.write("\n")


def normalize_memory(memory: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(DEFAULT_MEMORY)
    normalized.update(memory or {})
    normalized["last_10_trades"] = list(normalized.get("last_10_trades", []))[-10:]
    normalized["avoidance_patterns"] = list(dict.fromkeys(normalized.get("avoidance_patterns", [])))[:25]
    normalized["win_rate_24h"] = float(normalized.get("win_rate_24h", 0.0) or 0.0)
    normalized["consecutive_losses"] = int(normalized.get("consecutive_losses", 0) or 0)
    normalized["success_streak"] = int(normalized.get("success_streak", 0) or 0)
    normalized["daily_pnl"] = float(normalized.get("daily_pnl", 0.0) or 0.0)
    normalized["trade_count_today"] = int(normalized.get("trade_count_today", 0) or 0)
    if normalized["last_10_trades"]:
        normalized["last_trade_result"] = "SUCCESS" if normalized["last_10_trades"][-1].get("success") else "FAILURE"
    return normalized


def memory_check_line(memory: dict[str, Any]) -> str:
    normalized = normalize_memory(memory)
    last = normalized.get("last_trade_result", "NONE")
    win_rate = normalized.get("win_rate_24h", 0.0)
    bias = normalized.get("market_bias", "unknown")
    return f"MEMORY CHECK: Last trade {last}. Win rate: {win_rate:.1f}%. Bias: {bias}"


def analyze_setup(memory: dict[str, Any], snapshot: MarketSnapshot, pip_size: float = 0.10) -> Decision:
    normalized = normalize_memory(memory)
    checklist = build_checklist(normalized, snapshot)
    confirmations = collect_confirmations(snapshot)
    blockers = [label for label, passed in checklist.items() if not passed]
    warnings: list[str] = []
    state, state_reasons = classify_market_state(normalized, snapshot)
    blockers.extend(state_reasons)

    profile = STATE_PROFILES[state]
    hour_count = trades_this_hour(normalized, snapshot.timestamp)
    if profile.max_trades_per_hour and hour_count >= profile.max_trades_per_hour:
        blockers.append(f"Max trades/hour reached for {state} ({profile.max_trades_per_hour})")

    if to_eastern(snapshot.timestamp).weekday() == 4 and to_eastern(snapshot.timestamp).time() >= time(14, 0):
        warnings.append("Friday after 2PM Eastern: reduce risk by 50%.")
        profile = RiskProfile(
            risk_percent=profile.risk_percent * 0.5,
            sl_pips=profile.sl_pips,
            tp1_pips=profile.tp1_pips,
            tp2_pips=profile.tp2_pips,
            max_trades_per_hour=profile.max_trades_per_hour,
        )

    entry_ready = all(checklist.values())
    should_trade = state in {"PRIME", "HYPER", "RECOVERY"} and entry_ready and not blockers
    action = "SELL" if should_trade else ("NO TRADE" if state == "NO_TRADE" else "WAIT")
    plan = build_trade_plan(snapshot, profile, pip_size) if should_trade else None

    return Decision(
        memory_check=memory_check_line(normalized),
        market_state=state,
        should_trade=should_trade,
        action=action,
        checklist=checklist,
        confirmations=confirmations,
        blockers=list(dict.fromkeys(blockers)),
        warnings=warnings,
        plan=plan,
    )


def classify_market_state(memory: dict[str, Any], snapshot: MarketSnapshot) -> tuple[str, list[str]]:
    blockers: list[str] = []
    daily_pnl = float(memory.get("daily_pnl", 0.0) or 0.0)
    losses = int(memory.get("consecutive_losses", 0) or 0)
    trade_count_today = int(memory.get("trade_count_today", 0) or 0)

    if losses >= 3:
        blockers.append("3 consecutive losses: 1 hour break and journal review required")
    if daily_pnl <= -3.0:
        blockers.append("Daily drawdown limit hit (-3%)")
    if daily_pnl >= 4.0:
        blockers.append("Daily profit target reached (+4%)")
    if trade_count_today >= 40:
        blockers.append("Daily trade limit reached (40)")
    if snapshot.atr_pips < 8:
        blockers.append("Choppy volatility filter: ATR below 8 pips")
    if blockers:
        return "NO_TRADE", blockers

    if losses >= 2:
        return "RECOVERY", []

    if snapshot.news_within_30m:
        return "CAUTION", ["High-impact news within 30 minutes"]
    if not snapshot.news_checked_30m:
        return "CAUTION", ["News calendar not verified for 30 minutes"]
    if not snapshot.news_checked_2h:
        return "CAUTION", ["High-impact news calendar not verified for 2 hours"]

    prime = (
        htf_bias_ok(snapshot)
        and snapshot.ema50_rejection
        and rsi_rejection_ok(snapshot)
        and pattern_count(snapshot) >= 2
        and indicators_ok(snapshot)
        and no_news_ok(snapshot)
    )
    hyper = (
        prime
        and int(memory.get("success_streak", 0) or 0) >= 5
        and strong_bearish_momentum(snapshot)
    )
    if hyper:
        return "HYPER", []
    if prime:
        return "PRIME", []
    return "CAUTION", ["Mixed or incomplete confirmations"]


def build_checklist(memory: dict[str, Any], snapshot: MarketSnapshot) -> dict[str, bool]:
    return {
        "Time: 8AM-12PM Eastern": in_london_ny_overlap(snapshot.timestamp),
        "HTF: Below 200EMA": snapshot.htf_below_200ema,
        "HTF: Lower high formed": snapshot.htf_lower_high,
        "HTF: Bearish structure intact": snapshot.bearish_structure,
        "1min: 50EMA rejection": snapshot.ema50_rejection,
        "1min: RSI dropping below 60": rsi_rejection_ok(snapshot),
        "Pattern: 2+ bearish rejection signals": pattern_count(snapshot) >= 2,
        "MACD: Bearish or histogram shrinking": snapshot.macd_bearish_cross or snapshot.macd_histogram_shrinking,
        "Volume: Spike on rejection candle": snapshot.volume_spike_rejection,
        "ATR: >8 pips": snapshot.atr_pips > 8,
        "Sentiment: DXY strengthening": snapshot.dxy_strengthening,
        "Sentiment: Commercial shorts increasing": snapshot.cot_commercial_shorts_increasing,
        "News: Clear 30min": snapshot.news_checked_30m and not snapshot.news_within_30m,
        "News: Clear 2h": snapshot.news_checked_2h and not snapshot.news_within_2h,
        "Memory: Win rate >65% or recovery/new sample": memory_gate_ok(memory),
    }


def collect_confirmations(snapshot: MarketSnapshot) -> list[str]:
    confirmations: list[str] = []
    if htf_bias_ok(snapshot):
        confirmations.append("HTF downtrend: below 200EMA, lower high, bearish structure")
    if snapshot.ema50_rejection:
        confirmations.append("1min 50EMA rejection")
    if rsi_rejection_ok(snapshot):
        confirmations.append("RSI rejection: 55-70 zone dropping below 60")
    if snapshot.macd_bearish_cross:
        confirmations.append("MACD bearish crossover")
    elif snapshot.macd_histogram_shrinking:
        confirmations.append("MACD histogram shrinking")
    if snapshot.volume_spike_rejection:
        confirmations.append("Volume spike on rejection candle")
    for pattern_name in pattern_names(snapshot):
        confirmations.append(pattern_name)
    if snapshot.dxy_strengthening:
        confirmations.append("DXY strengthening")
    if snapshot.cot_commercial_shorts_increasing:
        confirmations.append("Commercial shorts increasing")
    return confirmations


def htf_bias_ok(snapshot: MarketSnapshot) -> bool:
    return snapshot.htf_below_200ema and snapshot.htf_lower_high and snapshot.bearish_structure


def rsi_rejection_ok(snapshot: MarketSnapshot) -> bool:
    if snapshot.rsi is None or snapshot.rsi_previous is None:
        return False
    return 55 <= snapshot.rsi_previous <= 70 and snapshot.rsi < 60 and snapshot.rsi < snapshot.rsi_previous


def indicators_ok(snapshot: MarketSnapshot) -> bool:
    macd_ok = snapshot.macd_bearish_cross or snapshot.macd_histogram_shrinking
    return rsi_rejection_ok(snapshot) and macd_ok and snapshot.volume_spike_rejection and snapshot.atr_pips > 8


def no_news_ok(snapshot: MarketSnapshot) -> bool:
    return (
        snapshot.news_checked_30m
        and snapshot.news_checked_2h
        and not snapshot.news_within_30m
        and not snapshot.news_within_2h
    )


def pattern_names(snapshot: MarketSnapshot) -> list[str]:
    names: list[str] = []
    if snapshot.bearish_engulfing_resistance:
        names.append("Bearish engulfing at resistance")
    if snapshot.shooting_star_rejection:
        names.append("Shooting star/doji rejection")
    if snapshot.ema50_slope_negative or snapshot.price_crossed_below_ema50:
        names.append("50EMA slope negative / cross below")
    if snapshot.orderblock_rejection:
        names.append("Orderblock rejection")
    return names


def pattern_count(snapshot: MarketSnapshot) -> int:
    return len(pattern_names(snapshot))


def strong_bearish_momentum(snapshot: MarketSnapshot) -> bool:
    rsi_drop = snapshot.rsi is not None and snapshot.rsi <= 50
    fast_drop = (
        snapshot.rsi is not None
        and snapshot.rsi_previous is not None
        and snapshot.rsi_previous - snapshot.rsi >= 4
    )
    return snapshot.dxy_strengthening and (snapshot.macd_bearish_cross or fast_drop or rsi_drop)


def memory_gate_ok(memory: dict[str, Any]) -> bool:
    trades = memory.get("last_10_trades", [])
    if len(trades) < 5:
        return True
    if int(memory.get("consecutive_losses", 0) or 0) >= 2:
        return True
    return float(memory.get("win_rate_24h", 0.0) or 0.0) >= 65.0


def in_london_ny_overlap(timestamp: datetime) -> bool:
    local = to_eastern(timestamp)
    return local.weekday() < 5 and time(8, 0) <= local.time() <= time(12, 0)


def trades_this_hour(memory: dict[str, Any], timestamp: datetime) -> int:
    local = to_eastern(timestamp)
    count = 0
    for trade in memory.get("last_10_trades", []):
        try:
            trade_time = to_eastern(parse_timestamp(trade.get("timestamp")))
        except Exception:
            continue
        if trade_time.date() == local.date() and trade_time.hour == local.hour:
            count += 1
    return count


def build_trade_plan(snapshot: MarketSnapshot, profile: RiskProfile, pip_size: float) -> TradePlan:
    entry = snapshot.price
    if snapshot.swing_high is not None and snapshot.swing_high > entry:
        stop_loss = snapshot.swing_high + (profile.sl_pips * pip_size)
    else:
        stop_loss = entry + (profile.sl_pips * pip_size)
    tp1 = entry - (profile.tp1_pips * pip_size)
    tp2 = entry - (profile.tp2_pips * pip_size)
    return TradePlan(
        side="SELL",
        entry=round_price(entry, pip_size),
        stop_loss=round_price(stop_loss, pip_size),
        tp1=round_price(tp1, pip_size),
        tp2=round_price(tp2, pip_size),
        risk_percent=round(profile.risk_percent, 3),
        profile=profile,
    )


def round_price(value: float, pip_size: float) -> float:
    if pip_size <= 0:
        return round(value, 2)
    decimals = max(2, int(abs(math.floor(math.log10(pip_size)))) + 1)
    return round(value, decimals)


def record_trade(memory: dict[str, Any], trade: TradeRecord) -> dict[str, Any]:
    updated = normalize_memory(memory)
    trade_day = to_eastern(trade.timestamp).date().isoformat()
    if updated.get("session_date") != trade_day:
        updated["session_date"] = trade_day
        updated["trade_count_today"] = 0
        updated["daily_pnl"] = 0.0

    trade_json = trade.to_json()
    if not trade.success and not trade_json.get("failure_mode"):
        mode, _countermeasure = analyze_failure_reason(trade.reason)
        trade_json["failure_mode"] = mode

    updated["last_10_trades"] = (updated.get("last_10_trades", []) + [trade_json])[-10:]
    updated["trade_count_today"] = int(updated.get("trade_count_today", 0) or 0) + 1
    updated["daily_pnl"] = round(float(updated.get("daily_pnl", 0.0) or 0.0) + trade.pnl_percent, 4)

    if trade.success:
        updated["consecutive_losses"] = 0
        updated["success_streak"] = int(updated.get("success_streak", 0) or 0) + 1
        updated["last_trade_result"] = "SUCCESS"
    else:
        updated["consecutive_losses"] = int(updated.get("consecutive_losses", 0) or 0) + 1
        updated["success_streak"] = 0
        updated["last_trade_result"] = "FAILURE"
        failure_mode = trade_json.get("failure_mode", "MANUAL_REVIEW")
        pattern = derive_avoidance_pattern(failure_mode, trade.reason)
        if pattern and pattern not in updated["avoidance_patterns"]:
            updated["avoidance_patterns"].append(pattern)
            updated["avoidance_patterns"] = updated["avoidance_patterns"][-25:]

    updated["win_rate_24h"] = calculate_win_rate_24h(updated["last_10_trades"], trade.timestamp)
    updated["market_bias"] = infer_market_bias(updated)
    updated["optimal_session_today"] = 8 <= to_eastern(trade.timestamp).hour <= 12
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    return normalize_memory(updated)


def calculate_win_rate_24h(trades: list[dict[str, Any]], now: datetime) -> float:
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=24)
    recent: list[dict[str, Any]] = []
    for trade in trades:
        try:
            ts = parse_timestamp(trade.get("timestamp")).astimezone(timezone.utc)
        except Exception:
            continue
        if ts >= cutoff:
            recent.append(trade)
    if not recent:
        return 0.0
    wins = sum(1 for trade in recent if bool(trade.get("success")))
    return round((wins / len(recent)) * 100, 1)


def infer_market_bias(memory: dict[str, Any]) -> str:
    streak = int(memory.get("success_streak", 0) or 0)
    losses = int(memory.get("consecutive_losses", 0) or 0)
    win_rate = float(memory.get("win_rate_24h", 0.0) or 0.0)
    if streak >= 5 and win_rate >= 80:
        return "bearish_strong"
    if losses >= 2:
        return "bearish_unstable"
    if win_rate >= 65:
        return "bearish_watch"
    return "unknown"


def analyze_failure_reason(reason: str) -> tuple[str, str]:
    lower = (reason or "").lower()
    if "news" in lower or "fomc" in lower or "cpi" in lower or "nfp" in lower:
        mode = "NEWS_SPIKE"
    elif "fake" in lower or "breakout" in lower or "wick" in lower:
        mode = "FAKEOUT"
    elif "rsi" in lower or "overextension" in lower or "exhaust" in lower:
        mode = "OVEREXTENSION"
    elif "atr" in lower or "chop" in lower or "range" in lower:
        mode = "CHOPS"
    else:
        mode = "MANUAL_REVIEW"
    return mode, FAILURE_COUNTERMEASURES[mode]


def derive_avoidance_pattern(failure_mode: str, reason: str) -> str:
    suffix = re.sub(r"[^a-z0-9]+", "_", (reason or "").lower()).strip("_")[:40]
    if suffix:
        return f"{failure_mode.lower()}_{suffix}"
    return failure_mode.lower()


def format_decision(decision: Decision) -> str:
    lines = [
        decision.memory_check,
        f"MARKET STATE: {decision.market_state}",
        f"ACTION: {decision.action}",
        "CHECKLIST:",
    ]
    for label, passed in decision.checklist.items():
        marker = "x" if passed else " "
        lines.append(f"[{marker}] {label}")

    if decision.confirmations:
        lines.append("CONFIRMATIONS: " + "; ".join(decision.confirmations))
    if decision.blockers:
        lines.append("BLOCKERS: " + "; ".join(decision.blockers))
    if decision.warnings:
        lines.append("WARNINGS: " + "; ".join(decision.warnings))
    if decision.plan:
        plan = decision.plan
        lines.append(
            "ENTRY: "
            f"{plan.side} @ {plan.entry:.2f} | SL: {plan.stop_loss:.2f} | "
            f"TP1: {plan.tp1:.2f} | TP2: {plan.tp2:.2f} | Risk: {plan.risk_percent:.2f}%"
        )
    return "\n".join(lines)
