from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .engine import Decision, MarketSnapshot, analyze_setup, format_decision, load_memory
from .goldapi import GoldApiClient, GoldQuote, format_quote


@dataclass(frozen=True)
class SignalRequest:
    memory_path: str | Path = "data/memory_state.json"
    snapshot_path: str | Path | None = None
    snapshot_overrides: dict[str, Any] = field(default_factory=dict)
    pip_size: float = 0.10
    metal: str = "XAU"
    currency: str = "USD"
    quote_timeout: float = 10.0
    news_clear_30m: bool = False
    news_clear_2h: bool = False


@dataclass(frozen=True)
class SignalResult:
    quote: GoldQuote
    decision: Decision
    output: str


def run_signal(request: SignalRequest, quote_client: GoldApiClient | None = None) -> SignalResult:
    client = quote_client or GoldApiClient()
    quote = client.latest_quote(request.metal, request.currency, timeout=request.quote_timeout)
    memory = load_memory(request.memory_path)
    snapshot = snapshot_from_quote(quote, request)
    decision = analyze_setup(memory, snapshot, pip_size=request.pip_size)
    output = f"{format_quote(quote)}\n{format_decision(decision)}"
    return SignalResult(quote=quote, decision=decision, output=output)


def snapshot_from_quote(quote: GoldQuote, request: SignalRequest) -> MarketSnapshot:
    payload = load_snapshot_payload(request.snapshot_path)
    payload.update(request.snapshot_overrides)
    payload.update(
        {
            "timestamp": quote.timestamp,
            "price": quote.price,
            "news_checked_30m": request.news_clear_30m
            or bool(payload.get("news_checked_30m", False))
            or bool(payload.get("news_clear_30m", False))
            or bool(payload.get("news_within_30m", False)),
            "news_checked_2h": request.news_clear_2h
            or bool(payload.get("news_checked_2h", False))
            or bool(payload.get("news_clear_2h", False))
            or bool(payload.get("news_within_2h", False)),
        }
    )
    return MarketSnapshot.from_mapping(payload)


def load_snapshot_payload(snapshot_path: str | Path | None) -> dict[str, Any]:
    if not snapshot_path:
        return {}
    with Path(snapshot_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
