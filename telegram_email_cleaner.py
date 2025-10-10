import os
import re
import csv
import time
import difflib
import logging
import asyncio
from io import StringIO, BytesIO
from typing import List, Tuple, Dict
import sys

# Networking + Telegram
from aiohttp import web
from telegram import Update, InputFile
import nest_asyncio
nest_asyncio.apply()
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Excel support
try:
    import openpyxl
except Exception:
    openpyxl = None

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger("email-cleaner-bot")

# -----------------------
# Common Email Domains + Known Typos
# -----------------------
COMMON_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "comcast.net", "verizon.net", "msn.com", "live.com",
    "protonmail.com", "proton.me", "zoho.com", "fastmail.com", "mail.com",
    "gmx.com", "mail.ru", "yandex.com", "yandex.ru", "hotmail.co.uk", "hotmail.de",
    "web.de", "gmx.de", "t-online.de", "freenet.de", "posteo.de",
    "online.de", "arcor.de", "email.de", "outlook.de", "gmx.net",
    "posteo.eu", "tutanota.com",
]

COMMON_DOMAIN_TYPOS = {
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gmaiil.com": "gmail.com",
    "gmaul.com": "gmail.com",
    "gmai.co": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.comm": "gmail.com",
    "hotnail.com": "hotmail.com",
    "hotmial.com": "hotmail.com",
    "hotmil.com": "hotmail.com",
    "yaho.com": "yahoo.com",
    "yahho.com": "yahoo.com",
    "yaoo.com": "yahoo.com",
    "yhoo.com": "yahoo.com",
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
    "outloook.com": "outlook.com",
    "iclod.com": "icloud.com",
    "iclud.com": "icloud.com",
    "protonmaill.com": "protonmail.com",
    "webd.de": "web.de",
    "gmxde": "gmx.de",
    "gmx.deu": "gmx.de",
    "t-onlin.de": "t-online.de",
    "t-online.cmo": "t-online.de",
}

COMMON_DOMAINS_SET = set(COMMON_DOMAINS)

# -----------------------
# Email Validation and Cleaning Functions
# -----------------------
EMAIL_VALID_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.-]+\.[a-z]{2,}$")

def normalize_local_part(local: str) -> str:
    local = local.strip().lower()
    local = re.sub(r"\s+", ".", local)
    local = re.sub(r"\.{2,}", ".", local)
    local = re.sub(r"^\.", "", local)
    local = re.sub(r"\.$", "", local)
    local = re.sub(r"[^a-z0-9._%+\-]", "", local)
    return local

def normalize_domain_part(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.replace("..", ".")
    domain = re.sub(r"[^\w.\-]", "", domain)
    domain = re.sub(r"\.(con|cim|cm|c0m)$", ".com", domain)
    domain = re.sub(r"\.(deu|d)$", ".de", domain)
    return domain

def fuzzy_correct_domain(domain: str) -> Tuple[str, bool]:
    domain = normalize_domain_part(domain)
    if domain in COMMON_DOMAIN_TYPOS:
        return COMMON_DOMAIN_TYPOS[domain], True
    if domain in COMMON_DOMAINS_SET:
        return domain, False
    match = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.75)
    if match:
        return match[0], True
    return domain, False

def clean_single_email(raw: str) -> Tuple[str, str]:
    s = raw.strip().lower()
    s = s.strip('\'"')
    s = re.sub(r"[\r\n\t]", "", s)
    s = re.sub(r"[^\w@.\-+% ]", "", s)
    s = re.sub(r"\s*@\s*", "@", s)
    s = re.sub(r"\s*\.\s*", ".", s)
    s = re.sub(r"\.{2,}", ".", s)
    s = re.sub(r"\.+@", "@", s)
    if "@" not in s:
        return "", "no_at"
    local, domain = s.split("@", 1)
    local = normalize_local_part(local)
    domain = normalize_domain_part(domain)
    domain, _ = fuzzy_correct_domain(domain)
    candidate = f"{local}@{domain}"
    if not EMAIL_VALID_RE.match(candidate):
        return "", "invalid_format"
    return candidate, ""

