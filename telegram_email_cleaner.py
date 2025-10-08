# telegram_email_cleaner.py
import os
import re
import difflib
import asyncio
import logging
from aiohttp import web
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email-cleaner-bot")

# --------------------------
# Known domains (for fuzzy correction)
# --------------------------
COMMON_DOMAINS = [
    # US / global
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "comcast.net", "verizon.net", "msn.com", "live.com",
    "protonmail.com", "zoho.com", "fastmail.com", "mail.com",
    # German / EU
    "web.de", "gmx.de", "t-online.de", "freenet.de", "posteo.de",
    "online.de", "arcor.de", "email.de", "outlook.de", "hotmail.de",
    "gmx.net", "protonmail.de", "tutanota.com",
]

# --------------------------
# Cleaning helpers
# --------------------------
def normalize_email(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'\.{2,}', '.', s)
    s = s.replace('@@', '@')
    s = re.sub(r'\.+@', '@', s)
    s = re.sub(r'@\.+', '@', s)
    s = s.strip('.')
    return s

def fuzzy_fix_domain(email: str) -> str:
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    domain = domain.strip().lower()
    domain = re.sub(r'\.(con|cim|cm|c0m)$', '.com', domain)
    domain = re.sub(r'\.(deu|d)$', '.de', domain)
    match = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.78)
    if match:
        domain = match[0]
    return f"{local}@{domain}"

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", email))

def clean_email_list(raw_items):
    seen = set()
    cleaned = []

    for raw in raw_items:
        if not raw or not isinstance(raw, str):
            continue
        s = normalize_email(raw)
        parts = re.split(r'[,\s;|]+', s)
        for p in parts:
            if not p or '@' not in p:
                continue
            p = fuzzy_fix_domain(p)
            p = p.replace('..', '.').replace('@@', '@')
            p = re.sub(r'\.+@', '@', p)
            p = p.strip('.')
            if not is_valid_email(p):
                continue
            if p not in seen:
                seen.add(p)
                cleaned.append(p)

    cleaned.sort(key=lambda e: (e.split('@')[1], e.split('@')[0]))
    return cleaned

# --------------------------
# Telegram Handlers
# --------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! Send me a .txt or .csv file (or paste emails). I'll clean duplicates, fix domains, and return a cleaned file."
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    items = [line.strip() for line in re.split(r'[\r\n]+', text) if line.strip()]
    if len(items) == 1:
        items = re.split(r'[,\s;|]+', items[0])
    cleaned = clean_email_list(items)
    if not cleaned:
        await update.message.reply_text("❌ No valid emails found after cleaning.")
        return
    out = "\n".join(cleaned)
    with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
        f.write(out)
    await update.message.reply_document(InputFile("cleaned_emails.txt"), caption=f"✅ Cleaned {len(cleaned)} emails")

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ Please send a valid .txt or .csv file.")
        return

    file = await doc.get_file()
    content = (await file.download_as_bytearray()).decode("utf-8", errors="ignore")

    items = re.split(r'[\r\n,;]+', content)
    cleaned = clean_email_list(items)
    if not cleaned:
        await update.message.reply_text("❌ No valid emails found after cleaning.")
        return
    out = "\n".join(cleaned)
    with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
        f.write(out)
    await update.message.reply_document(InputFile("cleaned_emails.txt"), caption=f"✅ Cleaned {len(cleaned)} emails")

# --------------------------
# Keep alive (for Render free plan)
# --------------------------
async def health(request):
    return web.Response(text="✅ Bot is alive and running!")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Web server running on port {port}")

# --------------------------
# Main entry
# --------------------------
async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("❌ BOT_TOKEN environment variable missing")

    await start_web()

    app = (
        ApplicationBuilder()
        .token(token)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("🤖 Bot running... waiting for Telegram messages.")
    await app.run_polling(close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
