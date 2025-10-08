import os
import re
import difflib
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
#                  EMAIL CLEANER FUNCTIONS
# ============================================================

COMMON_DOMAINS = {
    # US + Global
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "icloud.com", "aol.com", "comcast.net", "verizon.net",
    "msn.com", "live.com", "protonmail.com", "att.net",
    # German + EU
    "web.de", "gmx.de", "t-online.de", "freenet.de",
    "posteo.de", "online.de", "arcor.de", "email.de",
    "outlook.de", "hotmail.de", "me.com", "yandex.com",
    "gmx.net", "live.de", "protonmail.de", "tutanota.com",
}

def normalize(email: str) -> str:
    """Basic cleanup and normalization."""
    email = email.strip().lower()
    email = email.replace("..", ".").replace("@@", "@")
    email = re.sub(r'\s+', '', email)
    email = re.sub(r'\.{2,}', '.', email)
    email = re.sub(r'\s*@\s*', '@', email)
    return email

def correct_domain(email: str) -> tuple[str, bool]:
    """Fuzzy-correct domain typos to closest known domain."""
    if '@' not in email:
        return email, False
    user, domain = email.split('@', 1)
    domain = domain.strip().lower()

    # Auto-fix common TLD mistakes
    domain = re.sub(r'\.(con|cm|cpm|cim)$', '.com', domain)
    domain = re.sub(r'\.(deu)$', '.de', domain)
    domain = re.sub(r'\.(nett)$', '.net', domain)

    # Try fuzzy match
    match = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.85)
    if match:
        domain = match[0]
        return f"{user}@{domain}", True
    return f"{user}@{domain}", False

def is_valid(email: str) -> bool:
    """Validate general email structure."""
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email))

def clean_emails(raw_list):
    """Clean, normalize, and deduplicate emails."""
    seen = set()
    cleaned = []

    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        e = normalize(raw)
        e = re.sub(r'\.\s*@', '@', e)  # remove any dot before @
        e, _ = correct_domain(e)
        if not is_valid(e):
            continue
        if e not in seen:
            seen.add(e)
            cleaned.append(e)

    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    return cleaned

# ============================================================
#                      TELEGRAM BOT
# ============================================================

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

async def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("Missing TELEGRAM_TOKEN environment variable")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot is running... Ready to clean emails!")
    await app.run_polling()

# ============================================================
#                SAFE RENDER LOOP HANDLER (PY 3.13)
# ============================================================

if __name__ == "__main__":
    print("🚀 Starting bot...")
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(main())
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot stopped manually.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        try:
            loop.close()
        except Exception:
            pass
