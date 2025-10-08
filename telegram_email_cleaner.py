import os
import re
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# --- Logging setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Email cleaning function ---
def clean_emails(raw_text):
    # Extract possible emails
    potential_emails = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', raw_text)

    cleaned_emails = set()
    for email in potential_emails:
        email = email.strip().lower()

        # Fix common mistakes
        email = re.sub(r'\.\.+', '.', email)  # remove double dots
        email = re.sub(r'\.@', '@', email)    # remove dot before @
        email = re.sub(r'@\.', '@', email)    # remove @. mistake
        email = re.sub(r'[^a-z0-9._%+-@]', '', email)  # remove invalid chars
        email = re.sub(r'(\.[a-z]{2,})\1+', r'\1', email)  # remove duplicate TLDs

        # Validate final email
        if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email):
            cleaned_emails.add(email)

    return "\n".join(sorted(cleaned_emails))

# --- Telegram Handlers ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    cleaned = clean_emails(text)

    if cleaned:
        await update.message.reply_text(f"✅ Cleaned emails:\n\n{cleaned}")
    else:
        await update.message.reply_text("⚠️ No valid emails found.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me your email list and I'll clean it up!")

# --- Web server for Render (keeps service alive) ---
async def handle(request):
    return web.Response(text="Telegram bot is running!", content_type='text/plain')

async def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_TOKEN not set. Please add it to Render environment variables.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, start))

    # Start Telegram bot in background
    asyncio.create_task(app.run_polling())

    # Start dummy web server on Render
    port = int(os.environ.get("PORT", 10000))
    web_app = web.Application()
    web_app.router.add_get("/", handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    logger.info(f"🚀 Server running on port {port}")
    await site.start()

    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
