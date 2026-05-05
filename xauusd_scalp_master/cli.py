from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .callmebot import CallMeBotClient, CallMeBotError
from .config import ACTION_REQUIRED_KEYS, SERVER_REQUIRED_KEYS, env_bool, env_float, env_int, load_env_file, missing_keys, redacted_config_lines
from .engine import (
    MarketSnapshot,
    TradeRecord,
    analyze_failure_reason,
    analyze_setup,
    format_decision,
    load_memory,
    parse_timestamp,
    record_trade,
    save_memory,
)
from .goldapi import GoldApiError
from .server import run_webhook_server
from .signals import SignalRequest, run_signal


DEFAULT_MEMORY_PATH = Path("data/memory_state.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xauusd-scalp-master",
        description="Broker-neutral XAUUSD short scalp memory and checklist engine.",
    )
    parser.add_argument("--memory", default=str(DEFAULT_MEMORY_PATH), help="Path to persistent memory JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a candidate short scalp setup.")
    analyze_parser.add_argument("--snapshot", help="JSON file containing a MarketSnapshot payload.")
    analyze_parser.add_argument("--pip-size", type=float, default=0.10, help="XAUUSD pip size; broker-dependent.")
    add_snapshot_args(analyze_parser)

    signal_parser = subparsers.add_parser("signal", help="Fetch live XAU/USD price and run the checklist engine.")
    signal_parser.add_argument("--snapshot", help="Optional JSON file with chart/news confirmations to merge with the live quote.")
    signal_parser.add_argument("--pip-size", type=float, default=0.10, help="XAUUSD pip size; broker-dependent.")
    signal_parser.add_argument("--metal", default="XAU", help="GoldAPI metal symbol.")
    signal_parser.add_argument("--currency", default="USD", help="GoldAPI currency symbol.")
    signal_parser.add_argument("--timeout", type=float, default=10.0, help="GoldAPI request timeout in seconds.")
    signal_parser.add_argument("--news-clear-30m", action="store_true", help="Confirm economic calendar is clear for 30 minutes.")
    signal_parser.add_argument("--news-clear-2h", action="store_true", help="Confirm high-impact news is clear for 2 hours.")
    signal_parser.add_argument(
        "--notify",
        choices=["whatsapp", "telegram-group"],
        help="Send the signal result through CallMeBot.",
    )
    signal_parser.add_argument("--notify-timeout", type=float, default=10.0, help="CallMeBot request timeout in seconds.")
    signal_parser.add_argument("--telegram-html", action="store_true", help="Send Telegram group notification as HTML.")
    add_snapshot_args(signal_parser)

    watch_parser = subparsers.add_parser("watch", help="Poll for valid signals and notify automatically.")
    watch_parser.add_argument("--snapshot", help="JSON file with live chart/news confirmations.")
    watch_parser.add_argument("--pip-size", type=float, default=0.10)
    watch_parser.add_argument("--metal", default="XAU")
    watch_parser.add_argument("--currency", default="USD")
    watch_parser.add_argument("--timeout", type=float, default=10.0)
    watch_parser.add_argument("--interval", type=float, default=env_float("WATCH_INTERVAL", 60.0), help="Seconds between signal checks.")
    watch_parser.add_argument("--cooldown", type=float, default=env_float("WATCH_COOLDOWN", 300.0), help="Seconds between repeated valid alerts.")
    watch_parser.add_argument("--notify", choices=["whatsapp", "telegram-group"], default="whatsapp")
    watch_parser.add_argument("--notify-all", action="store_true", default=env_bool("NOTIFY_ALL", False), help="Notify even when the signal is WAIT/NO TRADE.")
    watch_parser.add_argument("--once", action="store_true", help="Run one watch iteration then exit.")
    watch_parser.add_argument("--news-clear-30m", action="store_true", default=env_bool("NEWS_CLEAR_30M", False))
    watch_parser.add_argument("--news-clear-2h", action="store_true", default=env_bool("NEWS_CLEAR_2H", False))
    watch_parser.add_argument("--telegram-html", action="store_true")

    serve_parser = subparsers.add_parser("serve", help="Run a local HTTP webhook server for CallMeBot commands.")
    serve_parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    serve_parser.add_argument("--port", type=int, default=env_int("PORT", 8787))
    serve_parser.add_argument("--token", default=os.getenv("WEBHOOK_TOKEN"), help="Shared secret required as ?token=... on webhook URLs.")
    serve_parser.add_argument("--snapshot", default=os.getenv("SIGNAL_SNAPSHOT_PATH"), help="JSON file with live chart/news confirmations.")
    serve_parser.add_argument("--pip-size", type=float, default=0.10)
    serve_parser.add_argument("--metal", default="XAU")
    serve_parser.add_argument("--currency", default="USD")
    serve_parser.add_argument("--timeout", type=float, default=10.0)
    serve_parser.add_argument("--notify", choices=["whatsapp", "telegram-group"], default="whatsapp")
    serve_parser.add_argument("--news-clear-30m", action="store_true", default=env_bool("NEWS_CLEAR_30M", False))
    serve_parser.add_argument("--news-clear-2h", action="store_true", default=env_bool("NEWS_CLEAR_2H", False))
    serve_parser.add_argument("--telegram-html", action="store_true")

    register_parser = subparsers.add_parser("register-whatsapp", help="Register a CallMeBot WhatsApp query webhook.")
    register_parser.add_argument("--query", default="/signal")
    register_parser.add_argument("--action-url", required=True)
    register_parser.add_argument("--timeout", type=float, default=10.0)

    subparsers.add_parser("list-whatsapp", help="List CallMeBot WhatsApp query webhooks.")

    doctor_parser = subparsers.add_parser("doctor", help="Validate required production configuration.")
    doctor_parser.add_argument("--mode", choices=["server", "actions"], default="server")

    notify_parser = subparsers.add_parser("notify", help="Send a test message through CallMeBot.")
    notify_parser.add_argument("text", help="Message text to send.")
    notify_parser.add_argument("--channel", choices=["whatsapp", "telegram-group"], default="whatsapp")
    notify_parser.add_argument("--timeout", type=float, default=10.0)
    notify_parser.add_argument("--telegram-html", action="store_true")

    subparsers.add_parser("config", help="Print redacted API configuration status.")

    record_parser = subparsers.add_parser("record", help="Record a completed paper/manual trade.")
    record_parser.add_argument("--timestamp", help="ISO timestamp. Naive values are treated as Eastern time.")
    record_parser.add_argument("--entry", type=float, required=True)
    record_parser.add_argument("--exit", type=float, required=True)
    record_parser.add_argument("--pips", type=float)
    record_parser.add_argument("--pip-size", type=float, default=0.10)
    record_parser.add_argument("--side", choices=["short"], default="short")
    record_parser.add_argument("--reason", default="")
    record_parser.add_argument("--state", default="")
    record_parser.add_argument("--pnl-percent", type=float, default=0.0)

    subparsers.add_parser("show-memory", help="Print the current persistent memory JSON.")

    args = parser.parse_args(argv)
    load_env_file()

    if args.command == "config":
        print("\n".join(redacted_config_lines()))
        return 0

    if args.command == "doctor":
        keys = SERVER_REQUIRED_KEYS if args.mode == "server" else ACTION_REQUIRED_KEYS
        missing = missing_keys(keys)
        print("\n".join(redacted_config_lines()))
        if missing:
            raise SystemExit("Missing required env vars: " + ", ".join(missing))
        print(f"DOCTOR OK: {args.mode} configuration is present.")
        return 0

    memory = load_memory(args.memory)

    if args.command == "analyze":
        snapshot = snapshot_from_args(args)
        decision = analyze_setup(memory, snapshot, pip_size=args.pip_size)
        print(format_decision(decision))
        return 0

    if args.command == "signal":
        try:
            request = signal_request_from_args(args, args.memory)
            result = run_signal(request)
        except GoldApiError as exc:
            raise SystemExit(f"Signal unavailable: {exc}") from exc
        print(result.output)
        if args.notify:
            send_notification(args.notify, result.output, args.notify_timeout, telegram_html=args.telegram_html)
        return 0

    if args.command == "watch":
        run_watch(args)
        return 0

    if args.command == "serve":
        run_webhook_server(
            host=args.host,
            port=args.port,
            token=args.token,
            memory_path=args.memory,
            snapshot_path=args.snapshot,
            pip_size=args.pip_size,
            metal=args.metal,
            currency=args.currency,
            quote_timeout=args.timeout,
            notify_channel=args.notify,
            news_clear_30m=args.news_clear_30m,
            news_clear_2h=args.news_clear_2h,
            telegram_html=args.telegram_html,
        )
        return 0

    if args.command == "register-whatsapp":
        try:
            response = CallMeBotClient().register_whatsapp_query(args.query, args.action_url, timeout=args.timeout)
        except CallMeBotError as exc:
            raise SystemExit(f"WhatsApp registration unavailable: {exc}") from exc
        print(f"WHATSAPP QUERY REGISTERED: {response}")
        return 0

    if args.command == "list-whatsapp":
        try:
            response = CallMeBotClient().list_whatsapp_queries()
        except CallMeBotError as exc:
            raise SystemExit(f"WhatsApp query list unavailable: {exc}") from exc
        print(response)
        return 0

    if args.command == "notify":
        send_notification(args.channel, args.text, args.timeout, telegram_html=args.telegram_html)
        return 0

    if args.command == "record":
        timestamp = parse_timestamp(args.timestamp)
        pips = args.pips
        if pips is None:
            pips = (args.entry - args.exit) / args.pip_size
        success = pips > 0
        failure_mode = ""
        if not success:
            failure_mode, countermeasure = analyze_failure_reason(args.reason)
            print(f"FAILURE ANALYSIS: {failure_mode}. {countermeasure}")
        trade = TradeRecord(
            timestamp=timestamp,
            entry=args.entry,
            exit=args.exit,
            pips=pips,
            success=success,
            reason=args.reason,
            state=args.state,
            pnl_percent=args.pnl_percent,
            failure_mode=failure_mode,
        )
        updated = record_trade(memory, trade)
        save_memory(updated, args.memory)
        print(
            "MEMORY UPDATED: "
            f"last_trade={'SUCCESS' if success else 'FAILURE'}, "
            f"win_rate_24h={updated['win_rate_24h']:.1f}%, "
            f"consecutive_losses={updated['consecutive_losses']}, "
            f"success_streak={updated['success_streak']}"
        )
        return 0

    if args.command == "show-memory":
        print(json.dumps(memory, indent=2, sort_keys=True))
        return 0

    return 2


