from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import os
import re
from difflib import get_close_matches

# === TELEGRAM TOKEN ===
TOKEN = os.getenv("TELEGRAM_TOKEN")

# === EMAIL CLEANER LOGIC ===
COMMON_DOMAINS = [
    "gmail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
    "icloud.com", "aol.com", "protonmail.com", "zoho.com", "live.com",
    "msn.com", "example.com", "gmx.com", "yandex.com", "me.com"
]
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

DEOBF_PATTERNS = [
    (r"\s*\(?\s*at\s*\)?\s*", "@"),
    (r"\s*\(?\s*dot\s*\)?\s*", "."),
    (r"\s*\[at\]\s*", "@"),
    (r"\s*\[dot\]\s*", "."),
    (r"\s*\(?\s*where\s*\)?\s*", "@"),
    (r"\s+@\s+", "@"),
]

def deobfuscate(s: str) -> str:
    s = s.strip().lower()
    for pat, repl in DEOBF_PATTERNS:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    return s

def normalize(email: str) -> str:
    email = deobfuscate(email)
    email = email.strip("<>\"' ,;:!()[]")
    email = re.sub(r"@{2,}", "@", email)
    email = re.sub(r"\.{2,}", ".", email)
    email = re.sub(r"\s*@\s*", "@", email)
    email = re.sub(r"\s+", "", email)
    if "@" in email:
        local, domain = email.split("@", 1)
        local = local.strip(".")
        email = f"{local}@{domain}"
    return email

def correct_domain(email: str) -> tuple[str, bool]:
    if "@" not in email:
        return email, False
    local, domain = email.split("@", 1)
    domain = domain.strip(". ")
    if "." not in domain:
        guess = domain + ".com"
        if guess in COMMON_DOMAINS:
            return f"{local}@{guess}", True
    match = get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.7)
    if match:
        corrected = f"{local}@{match[0]}"
        return corrected, match[0] != domain
    return f"{local}@{domain}", False

def is_valid(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))

def clean_emails(raw_list):
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

# === TELEGRAM BOT ===
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
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🤖 Bot running on Render...")
    await app.run_polling()

import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(application.run_polling())
    except RuntimeError:
        # Fix for "Cannot close a running event loop"
        loop = asyncio.get_event_loop()
        loop.run_until_complete(application.run_polling())