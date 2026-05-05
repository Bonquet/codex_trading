from __future__ import annotations

import os
from pathlib import Path


CONFIG_KEYS = [
    "GOLDAPI_KEY",
    "CALLMEBOT_WHATSAPP_PHONE",
    "CALLMEBOT_WHATSAPP_APIKEY",
    "CALLMEBOT_TELEGRAM_GROUP_APIKEY",
    "WEBHOOK_TOKEN",
    "SIGNAL_SNAPSHOT_JSON",
]


SERVER_REQUIRED_KEYS = [
    "GOLDAPI_KEY",
    "CALLMEBOT_WHATSAPP_PHONE",
    "CALLMEBOT_WHATSAPP_APIKEY",
    "WEBHOOK_TOKEN",
]


ACTION_REQUIRED_KEYS = [
    "GOLDAPI_KEY",
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