def add_snapshot_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timestamp", help="ISO timestamp. Naive values are treated as Eastern time.")
    parser.add_argument("--price", type=float)
    parser.add_argument("--htf-below-200ema", action="store_true")
    parser.add_argument("--htf-lower-high", action="store_true")
    parser.add_argument("--bearish-structure", action="store_true")
    parser.add_argument("--ema50-rejection", action="store_true")
    parser.add_argument("--ema50-slope-negative", action="store_true")
    parser.add_argument("--price-crossed-below-ema50", action="store_true")
    parser.add_argument("--rsi", type=float)
    parser.add_argument("--rsi-previous", type=float)
    parser.add_argument("--macd-bearish-cross", action="store_true")
    parser.add_argument("--macd-histogram-shrinking", action="store_true")
    parser.add_argument("--volume-spike-rejection", action="store_true")
    parser.add_argument("--atr-pips", type=float, default=0.0)
    parser.add_argument("--bearish-engulfing-resistance", action="store_true")
    parser.add_argument("--shooting-star-rejection", action="store_true")
    parser.add_argument("--orderblock-rejection", action="store_true")
    parser.add_argument("--dxy-strengthening", action="store_true")
    parser.add_argument("--cot-commercial-shorts-increasing", action="store_true")
    parser.add_argument("--news-within-30m", action="store_true")
    parser.add_argument("--news-within-2h", action="store_true")
    parser.add_argument("--resistance-price", type=float)
    parser.add_argument("--swing-high", type=float)


