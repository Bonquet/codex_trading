from __future__ import annotations

import os
from pathlib import Path


CONFIG_KEYS = [
    "GOLDAPI_KEY",
    "GOLDAPI_NET_KEY",
    "QUOTE_SOURCE",
    "CALLMEBOT_WHATSAPP_PHONE",
    "CALLMEBOT_WHATSAPP_APIKEY",
    "CALLMEBOT_TELEGRAM_GROUP_APIKEY",
    "WEBHOOK_TOKEN",
    "NOTIFY_FORMAT",
    "SIGNAL_SNAPSHOT_JSON",
]


SERVER_REQUIRED_KEYS = [
    "GOLDAPI_KEY",
    "CALLMEBOT_WHATSAPP_PHONE",
    "CALLMEBOT_WHATSAPP_APIKEY",
    "WEBHOOK_TOKEN",
]


ACTION_REQUIRED_KEYS = [
    "CALLMEBOT_WHATSAPP_PHONE",
    "CALLMEBOT_WHATSAPP_APIKEY",
]


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def redacted_config_lines() -> list[str]:
    lines = ["CONFIG:"]
    for key in CONFIG_KEYS:
        value = os.getenv(key, "")
        status = redact(value) if value else "not set"
        lines.append(f"{key}: {status}")
    return lines


def missing_keys(keys: list[str]) -> list[str]:
    return [key for key in keys if not os.getenv(key)]


def missing_production_keys(mode: str) -> list[str]:
    keys = list(SERVER_REQUIRED_KEYS if mode == "server" else ACTION_REQUIRED_KEYS)
    for key in quote_required_keys():
        if key not in keys:
            keys.append(key)
    return missing_keys(keys)


def quote_required_keys() -> list[str]:
    source = os.getenv("QUOTE_SOURCE", "auto").strip().lower()
    if source in {"goldapi-net", "goldapinet"}:
        return ["GOLDAPI_NET_KEY"]
    if source in {"goldapi", "goldapi-io", "goldapiio"}:
        return ["GOLDAPI_KEY"]
    if source in {"stooq", "snapshot"}:
        return []
    if os.getenv("GOLDAPI_NET_KEY"):
        return ["GOLDAPI_NET_KEY"]
    if os.getenv("GOLDAPI_KEY"):
        return ["GOLDAPI_KEY"]
    return ["GOLDAPI_NET_KEY"]


def env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return float(value)


def env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return int(value)


def redact(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return f"{value[:2]}...{value[-2:]}"
    return f"{value[:4]}...{value[-4:]}"
