# Production Runbook

This bot has two production modes:

- Scheduled alerts through GitHub Actions.
- On-demand `/signal` replies through a hosted webhook service.

## Required Secrets

Never commit real keys. Put these in the deployment provider and in GitHub Actions secrets:

```text
GOLDAPI_KEY
CALLMEBOT_WHATSAPP_PHONE
CALLMEBOT_WHATSAPP_APIKEY
WEBHOOK_TOKEN
```

For real valid signals, also provide:

```text
SIGNAL_SNAPSHOT_JSON
```

GoldAPI supplies price only. `SIGNAL_SNAPSHOT_JSON` must supply chart/news confirmations.

## Hosted Webhook

Deploy the repo as a Docker web service. The container runs:

```bash
python -m xauusd_scalp_master serve --host 0.0.0.0 --port "$PORT"
```

Health checks:

```text
GET /health
GET /ready
```

Webhook:

```text
GET /webhook?cmd=signal&token=YOUR_WEBHOOK_TOKEN
```

After deployment, register the WhatsApp command with CallMeBot:

```powershell
python -m xauusd_scalp_master register-whatsapp `
  --query "/signal" `
  --action-url "https://YOUR-HOST/webhook?cmd=signal&token=YOUR_WEBHOOK_TOKEN"
```

Then `/signal` sent to the CallMeBot WhatsApp contact will call the hosted service and send the signal result back to WhatsApp.

## GitHub Actions Scheduled Alerts

Set GitHub repository secrets:

```text
GOLDAPI_KEY
CALLMEBOT_WHATSAPP_PHONE
CALLMEBOT_WHATSAPP_APIKEY
SIGNAL_SNAPSHOT_JSON
```

The scheduled workflow runs every 5 minutes in the broad London-NY overlap window. It sends WhatsApp only when `should_trade` is true.

For a test notification, run the workflow manually with `notify_all=true`.

## Local Verification

```powershell
python -m xauusd_scalp_master doctor --mode server
python -m unittest discover -v
python -m xauusd_scalp_master signal --news-clear-30m --news-clear-2h --notify whatsapp
```

## Security Notes

- Keep `WEBHOOK_TOKEN` long and random.
- Rotate keys if they were ever pasted into a public place.
- Do not expose `/webhook` without a token.
- This project is a signal and notification system, not live trade execution.
