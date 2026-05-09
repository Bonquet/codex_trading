from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .callmebot import CallMeBotClient, CallMeBotError
from .config import missing_keys, missing_production_keys
from .goldapi import GoldApiError
from .signals import SignalRequest, run_signal


def run_webhook_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    token: str | None = None,
    memory_path: str | Path = "data/memory_state.json",
    snapshot_path: str | Path | None = None,
    pip_size: float = 0.10,
    metal: str = "XAU",
    currency: str = "USD",
    quote_timeout: float = 10.0,
    quote_source: str = "auto",
    notify_channel: str = "whatsapp",
    notify_format: str = "short",
    news_clear_30m: bool = False,
    news_clear_2h: bool = False,
    telegram_html: bool = False,
) -> None:
    active_snapshot_path = Path(snapshot_path or "data/latest_snapshot.json")
    if not token:
        missing = missing_keys(["WEBHOOK_TOKEN"])
        if missing:
            print("WARNING: WEBHOOK_TOKEN is not set. /signal will be publicly callable.")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if parsed.path == "/health":
                self.write_text(200, "OK")
                return

            if parsed.path == "/ready":
                missing = missing_production_keys("server")
                if missing:
                    self.write_text(503, "Missing required env vars: " + ", ".join(missing))
                    return
                self.write_text(200, "READY")
                return

            if parsed.path == "/snapshot":
                if not self.authorized(params, token):
                    self.write_text(403, "Forbidden: bad token")
                    return
                if not active_snapshot_path.exists():
                    self.write_text(404, "No snapshot has been stored yet.")
                    return
                self.write_json(200, json.loads(active_snapshot_path.read_text(encoding="utf-8")))
                return

            if parsed.path not in {"/signal", "/webhook"}:
                self.write_text(404, "Use /signal, /webhook?cmd=signal, or /snapshot")
                return

            if not self.authorized(params, token):
                self.write_text(403, "Forbidden: bad token")
                return

            command = params.get("cmd", ["signal"])[0].lower()
            if command not in {"signal", "/signal"}:
                self.write_text(400, "Supported command: signal")
                return

            try:
                result = run_signal(
                    SignalRequest(
                        memory_path=memory_path,
                        snapshot_path=active_snapshot_path,
                        pip_size=pip_size,
                        metal=metal,
                        currency=currency,
                        quote_timeout=quote_timeout,
                        quote_source=quote_source,
                        news_clear_30m=news_clear_30m,
                        news_clear_2h=news_clear_2h,
                    )
                )
                message = result.output if notify_format == "full" else result.alert
                notification = send_server_notification(notify_channel, message, telegram_html)
            except GoldApiError as exc:
                self.write_text(502, f"Signal unavailable: {exc}")
                return
            except CallMeBotError as exc:
                self.write_text(502, f"Notification unavailable: {exc}")
                return
            self.write_text(200, f"{result.output}\nNOTIFICATION SENT: {notify_channel} | {notification}")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if parsed.path != "/snapshot":
                self.write_text(404, "Use POST /snapshot?token=...")
                return
            if not self.authorized(params, token):
                self.write_text(403, "Forbidden: bad token")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("snapshot must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                self.write_text(400, f"Invalid snapshot JSON: {exc}")
                return
            active_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            active_snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.write_json(200, {"status": "stored", "path": str(active_snapshot_path)})

        def log_message(self, format: str, *args) -> None:
            print(f"{self.address_string()} - {format % args}")

        @staticmethod
        def authorized(params: dict[str, list[str]], expected_token: str | None) -> bool:
            return not expected_token or params.get("token", [""])[0] == expected_token

        def write_text(self, status: int, body: str) -> None:
            data = body.encode("utf-8", errors="replace")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def write_json(self, status: int, payload: dict) -> None:
            data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Webhook server listening on http://{host}:{port}")
    print("Local test URL: " + f"http://{host}:{port}/signal" + (f"?token={token}" if token else ""))
    print(f"Snapshot path: {active_snapshot_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping webhook server.")
    finally:
        server.server_close()


def send_server_notification(channel: str, text: str, telegram_html: bool = False) -> str:
    client = CallMeBotClient()
    if channel == "whatsapp":
        return client.send_whatsapp(text)
    if channel == "telegram-group":
        return client.send_telegram_group(text, html=telegram_html)
    raise CallMeBotError(f"Unsupported notification channel: {channel}")
