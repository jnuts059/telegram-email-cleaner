import os
import re
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_TOKEN")

# === Email Normalization & Validation ===
def normalize(email):
    return email.strip().lower()

def correct_domain(email):
    known_domains = {
        "gamil.com": "gmail.com",
        "gmial.com": "gmail.com",
        "outllok.com": "outlook.com",
        "hotnail.com": "hotmail.com",
        "yahho.com": "yahoo.com",
        "ymial.com": "ymail.com",
    }
    parts = email.split("@")
    if len(parts) == 2:
        user, domain = parts
        if domain in known_domains:
            return f"{user}@{known_domains[domain]}", True
    return email, False

def is_valid(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

# === Core Cleaning Function ===
def clean_email_list(raw_list):
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

# === Telegram Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a .txt file or paste emails to clean!")

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

# === Main Bot Setup ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🤖 Bot running on Render...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
