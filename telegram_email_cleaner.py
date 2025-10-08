import os
import re
import asyncio
from difflib import get_close_matches
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- DOMAIN LISTS (Germany + USA + Common) ---
KNOWN_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com",
    "icloud.com", "live.com", "msn.com", "comcast.net", "protonmail.com",
    "yandex.ru", "mail.com", "gmx.de", "web.de", "t-online.de", "freenet.de",
    "posteo.de", "arcor.de", "online.de", "me.com", "mac.com", "gmx.net",
    "verizon.net", "earthlink.net", "bellsouth.net", "cox.net", "att.net"
]

# --- CLEANING HELPERS ---
def normalize(email: str) -> str:
    return email.strip().lower()

def is_valid(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def correct_domain(email: str):
    if "@" not in email:
        return email, False
    local, domain = email.split("@", 1)
    domain = domain.replace("..", ".").replace("@@", "@").strip(".")
    match = get_close_matches(domain, KNOWN_DOMAINS, n=1, cutoff=0.75)
    if match:
        return f"{local}@{match[0]}", True
    return f"{local}@{domain}", False

def clean_emails_list(raw_list):
    seen = set()
    cleaned = []
    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        e = normalize(raw)
        e, _ = correct_domain(e)
        e = e.replace("..", ".").replace("@@", "@").strip()
        if not is_valid(e):
            continue
        if e not in seen:
            seen.add(e)
            cleaned.append(e)
    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    return cleaned

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me your email list, and I’ll clean and fix them for you!")

async def handle_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    emails = re.findall(r"[^\s,;]+@[^\s,;]+", text)
    if not emails:
        await update.message.reply_text("⚠️ No valid emails found in your message.")
        return
    cleaned = clean_emails_list(emails)
    if not cleaned:
        await update.message.reply_text("❌ No valid emails after cleaning.")
    else:
        result = "\n".join(cleaned)
        await update.message.reply_text(f"✅ Cleaned Emails ({len(cleaned)}):\n\n{result}")

# --- MAIN FUNCTION ---
async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set in environment variables.")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emails))

    print("🤖 Bot is running... (Render background worker)")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()  # Keeps bot alive

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        print(f"⚠️ Runtime error: {e}")
