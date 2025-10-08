import os
import re
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# --------------------------
# Email Normalization Helpers
# --------------------------

def normalize(email):
    return email.strip().lower()

def is_valid(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

# --------------------------
# Known Domains & Auto-corrects
# --------------------------

KNOWN_DOMAINS = {
    # --- USA Common Domains ---
    "gmail.con": "gmail.com", "gmai.com": "gmail.com", "gmal.com": "gmail.com", "gnail.com": "gmail.com",
    "yahho.com": "yahoo.com", "yaho.com": "yahoo.com", "yhoo.com": "yahoo.com",
    "outlok.com": "outlook.com", "outllok.com": "outlook.com",
    "hotmail.con": "hotmail.com", "hotmal.com": "hotmail.com", "hotmial.com": "hotmail.com",
    "icloud.con": "icloud.com", "iclod.com": "icloud.com", "iclud.com": "icloud.com",
    "aol.con": "aol.com", "ao.com": "aol.com",
    "comcast.con": "comcast.com", "comast.com": "comcast.com",
    "att.con": "att.com", "att.net": "att.net",
    "verizon.con": "verizon.com", "verzon.com": "verizon.com",
    "proton.con": "protonmail.com", "protonmail.con": "protonmail.com",
    "live.con": "live.com", "liv.com": "live.com",
    "msn.con": "msn.com", "ms.con": "msn.com",

    # --- German Common Domains ---
    "web.dee": "web.de", "wb.de": "web.de",
    "gmx.dee": "gmx.de", "gmx.d": "gmx.de",
    "t-online.dee": "t-online.de", "tonline.de": "t-online.de",
    "freenet.dee": "freenet.de", "freenett.de": "freenet.de",
    "posteo.dee": "posteo.de", "postoo.de": "posteo.de",
    "mail.dee": "mail.de", "email.dee": "email.de",
    "outlook.dee": "outlook.de",
    "yahoo.dee": "yahoo.de",
    "icloud.dee": "icloud.de",
}

def correct_domain(email):
    try:
        local, domain = email.split("@")
        domain = KNOWN_DOMAINS.get(domain, domain)
        return f"{local}@{domain}", domain
    except Exception:
        return email, None

# --------------------------
# Email Cleaning Function
# --------------------------

async def clean_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    raw_list = re.split(r'[, \n]+', text)

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

    if cleaned:
        await update.message.reply_text("\n".join(cleaned))
    else:
        await update.message.reply_text("❌ No valid emails found.")

# --------------------------
# File Upload Handler
# --------------------------

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("uploaded.txt")

    with open("uploaded.txt", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    seen = set()
    cleaned = []

    for raw in lines:
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

    with open("cleaned.txt", "w", encoding="utf-8") as f:
        for e in cleaned:
            f.write(e + "\n")

    await update.message.reply_document(open("cleaned.txt", "rb"), caption="✅ Cleaned emails")

# --------------------------
# Start Command
# --------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a .txt file or paste emails directly to clean duplicates, typos, and invalid addresses.\n\n"
        "Supports 🇺🇸 USA and 🇩🇪 German domains."
    )

# --------------------------
# Main Entrypoint
# --------------------------

async def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ Missing TELEGRAM_TOKEN environment variable.")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, clean_emails))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot running on Render... Ready to clean emails!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
