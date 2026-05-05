from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


GOLDAPI_BASE_URL = "https://www.goldapi.io/api"


class GoldApiError(RuntimeError):
    """Raised when GoldAPI cannot return a usable quote."""


@dataclass(frozen=True)
class GoldQuote:
    metal: str
    currency: str
    price: float
    timestamp: datetime
    bid: float | None = None
    ask: float | None = None
    change: float | None = None
    change_percent: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    previous_close_price: float | None = None
    exchange: str = ""
    symbol: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "GoldQuote":
        price = payload.get("price")
        if price is None:
            raise GoldApiError("GoldAPI response did not include a price.")
        timestamp = parse_api_timestamp(payload.get("timestamp"))
        return cls(
            metal=str(payload.get("metal", "XAU")),
            currency=str(payload.get("currency", "USD")),
            price=float(price),
            timestamp=timestamp,
            bid=optional_float(payload.get("bid")),
            ask=optional_float(payload.get("ask")),
            change=optional_float(payload.get("ch")),
            change_percent=optional_float(payload.get("chp")),
            open_price=optional_float(payload.get("open_price")),
            high_price=optional_float(payload.get("high_price")),
            low_price=optional_float(payload.get("low_price")),
            previous_close_price=optional_float(payload.get("prev_close_price")),
            exchange=str(payload.get("exchange", "")),
            symbol=str(payload.get("symbol", "")),
        )


class GoldApiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = GOLDAPI_BASE_URL,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GOLDAPI_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.opener = opener or self._default_open

    def latest_quote(self, metal: str = "XAU", currency: str = "USD", timeout: float = 10.0) -> GoldQuote:
        if not self.api_key:
            raise GoldApiError("Set GOLDAPI_KEY before requesting a live quote.")
        url = f"{self.base_url}/{metal.upper()}/{currency.upper()}"
        request = urllib.request.Request(
            url,
            headers={
                "x-access-token": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "xauusd-scalp-master/1.0",
            },
            method="GET",
        )
        try:
            raw = self.opener(request, timeout)
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise GoldApiError(f"GoldAPI HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise GoldApiError(f"GoldAPI network error: {exc.reason}") from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GoldApiError("GoldAPI returned invalid JSON.") from exc
        return GoldQuote.from_mapping(payload)

    @staticmethod
    def _default_open(request: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()


def parse_api_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        clean = value.strip()
        if clean.isdigit():
            return datetime.fromtimestamp(int(clean), tz=timezone.utc)
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        parsed = datetime.fromisoformat(clean)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise GoldApiError(f"Unsupported GoldAPI timestamp: {value!r}")


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def format_quote(quote: GoldQuote) -> str:
    parts = [
        f"LIVE QUOTE: {quote.metal}/{quote.currency} {quote.price:.2f}",
        f"time={quote.timestamp.isoformat()}",
    ]
    if quote.bid is not None and quote.ask is not None:
        parts.append(f"bid={quote.bid:.2f} ask={quote.ask:.2f}")
    if quote.change is not None and quote.change_percent is not None:
        parts.append(f"change={quote.change:+.2f} ({quote.change_percent:+.2f}%)")
    return " | ".join(parts)
