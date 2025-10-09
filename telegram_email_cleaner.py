#!/usr/bin/env python3
"""
Telegram Email Cleaner Bot
- Paste emails or upload .txt/.csv/.xlsx
- Cleans, fuzzy-corrects domains (US+DE+common), dedupes, sorts
- Returns cleaned file + summary
- Includes logging and robust asyncio loop for Render
"""

import os
import re
import csv
import time
import difflib
import logging
import asyncio
from io import StringIO, BytesIO
from typing import List, Tuple, Dict

# Networking + Telegram
from aiohttp import web
from telegram import Update, InputFile
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
# Domain list (expanded)
# -----------------------
COMMON_DOMAINS = [
    # Major US/global
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "comcast.net", "verizon.net", "msn.com", "live.com",
    "protonmail.com", "proton.me", "zoho.com", "fastmail.com", "mail.com",
    "gmx.com", "mail.ru", "yandex.com", "yandex.ru", "hotmail.co.uk", "hotmail.de",
    # German / EU
    "web.de", "gmx.de", "t-online.de", "freenet.de", "posteo.de",
    "online.de", "arcor.de", "email.de", "outlook.de", "hotmail.de",
    "gmx.net", "posteo.eu", "tutanota.com",
    # Other common
    "orange.fr", "btinternet.com", "virginmedia.com", "shaw.ca", "ntlworld.com",
    "cox.net", "att.net", "bellsouth.net", "sbcglobal.net"
]
# keep a set for quick membership tests
COMMON_DOMAINS_SET = set(COMMON_DOMAINS)

# -----------------------
# Normalization & validation
# -----------------------
LOCAL_ALLOWED_RE = re.compile(r"[a-z0-9._%+\-]")
EMAIL_VALID_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.-]+\.[a-z]{2,}$")

def normalize_local_part(local: str) -> str:
    """Normalize local part: replace spaces with dots, collapse multiple dots, remove leading/trailing dot"""
    local = local.strip().lower()
    local = re.sub(r"\s+", ".", local)           # spaces -> dots
    local = re.sub(r"\.{2,}", ".", local)        # collapse dots
    local = re.sub(r"^\.", "", local)            # leading dot
    local = re.sub(r"\.$", "", local)            # trailing dot
    # remove invalid characters (keep common ones)
    local = re.sub(r"[^a-z0-9._%+\-]", "", local)
    return local