def snapshot_from_args(args: argparse.Namespace) -> MarketSnapshot:
    if args.snapshot:
        with Path(args.snapshot).open("r", encoding="utf-8") as handle:
            return MarketSnapshot.from_mapping(json.load(handle))
    if args.price is None:
        raise SystemExit("--price is required unless --snapshot is provided.")
    return MarketSnapshot(
        timestamp=parse_timestamp(args.timestamp),
        price=args.price,
        htf_below_200ema=args.htf_below_200ema,
        htf_lower_high=args.htf_lower_high,
        bearish_structure=args.bearish_structure,
        ema50_rejection=args.ema50_rejection,
        ema50_slope_negative=args.ema50_slope_negative,
        price_crossed_below_ema50=args.price_crossed_below_ema50,
        rsi=args.rsi,
        rsi_previous=args.rsi_previous,
        macd_bearish_cross=args.macd_bearish_cross,
        macd_histogram_shrinking=args.macd_histogram_shrinking,
        volume_spike_rejection=args.volume_spike_rejection,
        atr_pips=args.atr_pips,
        bearish_engulfing_resistance=args.bearish_engulfing_resistance,
        shooting_star_rejection=args.shooting_star_rejection,
        orderblock_rejection=args.orderblock_rejection,
        dxy_strengthening=args.dxy_strengthening,
        cot_commercial_shorts_increasing=args.cot_commercial_shorts_increasing,
        news_within_30m=args.news_within_30m,
        news_within_2h=args.news_within_2h,
        resistance_price=args.resistance_price,
        swing_high=args.swing_high,
    )


