# XAUUSD Short Scalp Master

Broker-neutral paper-trading and checklist engine for the XAUUSD short scalp system.

This project does not place live trades, connect to a broker, or guarantee a win rate. It is a discipline layer: feed it current chart/news/sentiment facts, and it returns `SELL`, `WAIT`, or `NO TRADE` with the required memory check, market state, checklist, and risk plan.

## What It Implements

- Persistent `MEMORY_STATE` in `data/memory_state.json`
- Mandatory `MEMORY CHECK` before every analysis
- Market states: `PRIME`, `CAUTION`, `NO_TRADE`, `RECOVERY`, `HYPER`
- Entry matrix with HTF bias, 1-minute EMA/RSI execution, patterns, MACD, volume, ATR, DXY/COT/news filters
- Dynamic risk profiles by state
- Post-trade memory updates for last 10 trades, 24h win rate, streaks, daily PnL, and avoidance patterns
- Failure analysis for fakeouts, news spikes, overextension, and chop
- Live XAU/USD quote lookup through GoldAPI.io using `GOLDAPI_KEY`

## GoldAPI Setup

Do not hardcode your API key in the repo. Set it in the current PowerShell session:

```powershell
$env:GOLDAPI_KEY = "your-goldapi-key"
```

The live quote client uses:

```text
GET https://www.goldapi.io/api/XAU/USD
Header: x-access-token: $GOLDAPI_KEY
```

## Get A Live Signal

The `signal` command fetches the live XAU/USD price from GoldAPI and then runs the same strict checklist engine.

```powershell
python -m xauusd_scalp_master signal `
  --news-clear-30m `
  --news-clear-2h
```

Price alone is not enough to approve a short. To get a true `SELL`, provide the live chart confirmations too:

```powershell
python -m xauusd_scalp_master signal `
  --news-clear-30m `
  --news-clear-2h `
  --htf-below-200ema `
  --htf-lower-high `
  --bearish-structure `
  --ema50-rejection `
  --ema50-slope-negative `
  --rsi 58 `
  --rsi-previous 62 `
  --macd-bearish-cross `
  --volume-spike-rejection `
  --atr-pips 11 `
  --bearish-engulfing-resistance `
  --shooting-star-rejection `
  --dxy-strengthening `
  --cot-commercial-shorts-increasing `
  --swing-high 2652.20
```

Without verified chart/news confirmations, a valid signal is `WAIT` or `NO TRADE`.

## CallMeBot Notifications

CallMeBot can send the signal result to WhatsApp or a Telegram group. It is an outbound notification tool; it does not turn this bot into a two-way WhatsApp chat listener.

The CLI automatically loads local secrets from `.env` if that file exists. `.env` is ignored by git; use `.env.example` as the template.

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your real keys.

### WhatsApp Direct Message

1. Add the current CallMeBot WhatsApp number from the CallMeBot setup page to your phone contacts.
2. Send this message to that WhatsApp contact:

```text
I allow callmebot to send me messages
```

3. Wait for the activation reply containing your API key.
4. Set the values in PowerShell:

```powershell
$env:CALLMEBOT_WHATSAPP_PHONE = "+15551234567"
$env:CALLMEBOT_WHATSAPP_APIKEY = "your-callmebot-whatsapp-apikey"
```

Or put the values in `.env`:

```text
CALLMEBOT_WHATSAPP_PHONE=12068145743
CALLMEBOT_WHATSAPP_APIKEY=your-callmebot-whatsapp-apikey
```

Check that the CLI sees your local config without printing the full secrets:

```powershell
python -m xauusd_scalp_master config
```

5. Send a test:

```powershell
python -m xauusd_scalp_master notify "XAU bot test" --channel whatsapp
```

6. Send live signal output to WhatsApp:

```powershell
python -m xauusd_scalp_master signal `
  --news-clear-30m `
  --news-clear-2h `
  --notify whatsapp
```

CallMeBot's WhatsApp API sends only to your activated contact. It does not send WhatsApp messages to groups or receive replies.

### Make `/signal` Work From WhatsApp

Sending `/signal` to the CallMeBot WhatsApp contact only works after two things are running:

- Your local webhook server.
- A public HTTPS tunnel that CallMeBot can reach.

Start the local server:

```powershell
python -m xauusd_scalp_master serve `
  --token change-this-secret `
  --news-clear-30m `
  --news-clear-2h
```

Expose it with a tunnel such as ngrok or Cloudflare Tunnel. Example with ngrok:

```powershell
ngrok http 8787
```

Copy the HTTPS URL from the tunnel, then register `/signal` with CallMeBot:

```powershell
python -m xauusd_scalp_master register-whatsapp `
  --query "/signal" `
  --action-url "https://YOUR-TUNNEL-URL/webhook?cmd=signal&token=change-this-secret"
```

Now when you send `/signal` to the CallMeBot WhatsApp contact, CallMeBot calls your webhook, the bot runs the signal check, and the bot sends the result back to WhatsApp.

Check registered CallMeBot WhatsApp commands:

```powershell
python -m xauusd_scalp_master list-whatsapp
```

### Automatic Valid Signal Alerts

Use `watch` to poll and send a WhatsApp message only when the engine sees a real valid `SELL`:

```powershell
Copy-Item data/latest_snapshot.example.json data/latest_snapshot.json
python -m xauusd_scalp_master watch `
  --snapshot data/latest_snapshot.json `
  --news-clear-30m `
  --news-clear-2h `
  --notify whatsapp `
  --interval 60 `
  --cooldown 300
