import re
import os
import difflib
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# ========================
# 1️⃣ COMMON EMAIL DOMAINS (US + Germany + Global)
# ========================
COMMON_DOMAINS = [
    # US-based
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "comcast.net", "msn.com",
    "att.net", "verizon.net", "live.com", "me.com",

    # German
    "gmx.de", "web.de", "t-online.de", "freenet.de", "posteo.de", "outlook.de", "hotmail.de",

    # Global/European
    "yandex.ru", "zoho.com", "fastmail.com", "mail.ru", "bluewin.ch", "orange.fr"
]

# ========================
# 2️⃣ EMAIL CLEANING UTILITIES
# ========================

def normalize(email):
    """Normalize spacing and casing."""
    return email.strip().lower()

def correct_domain(email):
    """Correct domain typos with fuzzy matching."""
    if "@" not in email:
        return email, False
    local, domain = email.split("@", 1)

    # Remove unwanted spaces/dots
    domain = domain.replace("..", ".").strip(".")
    if domain not in COMMON_DOMAINS:
        closest = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.75)
        if closest:
            domain = closest[0]
            return f"{local}@{domain}", True
    return f"{local}@{domain}", False

def is_valid(email):
    """Basic regex validation."""
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email))

def clean_emails(raw_list):
    """Cleans, fixes, deduplicates, and sorts email addresses."""
    seen = set()
    cleaned = []
    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        e = normalize(raw)
        e, _ = correct_domain(e)
        e = e.replace("..", ".").replace("@@", "@")
        if not is_valid(e):
            continue
        if e not in seen:
            seen.add(e)
            cleaned.append(e)
    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    return cleaned

# ========================
# 3️⃣ TELEGRAM HANDLERS
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a .txt file or paste emails to clean!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    raw_emails = [line.strip() for line in text.split() if "@" in line]
    if not raw_emails:
        await update.message.reply_text("No emails found 😅")
        return
    cleaned = clean_emails(raw_emails)
    reply = "\n".join(cleaned) if cleaned else "No valid emails after cleaning."
    await update.message.reply_text(f"✅ Cleaned Emails:\n{reply}")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("uploaded.txt")
    with open("uploaded.txt", "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    cleaned = clean_emails(lines)
    with open("cleaned.txt", "w") as f:
        for e in cleaned:
            f.write(e + "\n")
    await update.message.reply_document(open("cleaned.txt", "rb"), caption="✅ Cleaned emails")

# ========================
# 4️⃣ APP INITIALIZATION (Render Safe)
# ========================

if __name__ == "__main__":
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot running on Render... Ready to clean emails!")

    loop = asyncio.get_event_loop()
    loop.create_task(app.run_polling())
    loop.run_forever()