def snapshot_from_signal_args(args: argparse.Namespace, quote) -> MarketSnapshot:
    payload = {}
    if args.snapshot:
        with Path(args.snapshot).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

    payload.update(
        {
            "timestamp": quote.timestamp,
            "price": quote.price,
            "htf_below_200ema": args.htf_below_200ema or bool(payload.get("htf_below_200ema", False)),
            "htf_lower_high": args.htf_lower_high or bool(payload.get("htf_lower_high", False)),
            "bearish_structure": args.bearish_structure or bool(payload.get("bearish_structure", False)),
            "ema50_rejection": args.ema50_rejection or bool(payload.get("ema50_rejection", False)),
            "ema50_slope_negative": args.ema50_slope_negative or bool(payload.get("ema50_slope_negative", False)),
            "price_crossed_below_ema50": args.price_crossed_below_ema50
            or bool(payload.get("price_crossed_below_ema50", False)),
            "rsi": args.rsi if args.rsi is not None else payload.get("rsi"),
            "rsi_previous": args.rsi_previous if args.rsi_previous is not None else payload.get("rsi_previous"),
            "macd_bearish_cross": args.macd_bearish_cross or bool(payload.get("macd_bearish_cross", False)),
            "macd_histogram_shrinking": args.macd_histogram_shrinking
            or bool(payload.get("macd_histogram_shrinking", False)),
            "volume_spike_rejection": args.volume_spike_rejection or bool(payload.get("volume_spike_rejection", False)),
            "atr_pips": args.atr_pips if args.atr_pips else float(payload.get("atr_pips", 0.0) or 0.0),
            "bearish_engulfing_resistance": args.bearish_engulfing_resistance
            or bool(payload.get("bearish_engulfing_resistance", False)),
            "shooting_star_rejection": args.shooting_star_rejection
            or bool(payload.get("shooting_star_rejection", False)),
            "orderblock_rejection": args.orderblock_rejection or bool(payload.get("orderblock_rejection", False)),
            "dxy_strengthening": args.dxy_strengthening or bool(payload.get("dxy_strengthening", False)),
            "cot_commercial_shorts_increasing": args.cot_commercial_shorts_increasing
            or bool(payload.get("cot_commercial_shorts_increasing", False)),
            "news_within_30m": args.news_within_30m or bool(payload.get("news_within_30m", False)),
            "news_within_2h": args.news_within_2h or bool(payload.get("news_within_2h", False)),
            "news_checked_30m": args.news_clear_30m
            or args.news_within_30m
            or bool(payload.get("news_checked_30m", False))
            or bool(payload.get("news_clear_30m", False)),
            "news_checked_2h": args.news_clear_2h
            or args.news_within_2h
            or bool(payload.get("news_checked_2h", False))
            or bool(payload.get("news_clear_2h", False)),
            "resistance_price": args.resistance_price
            if args.resistance_price is not None
            else payload.get("resistance_price"),
            "swing_high": args.swing_high if args.swing_high is not None else payload.get("swing_high"),
        }
    )
    return MarketSnapshot.from_mapping(payload)