```

`data/latest_snapshot.json` must be updated by your charting/data stack with EMA, RSI, MACD, ATR, volume, DXY, COT, and news confirmations. GoldAPI only supplies the live XAU/USD quote, so the watcher will not send a valid `SELL` alert from price alone.

## GitHub Remote Automation

This repo includes GitHub Actions for remote scheduled checks:

- `.github/workflows/tests.yml` runs the unit tests.
- `.github/workflows/auto-signal.yml` runs every 5 minutes during the broad London-NY overlap window and sends WhatsApp only when the engine returns a valid `SELL`.

Set these repository secrets in GitHub:

```text
GOLDAPI_KEY
CALLMEBOT_WHATSAPP_PHONE
CALLMEBOT_WHATSAPP_APIKEY
```

Optional, but needed for real valid signals:

```text
SIGNAL_SNAPSHOT_JSON
```

`SIGNAL_SNAPSHOT_JSON` should contain chart confirmations like this:

```json
{
  "htf_below_200ema": true,
  "htf_lower_high": true,
  "bearish_structure": true,
  "ema50_rejection": true,
  "ema50_slope_negative": true,
  "rsi": 58,
  "rsi_previous": 62,
  "macd_bearish_cross": true,
  "volume_spike_rejection": true,
  "atr_pips": 11,
  "bearish_engulfing_resistance": true,
  "shooting_star_rejection": true,
  "dxy_strengthening": true,
  "cot_commercial_shorts_increasing": true,
  "news_checked_30m": true,
  "news_checked_2h": true,
  "swing_high": 2652.2
}
```

GitHub Actions can run scheduled automatic checks while your PC is off. It cannot act as a public inbound WhatsApp webhook for `/signal`; for that you still need a small always-on web service such as Cloudflare Workers, Render, Railway, or a VPS.

### Telegram Group Message

CallMeBot supports Telegram group messages with a separate group API key.

1. Start/authorize CallMeBot from the Telegram setup page.
2. Create your Telegram group.
3. Add `@API_CallMeBot` to the group.
4. Use the CallMeBot Telegram group setup page to get the group API key.
5. Set the key:

```powershell
$env:CALLMEBOT_TELEGRAM_GROUP_APIKEY = "your-telegram-group-apikey"
```

6. Send a test:

```powershell
python -m xauusd_scalp_master notify "XAU bot test" --channel telegram-group
```

7. Send live signal output to the Telegram group:

```powershell
python -m xauusd_scalp_master signal `
  --news-clear-30m `
  --news-clear-2h `
  --notify telegram-group
```

## Analyze A Setup

```powershell
python -m xauusd_scalp_master analyze `
  --timestamp 2026-05-05T09:17:00-04:00 `
  --price 2652.10 `
  --htf-below-200ema `
  --htf-lower-high `
  --bearish-structure `
  --ema50-rejection `
  --ema50-slope-negative `
  --rsi 58 `
  --rsi-previous 62 `
  --macd-bearish-cross `
  --volume-spike-rejection `
  --atr-pips 11 `
  --bearish-engulfing-resistance `
  --shooting-star-rejection `
  --dxy-strengthening `
  --cot-commercial-shorts-increasing `
  --swing-high 2652.20
```

Example output:

```text
MEMORY CHECK: Last trade NONE. Win rate: 0.0%. Bias: unknown
MARKET STATE: PRIME
ACTION: SELL
...
ENTRY: SELL @ 2652.10 | SL: 2653.00 | TP1: 2651.10 | TP2: 2650.30 | Risk: 1.00%
```

## Record A Completed Trade

```powershell
python -m xauusd_scalp_master record `
  --timestamp 2026-05-05T09:35:00-04:00 `
  --entry 2652.10 `
  --exit 2650.40 `
  --pips 17 `
  --reason "RSI rejection" `
  --state PRIME `
  --pnl-percent 0.4
```

For a loss, include a useful reason so the memory system can add an avoidance pattern:

```powershell
python -m xauusd_scalp_master record `
  --timestamp 2026-05-05T09:55:00-04:00 `
  --entry 2652.10 `
  --exit 2653.00 `
  --pips -9 `
  --reason "news spike reversal" `
  --state PRIME `
  --pnl-percent -0.3
```

## Show Memory

```powershell
python -m xauusd_scalp_master show-memory
```

## Notes

- Default `pip_size` is `0.10`, meaning 10 pips equals 1.00 XAUUSD price unit. Change `--pip-size` if your broker defines gold pips differently.
- `CAUTION` is treated as `WAIT`, even though the risk table is stored for completeness.
- `RECOVERY` can still trade if every checklist item passes, but risk is reduced to 0.3%.
- GoldAPI provides the live XAU/USD quote. Economic calendar data, DXY, COT, volume, and indicator values must still come from your charting/data stack.
