import os
import re
import difflib
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# === Common domain list (USA + German + global popular) ===
COMMON_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com",
    "comcast.net", "verizon.net", "mail.com", "live.com", "msn.com", "att.net",
    "protonmail.com", "zoho.com", "gmx.com", "gmx.de", "web.de", "t-online.de",
    "posteo.de", "freenet.de", "yandex.com", "yandex.ru", "mail.ru", "fastmail.com"
}

# === Email utilities ===
def normalize(email: str) -> str:
    """Normalize and lowercase emails."""
    return email.strip().lower()

def correct_domain(email: str) -> tuple[str, bool]:
    """Fuzzy-match domain corrections."""
    if "@" not in email:
        return email, False
    name, domain = email.split("@", 1)
    domain = domain.strip()

    # Fix common typos
    if domain.endswith(".con"):
        domain = domain[:-4] + ".com"
    elif domain.endswith(".cim"):
        domain = domain[:-4] + ".com"
    elif domain.endswith(".coo"):
        domain = domain[:-4] + ".com"

    # Suggest closest known domain if it's off
    match = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.7)
    if match:
        return f"{name}@{match[0]}", True
    return f"{name}@{domain}", False

def is_valid(email: str) -> bool:
    """Validate cleaned emails."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def clean_emails(raw_list):
    """Clean a list of emails."""
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

# === MAIN ===
if __name__ == "__main__":
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not set. Please add it in Render environment variables.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot running on Render... Ready to clean emails!")

    # Start bot safely (no asyncio.run() loop conflict)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.run_polling())
