import os
import re
import asyncio
import difflib
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_TOKEN")

# === Trusted / Common Domains ===
COMMON_DOMAINS = [
    # 🇺🇸 U.S. providers
    "gmail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "yahoo.com", "ymail.com", "rocketmail.com", "aol.com", "comcast.net",
    "verizon.net", "att.net", "sbcglobal.net", "bellsouth.net", "icloud.com",
    "me.com", "mac.com", "fastmail.com", "zoho.com", "zohomail.com",
    "protonmail.com", "proton.me", "mail.com", "usa.com",
    "cox.net", "charter.net", "frontier.com", "earthlink.net",

    # 🇩🇪 German providers
    "gmx.de", "gmx.net", "web.de", "t-online.de", "freenet.de",
    "posteo.de", "mail.de", "online.de", "1und1.de", "outlook.de",
    "hotmail.de", "live.de", "yahoo.de", "vodafone.de", "arcor.de",
    "unitybox.de", "kabelmail.de", "ewetel.net",

    # 🌍 International / Secure
    "protonmail.ch", "pm.me", "tuta.io", "tutanota.com", "yandex.com", "yandex.ru",
    "zoho.eu", "icloud.com", "mail.ru", "inbox.ru", "bk.ru"
]

# === Email Normalization ===
def normalize(email):
    return email.strip().lower()

# === Smart Domain Correction using fuzzy matching ===
def correct_domain(email):
    if "@" not in email:
        return email, False

    user, domain = email.split("@", 1)
    domain = domain.strip().lower()

    # If it's already valid, return as is
    if domain in COMMON_DOMAINS:
        return f"{user}@{domain}", False

    # Try fuzzy match
    match = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.75)
    if match:
        return f"{user}@{match[0]}", True

    return f"{user}@{domain}", False

# === Email Validation ===
def is_valid(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

# === Main Cleaning Function ===
def clean_email_list(raw_list):
    seen = set()
    cleaned = []
    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        e = normalize(raw)
        e = e.replace("..", ".").replace("@@", "@")

        if "@" not in e:
            continue

        e, corrected = correct_domain(e)
        if not is_valid(e):
            continue

        if e not in seen:
            seen.add(e)
            cleaned.append(e)

    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    return cleaned

# === Telegram Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a list of emails or upload a .txt file — I’ll clean and fix them for you!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    raw_emails = re.split(r'[, \n]+', text)
    cleaned = clean_email_list(raw_emails)
    if cleaned:
        await update.message.reply_text("✅ Cleaned Emails:\n" + "\n".join(cleaned))
    else:
        await update.message.reply_text("❌ No valid emails found.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("uploaded.txt")
    with open("uploaded.txt", "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    cleaned = clean_email_list(lines)
    with open("cleaned.txt", "w") as f:
        for e in cleaned:
            f.write(e + "\n")
    await update.message.reply_document(open("cleaned.txt", "rb"), caption="✅ Cleaned emails")

# === Main Bot App ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🤖 Bot running on Render... Ready to clean emails!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