def clean_email_list(items: List[str]) -> Dict:
    start = time.time()
    seen, cleaned, removed = set(), [], []
    duplicates, total_input = 0, 0

    for raw in items:
        if not raw or not isinstance(raw, str):
            continue
        for p in re.split(r"[,\t;|]+", raw):
            candidate = p.strip()
            if not candidate:
                continue
            total_input += 1
            cleaned_candidate, reason = clean_single_email(candidate)
            if not cleaned_candidate:
                removed.append((candidate, reason))
                continue
            if cleaned_candidate in seen:
                duplicates += 1
                continue
            seen.add(cleaned_candidate)
            cleaned.append(cleaned_candidate)

    cleaned.sort(key=lambda x: (x.split("@")[1], x.split("@")[0]))
    elapsed = time.time() - start
    return {
        "cleaned": cleaned,
        "removed": removed,
        "summary": {
            "total_input": total_input,
            "kept": len(cleaned),
            "removed": len(removed),
            "duplicates": duplicates,
            "time_seconds": round(elapsed, 3),
        },
    }

# -----------------------
# File Handlers
# -----------------------
def read_txt(content: str) -> List[str]:
    return [line.strip() for line in content.splitlines() if line.strip()]

def read_csv(content: str) -> List[str]:
    out = []
    f = StringIO(content)
    try:
        reader = csv.reader(f)
        for row in reader:
            for cell in row:
                if "@" in cell:
                    out.append(cell.strip())
    except Exception:
        out.extend(re.split(r'[\s,;]+', content))
    return out

def read_xlsx_bytes(data: bytes) -> List[str]:
    if openpyxl is None:
        raise RuntimeError("openpyxl not installed")
    wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    out = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for cell in row:
                if cell and "@" in str(cell):
                    out.append(str(cell).strip())
    return out

# -----------------------
# Telegram Handlers
# -----------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me emails (paste) or upload a .txt / .csv / .xlsx file.\n"
        "I'll clean, fix domains, dedupe and return a cleaned file + summary."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    items = [x.strip() for x in re.split(r'[\r\n]+', text) if x.strip()]
    if len(items) == 1:
        items = re.split(r'[,\s;|]+', items[0])
    result = clean_email_list(items)
    await send_results(update, result)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Please upload a file (.txt, .csv, .xlsx)")
        return
    filename = doc.file_name.lower()
    file = await doc.get_file()
    data = await file.download_as_bytearray()

    text_items = []
    try:
        if filename.endswith('.txt'):
            text_items = read_txt(data.decode())
        elif filename.endswith('.csv'):
            text_items = read_csv(data.decode())
        elif filename.endswith('.xlsx'):
            text_items = read_xlsx_bytes(data)
        else:
            await update.message.reply_text("File format not supported. Please upload .txt, .csv, or .xlsx.")
            return
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        await update.message.reply_text("There was an error processing the file. Please try again.")
        return

    result = clean_email_list(text_items)
    await send_results(update, result)

async def send_results(update: Update, result: Dict):
    cleaned_emails = result["cleaned"]
    summary = result["summary"]
    if len(cleaned_emails) == 0:
        await update.message.reply_text("No valid emails found.")
        return

    # Prepare the cleaned emails in a text file
    cleaned_txt = "\n".join(cleaned_emails)
    with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
        f.write(cleaned_txt)

    # Send the file
    with open("cleaned_emails.txt", "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="cleaned_emails.txt",
            caption=f"Cleaned emails - {summary['kept']} valid emails out of {summary['total_input']}.",
        )

    # Optionally remove the file after sending it
    os.remove("cleaned_emails.txt")

# -----------------------
# Start Telegram Bot
# -----------------------
async def main():
    # Read token from environment to avoid committing secrets in source.
    # Support multiple environment variable names for convenience.
    token = os.getenv("BOT_API_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    if not token or token == "YOUR_BOT_API_TOKEN":
        logger.error("Bot token environment variable is not set. Set BOT_API_TOKEN or TELEGRAM_BOT_TOKEN and restart the bot.")
        print("Error: bot token environment variable is not set.\nSet it like: export TELEGRAM_BOT_TOKEN='<your-token>'\nThen run: python3 telegram_email_cleaner.py")
        return

    # Do not log the token value to avoid accidental leaks
    application = ApplicationBuilder().token(token).build()

    # Handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(MessageHandler(filters.TEXT, handle_text))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Start a tiny web server so Render can use a Web service (health checks / port binding).
    port = int(os.getenv("PORT", "10000"))
    app = web.Application()

    async def health(request):
        return web.Response(text="OK")

    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server started on port {port}")

    try:
        # Run the bot (polling) — the web server runs concurrently and keeps Render happy.
        await application.run_polling()
    finally:
        # Clean up web server on shutdown
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
