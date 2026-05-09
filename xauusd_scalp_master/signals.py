from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .engine import Decision, MarketSnapshot, analyze_setup, format_decision, load_memory
from .goldapi import GoldApiClient, GoldApiError, GoldApiNetClient, GoldQuote, StooqQuoteClient, format_quote


@dataclass(frozen=True)
class SignalRequest:
    memory_path: str | Path = "data/memory_state.json"
    snapshot_path: str | Path | None = None
    snapshot_overrides: dict[str, Any] = field(default_factory=dict)
    pip_size: float = 0.10
    metal: str = "XAU"
    currency: str = "USD"
    quote_timeout: float = 10.0
    quote_source: str = "auto"
    news_clear_30m: bool = False
    news_clear_2h: bool = False


@dataclass(frozen=True)
class SignalResult:
    quote: GoldQuote
    decision: Decision
    output: str
    alert: str = ""


def run_signal(request: SignalRequest, quote_client: GoldApiClient | None = None) -> SignalResult:
    snapshot_payload = load_snapshot_payload(request.snapshot_path)
    quote, quote_notes = resolve_quote(request, snapshot_payload, quote_client)
    memory = load_memory(request.memory_path)
    snapshot = snapshot_from_quote(quote, request, snapshot_payload=snapshot_payload)
    decision = analyze_setup(memory, snapshot, pip_size=request.pip_size)
    output_lines = [format_quote(quote), *quote_notes, format_decision(decision)]
    output = "\n".join(output_lines)
    return SignalResult(quote=quote, decision=decision, output=output, alert=format_signal_alert(quote, decision))


def resolve_quote(
    request: SignalRequest,
    snapshot_payload: dict[str, Any],
    quote_client: GoldApiClient | None = None,
) -> tuple[GoldQuote, list[str]]:
    if quote_client is not None:
        return quote_client.latest_quote(request.metal, request.currency, timeout=request.quote_timeout), []

    source = request.quote_source.strip().lower()
    if source in {"goldapi-net", "goldapinet"}:
        return GoldApiNetClient().latest_quote(request.metal, request.currency, timeout=request.quote_timeout), []
    if source in {"goldapi", "goldapi-io", "goldapiio"}:
        return GoldApiClient().latest_quote(request.metal, request.currency, timeout=request.quote_timeout), []
    if source == "stooq":
        return latest_stooq_quote(request), []
    if source == "snapshot":
        return quote_from_snapshot_payload(snapshot_payload, request), []
    if source != "auto":
        raise GoldApiError("Unsupported quote source. Use auto, goldapi, stooq, or snapshot.")

    errors: list[str] = []
    if os.getenv("GOLDAPI_NET_KEY"):
        try:
            return GoldApiNetClient().latest_quote(request.metal, request.currency, timeout=request.quote_timeout), []
        except GoldApiError as exc:
            errors.append(f"GoldAPI.net unavailable: {exc}")

    try:
        return GoldApiClient().latest_quote(request.metal, request.currency, timeout=request.quote_timeout), []
    except GoldApiError as exc:
        errors.append(f"GoldAPI.io unavailable: {exc}")

    try:
        quote = latest_stooq_quote(request)
        return quote, ["QUOTE FALLBACK: primary GoldAPI source failed, using Stooq spot quote."]
    except GoldApiError as exc:
        errors.append(f"Stooq unavailable: {exc}")

    if snapshot_payload.get("price") is not None:
        quote = quote_from_snapshot_payload(snapshot_payload, request)
        return quote, ["QUOTE FALLBACK: GoldAPI/Stooq failed, using snapshot price."]

    raise GoldApiError("; ".join(errors))


def latest_stooq_quote(request: SignalRequest) -> GoldQuote:
    last_error: GoldApiError | None = None
    for attempt in range(2):
        timeout = request.quote_timeout if attempt == 0 else max(request.quote_timeout, 20.0)
        try:
            return StooqQuoteClient().latest_quote(request.metal, request.currency, timeout=timeout)
        except GoldApiError as exc:
            last_error = exc
    raise last_error or GoldApiError("Stooq quote unavailable.")


def quote_from_snapshot_payload(payload: dict[str, Any], request: SignalRequest) -> GoldQuote:
    if payload.get("price") is None:
        raise GoldApiError("Snapshot quote source requires a price field.")
    return GoldQuote.from_mapping(
        {
            "timestamp": payload.get("timestamp"),
            "metal": request.metal,
            "currency": request.currency,
            "price": payload["price"],
            "bid": payload.get("bid"),
            "ask": payload.get("ask"),
            "exchange": "snapshot",
            "symbol": f"{request.metal.upper()}{request.currency.upper()}",
        }
    )


def snapshot_from_quote(
    quote: GoldQuote,
    request: SignalRequest,
    snapshot_payload: dict[str, Any] | None = None,
) -> MarketSnapshot:
    payload = dict(snapshot_payload if snapshot_payload is not None else load_snapshot_payload(request.snapshot_path))
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


def format_signal_alert(quote: GoldQuote, decision: Decision) -> str:
    pair = f"{quote.metal.upper()}{quote.currency.upper()}"
    if decision.plan:
        plan = decision.plan
        return (
            f"{pair} SELL {plan.entry:.2f} | SL {plan.stop_loss:.2f} | "
            f"TP1 {plan.tp1:.2f} | TP2 {plan.tp2:.2f} | {decision.market_state} | "
            f"Risk {plan.risk_percent:.2f}%"
        )

    blockers = "; ".join(decision.blockers[:3])
    if len(decision.blockers) > 3:
        blockers += f"; +{len(decision.blockers) - 3} more"
    suffix = f" | {blockers}" if blockers else ""
    return f"{pair} {decision.action} {quote.price:.2f} | {decision.market_state}{suffix}"


def load_snapshot_payload(snapshot_path: str | Path | None) -> dict[str, Any]:
    if not snapshot_path:
        snapshot_json = os.getenv("SIGNAL_SNAPSHOT_JSON", "").strip()
        if snapshot_json:
            return json.loads(snapshot_json)
        return {}
    if not Path(snapshot_path).exists():
        snapshot_json = os.getenv("SIGNAL_SNAPSHOT_JSON", "").strip()
        if snapshot_json:
            return json.loads(snapshot_json)
        return {}
    with Path(snapshot_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
