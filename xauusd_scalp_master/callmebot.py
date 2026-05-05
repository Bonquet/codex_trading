from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable


CALLMEBOT_API_BASE_URL = "https://api.callmebot.com"


class CallMeBotError(RuntimeError):
    """Raised when a CallMeBot notification cannot be sent."""


class CallMeBotClient:
    def __init__(
        self,
        base_url: str = CALLMEBOT_API_BASE_URL,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = opener or self._default_open

    def send_whatsapp(
        self,
        text: str,
        phone: str | None = None,
        apikey: str | None = None,
        timeout: float = 10.0,
    ) -> str:
        phone = phone or os.getenv("CALLMEBOT_WHATSAPP_PHONE", "")
        apikey = apikey or os.getenv("CALLMEBOT_WHATSAPP_APIKEY", "")
        if not phone:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_PHONE before sending WhatsApp messages.")
        if not apikey:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_APIKEY before sending WhatsApp messages.")
        query = urllib.parse.urlencode({"phone": phone, "text": text, "apikey": apikey})
        return self._send(f"{self.base_url}/whatsapp.php?{query}", timeout)

    def send_telegram_group(
        self,
        text: str,
        apikey: str | None = None,
        html: bool = False,
        timeout: float = 10.0,
    ) -> str:
        apikey = apikey or os.getenv("CALLMEBOT_TELEGRAM_GROUP_APIKEY", "")
        if not apikey:
            raise CallMeBotError("Set CALLMEBOT_TELEGRAM_GROUP_APIKEY before sending Telegram group messages.")
        query = urllib.parse.urlencode({"apikey": apikey, "text": text, "html": "yes" if html else "no"})
        return self._send(f"{self.base_url}/telegram/group.php?{query}", timeout)

    def register_whatsapp_query(
        self,
        query_text: str,
        action_url: str,
        phone: str | None = None,
        apikey: str | None = None,
        timeout: float = 10.0,
    ) -> str:
        phone = phone or os.getenv("CALLMEBOT_WHATSAPP_PHONE", "")
        apikey = apikey or os.getenv("CALLMEBOT_WHATSAPP_APIKEY", "")
        if not phone:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_PHONE before registering WhatsApp queries.")
        if not apikey:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_APIKEY before registering WhatsApp queries.")
        query = urllib.parse.urlencode(
            {"phone": phone, "apikey": apikey, "query": query_text, "action": action_url}
        )
        return self._send(f"{self.base_url}/whatsapp_add.php?{query}", timeout)

    def remove_whatsapp_query(
        self,
        query_text: str,
        phone: str | None = None,
        apikey: str | None = None,
        timeout: float = 10.0,
    ) -> str:
        phone = phone or os.getenv("CALLMEBOT_WHATSAPP_PHONE", "")
        apikey = apikey or os.getenv("CALLMEBOT_WHATSAPP_APIKEY", "")
        if not phone:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_PHONE before removing WhatsApp queries.")
        if not apikey:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_APIKEY before removing WhatsApp queries.")
        query = urllib.parse.urlencode({"phone": phone, "apikey": apikey, "query": query_text})
        return self._send(f"{self.base_url}/whatsapp_remove.php?{query}", timeout)

    def list_whatsapp_queries(
        self,
        phone: str | None = None,
        apikey: str | None = None,
        timeout: float = 10.0,
    ) -> str:
        phone = phone or os.getenv("CALLMEBOT_WHATSAPP_PHONE", "")
        apikey = apikey or os.getenv("CALLMEBOT_WHATSAPP_APIKEY", "")
        if not phone:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_PHONE before listing WhatsApp queries.")
        if not apikey:
            raise CallMeBotError("Set CALLMEBOT_WHATSAPP_APIKEY before listing WhatsApp queries.")
        query = urllib.parse.urlencode({"phone": phone, "apikey": apikey})
        return self._send(f"{self.base_url}/whatsapp_list.php?{query}", timeout)

    def _send(self, url: str, timeout: float) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "xauusd-scalp-master/1.0"},
            method="GET",
        )
        try:
            raw = self.opener(request, timeout)
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise CallMeBotError(f"CallMeBot HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise CallMeBotError(f"CallMeBot network error: {exc.reason}") from exc
        return raw.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _default_open(request: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
