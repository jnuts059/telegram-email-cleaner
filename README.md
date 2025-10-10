# Telegram Email Cleaner

A small Telegram bot that accepts pasted emails or uploaded files (.txt, .csv, .xlsx), cleans and deduplicates email addresses, and returns a cleaned file plus summary.

## Quick start (local)

1. Create and activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your Telegram bot token (do NOT commit it):

```bash
export TELEGRAM_BOT_TOKEN="<your-token-here>"
```

4. Run the bot:

```bash
python3 telegram_email_cleaner.py
```

5. Send `/start` to your bot in Telegram to confirm it's working.

## Deploying to Render (free web service)

This project includes a `render.yaml` so Render can deploy it automatically. The bot will run as a web service (exposes a health endpoint) while polling Telegram in the background.

1. Push the repository to GitHub or GitLab.
2. Create a New -> Web Service on Render and connect your repository and branch (e.g., `main`).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python3 telegram_email_cleaner.py`
5. Add an Environment Variable in Render: `TELEGRAM_BOT_TOKEN` (value: your bot token). Mark it secret.
6. Deploy and watch Live Logs. The service will respond to `/` with `OK` for health checks.

Notes:
- If you prefer webhooks, you'll need to implement an HTTPS endpoint and register it with Telegram. Polling keeps things simpler and works on Render's free web tier as a Web service.
- Do not commit secrets to the repository.

## Files of interest
- `telegram_email_cleaner.py` - main bot and server logic
- `Email_cleaner.py` - additional email cleaning helpers
- `requirements.txt` - Python dependencies
- `render.yaml` - Render deployment configuration

## Troubleshooting
- ModuleNotFoundError: ensure you installed requirements in the environment used to run the bot.
- InvalidToken: ensure `TELEGRAM_BOT_TOKEN` is set correctly in Render and locally.
- Check `bot.log` for runtime logs.

If you'd like, I can also add a `.env.example` and `python-dotenv` support to make local dev easier.