def signal_request_from_args(args: argparse.Namespace, memory_path: str | Path) -> SignalRequest:
    overrides = {}
    bool_fields = [
        "htf_below_200ema",
        "htf_lower_high",
        "bearish_structure",
        "ema50_rejection",
        "ema50_slope_negative",
        "price_crossed_below_ema50",
        "macd_bearish_cross",
        "macd_histogram_shrinking",
        "volume_spike_rejection",
        "bearish_engulfing_resistance",
        "shooting_star_rejection",
        "orderblock_rejection",
        "dxy_strengthening",
        "cot_commercial_shorts_increasing",
        "news_within_30m",
        "news_within_2h",
    ]
    for field_name in bool_fields:
        if getattr(args, field_name, False):
            overrides[field_name] = True
    for field_name in ["rsi", "rsi_previous", "atr_pips", "resistance_price", "swing_high"]:
        value = getattr(args, field_name, None)
        if value is not None:
            overrides[field_name] = value
    return SignalRequest(
        memory_path=memory_path,
        snapshot_path=getattr(args, "snapshot", None),
        snapshot_overrides=overrides,
        pip_size=args.pip_size,
        metal=args.metal,
        currency=args.currency,
        quote_timeout=args.timeout,
        news_clear_30m=getattr(args, "news_clear_30m", False),
        news_clear_2h=getattr(args, "news_clear_2h", False),
    )


def run_watch(args: argparse.Namespace) -> None:
    last_sent = 0.0
    while True:
        try:
            result = run_signal(signal_request_from_args(args, args.memory))
        except GoldApiError as exc:
            print(f"Signal unavailable: {exc}")
        else:
            print(result.output)
            now = time.monotonic()
            should_notify = result.decision.should_trade or args.notify_all
            cooldown_ready = now - last_sent >= args.cooldown
            if should_notify and cooldown_ready:
                send_notification(args.notify, result.output, 10.0, telegram_html=args.telegram_html)
                last_sent = now
        if args.once:
            break
        time.sleep(args.interval)


def send_notification(channel: str, text: str, timeout: float, telegram_html: bool = False) -> None:
    client = CallMeBotClient()
    try:
        if channel == "whatsapp":
            response = client.send_whatsapp(text, timeout=timeout)
        elif channel == "telegram-group":
            response = client.send_telegram_group(text, timeout=timeout, html=telegram_html)
        else:
            raise SystemExit(f"Unsupported notification channel: {channel}")
    except CallMeBotError as exc:
        raise SystemExit(f"Notification unavailable: {exc}") from exc
    print(f"NOTIFICATION SENT: {channel} | {response}")


if __name__ == "__main__":
    raise SystemExit(main())
