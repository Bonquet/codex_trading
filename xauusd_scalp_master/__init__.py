"""Broker-neutral XAUUSD short scalp signal discipline engine."""

from .callmebot import CallMeBotClient, CallMeBotError
from .config import load_env_file
from .engine import (
    DEFAULT_MEMORY,
    MarketSnapshot,
    TradeRecord,
    analyze_setup,
    format_decision,
    load_memory,
    record_trade,
    save_memory,
)
from .goldapi import GoldApiClient, GoldApiError, GoldQuote
from .signals import SignalRequest, SignalResult, run_signal

__all__ = [
    "CallMeBotClient",
    "CallMeBotError",
    "DEFAULT_MEMORY",
    "GoldApiClient",
    "GoldApiError",
    "GoldQuote",
    "SignalRequest",
    "SignalResult",
    "load_env_file",
    "MarketSnapshot",
    "TradeRecord",
    "analyze_setup",
    "format_decision",
    "load_memory",
    "record_trade",
    "run_signal",
    "save_memory",
]
