from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .callmebot import CallMeBotClient, CallMeBotError
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
    notify_channel: str = "whatsapp",
    news_clear_30m: bool = False,
    news_clear_2h: bool = False,
    telegram_html: bool = False,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if parsed.path == "/health":
                self.write_text(200, "OK")
                return

            if parsed.path not in {"/signal", "/webhook"}:
                self.write_text(404, "Use /signal or /webhook?cmd=signal")
                return

            if token and params.get("token", [""])[0] != token:
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
                        snapshot_path=snapshot_path,
                        pip_size=pip_size,
                        metal=metal,
                        currency=currency,
                        quote_timeout=quote_timeout,
                        news_clear_30m=news_clear_30m,
                        news_clear_2h=news_clear_2h,
                    )
                )
                notification = send_server_notification(notify_channel, result.output, telegram_html)
            except GoldApiError as exc:
                self.write_text(502, f"Signal unavailable: {exc}")
                return
            except CallMeBotError as exc:
                self.write_text(502, f"Notification unavailable: {exc}")
                return
            self.write_text(200, f"{result.output}\nNOTIFICATION SENT: {notify_channel} | {notification}")

        def log_message(self, format: str, *args) -> None:
            print(f"{self.address_string()} - {format % args}")

        def write_text(self, status: int, body: str) -> None:
            data = body.encode("utf-8", errors="replace")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Webhook server listening on http://{host}:{port}")
    print("Local test URL: " + f"http://{host}:{port}/signal" + (f"?token={token}" if token else ""))
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