def normalize_domain_part(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.replace("..", ".")
    domain = re.sub(r"[^\w\.\-]", "", domain)
    # fix common tld typos
    domain = re.sub(r"\.(con|cim|cm|c0m)$", ".com", domain)
    domain = re.sub(r"\.(deu|d)$", ".de", domain)
    return domain

def fuzzy_correct_domain(domain: str) -> Tuple[str, bool]:
    """Return corrected domain and whether we corrected it"""
    domain = normalize_domain_part(domain)
    if domain in COMMON_DOMAINS_SET:
        return domain, False
    # try exact common replacements quickly
    replacements = {
        "gamil.com": "gmail.com",
        "gmial.com": "gmail.com",
        "gmaill.com": "gmail.com",
        "outlok.com": "outlook.com",
        "outllok.com": "outlook.com",
        "yahho.com": "yahoo.com",
        "webd.de": "web.de",
        "gmxde": "gmx.de",
    }
    if domain in replacements:
        return replacements[domain], True
    # fuzzy match
    match = difflib.get_close_matches(domain, COMMON_DOMAINS, n=1, cutoff=0.75)
    if match:
        return match[0], True
    return domain, False

def clean_single_email(raw: str) -> Tuple[str, str]:
    """
    Clean one raw email-like string.
    Returns (clean_email, reason) where reason is '' if valid, otherwise a short reason.
    """
    original = raw
    s = raw.strip().lower()
    # remove surrounding quotes
    s = s.strip('\'"')
    # remove illegal invisible chars
    s = re.sub(r"[\r\n\t]", "", s)
    # remove illegal characters except standard email ones
    s = re.sub(r"[^\w@.\-+% ]", "", s)
    # remove spaces directly around @ and dots etc
    s = re.sub(r"\s*@\s*", "@", s)
    s = re.sub(r"\s*\.\s*", ".", s)
    # collapse multiple dots
    s = re.sub(r"\.{2,}", ".", s)
    # remove dot before @ (the main complaint)
    s = re.sub(r"\.+@", "@", s)
    # if missing @, can't clean reliably
    if "@" not in s:
        return "", "no_at"
    local, domain = s.split("@", 1)
    local = normalize_local_part(local)
    domain = normalize_domain_part(domain)
    domain, corrected = fuzzy_correct_domain(domain)
    candidate = f"{local}@{domain}"
    if not EMAIL_VALID_RE.match(candidate):
        return "", "invalid_format"
    return candidate, ""


# -----------------------
# Bulk cleaning
# -----------------------
def extract_emails_from_text(text: str) -> List[str]:
    # find sequences that look like emails (loose)
    found = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{1,}", text)
    return found

def clean_email_list(items: List[str]) -> Dict:
    """
    items: list of strings (lines, or raw tokens)
    Returns a dict with keys: cleaned(list), removed(list), summary(dict)
    """
    start = time.time()
    seen = set()
    cleaned = []
    removed = []
    duplicates = 0
    total_input = 0

    for raw in items:
        if not raw or not isinstance(raw, str):
            continue
        # some lines may contain multiple emails separated by commas/tabs/spaces
        parts = re.split(r"[,\t;|]+", raw)
        for p in parts:
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
    summary = {
        "total_input": total_input,
        "kept": len(cleaned),
        "removed": len(removed),
        "duplicates": duplicates,
        "time_seconds": round(elapsed, 3),
    }
    return {"cleaned": cleaned, "removed": removed, "summary": summary}


# -----------------------
# File reading helpers: txt, csv, xlsx
# -----------------------
def read_txt(content: str) -> List[str]:
    return [line.strip() for line in content.splitlines() if line.strip()]

def read_csv(content: str) -> List[str]:
    out = []
    f = StringIO(content)
    try:
        reader = csv.reader(f)
        for row in reader:
            # look for any cell that looks like an email or contains @
            for cell in row:
                if "@" in cell:
                    out.append(cell.strip())
    except Exception:
        # fallback: split by whitespace
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
                if not cell:
                    continue
                cell_str = str(cell)
                if "@" in cell_str:
                    out.append(cell_str.strip())
    return out

# -----------------------
# Telegram handlers
# -----------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me emails (paste) or upload a .txt / .csv / .xlsx file. I'll clean, fix domains, dedupe and return a cleaned file + summary."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    logger.info(f"Received text from {update.effective_user.id}: {len(text)} chars")
    items = [line.strip() for line in re.split(r'[\r\n]+', text) if line.strip()]
    if len(items) == 1:
        # maybe many emails on one line
        items = re.split(r'[,\s;|]+', items[0])
    result = clean_email_list(items)
    await send_results(update, result)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # supports .txt, .csv, .xlsx
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Please upload a file (.txt, .csv, .xlsx)")
        return
    filename = doc.file_name.lower()
    logger.info(f"User {update.effective_user.id} uploaded file: {filename}")
    file = await doc.get_file()
    data = await file.download_as_bytearray()
    text_items = []
    try:
        if filename.endswith(".txt"):
            content = data.decode("utf-8", errors="ignore")
            text_items = read_txt(content)
        elif filename.endswith(".csv"):
            content = data.decode("utf-8", errors="ignore")
            text_items = read_csv(content)
        elif filename.endswith(".xlsx") or filename.endswith(".xlsm") or filename.endswith(".xltx"):
            text_items = read_xlsx_bytes(bytes(data))
        else:
            # fallback: try txt parsing
            content = data.decode("utf-8", errors="ignore")
            text_items = read_txt(content)
    except Exception as e:
        logger.exception("Error reading uploaded file")
        await update.message.reply_text(f"Failed to read file: {e}")
        return

    result = clean_email_list(text_items)
    await send_results(update, result)

async def send_results(update: Update, result: Dict):
    cleaned = result["cleaned"]
    removed = result["removed"]
    summary = result["summary"]

    # Build summary text
    summary_lines = [
        f"✅ Clean complete",
        f"• Total input tokens scanned: {summary['total_input']}",
        f"• Kept: {summary['kept']}",
        f"• Removed (invalid): {summary['removed']}",
        f"• Duplicates removed: {summary['duplicates']}",
        f"• Time: {summary['time_seconds']}s",
    ]
    summary_text = "\n".join(summary_lines)

    if not cleaned:
        await update.message.reply_text(summary_text + "\n\nNo valid emails found.")
        return

    # If result is small, send inline; otherwise send as file
    out_text = "\n".join(cleaned)
    if len(out_text) <= 3800:  # safe margin under Telegram 4096 limit
        await update.message.reply_text(summary_text + "\n\n" + out_text)
    else:
        # write to file and send
        with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
            f.write(out_text)
        await update.message.reply_document(InputFile("cleaned_emails.txt"), caption=summary_text)

# -----------------------
# Health web server (keeps Render happy)
# -----------------------
async def health(request):
    return web.Response(text="OK - bot alive")

async def start_health_server(port: int = None):
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = port or int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server listening on port {port}")

# -----------------------
# Entrypoint
# -----------------------
async def main():
    # Accept multiple env var names to avoid token name mismatches
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN (or BOT_TOKEN/TELEGRAM_TOKEN) not set in environment")
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN env var")

    # Start health server
    await start_health_server()

    # Build app
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Starting Telegram polling...")
    # Run the Telegram app's polling; don't close loop when done
    await app.run_polling(close_loop=False)

# Run with robust loop handling
if __name__ == "__main__":
    try:
        # Create a fresh loop and run main (safe for Python 3.13)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except Exception:
        logger.exception("Fatal error in bot main")
    finally:
        try:
            loop.stop()
        except Exception:
            pass
