from __future__ import annotations

import os
from pathlib import Path


CONFIG_KEYS = [
    "GOLDAPI_KEY",
    "CALLMEBOT_WHATSAPP_PHONE",
    "CALLMEBOT_WHATSAPP_APIKEY",
    "CALLMEBOT_TELEGRAM_GROUP_APIKEY",
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


def redact(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return f"{value[:2]}...{value[-2:]}"
    return f"{value[:4]}...{value[-4:]}"
