import os
import re
import asyncio
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ----------------------------
#  EMAIL CLEANER FUNCTION
# ----------------------------
def clean_emails(text: str) -> str:
    """
    Cleans a block of text containing emails:
    - Removes duplicates
    - Fixes dots before '@' (e.g., 'lucia.stark.@web.de' -> 'lucia.stark@web.de')
    - Keeps only valid email addresses
    - Sorts alphabetically
    """

    raw_emails = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    cleaned = []

    for email in raw_emails:
        email = re.sub(r"\.\@", "@", email)  # fix `.@`
        cleaned.append(email.lower())

    unique = sorted(set(cleaned))
    return "\n".join(unique)


# ----------------------------
#  TELEGRAM HANDLERS
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! Send me a list of emails (text or file), and I’ll clean it up for you."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    cleaned_text = clean_emails(raw_text)

    if not cleaned_text.strip():
        await update.message.reply_text("❌ No valid emails found in your message.")
        return

    with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    await update.message.reply_document(
        InputFile("cleaned_emails.txt"), caption="✅ Cleaned email list!"
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document:
        await update.message.reply_text("❌ Please send a valid text file.")
        return

    file = await document.get_file()
    file_path = "input.txt"
    await file.download_to_drive(file_path)

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_text = f.read()

    cleaned_text = clean_emails(raw_text)

    if not cleaned_text.strip():
        await update.message.reply_text("❌ No valid emails found in that file.")
        return

    with open("cleaned_emails.txt", "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    await update.message.reply_document(
        InputFile("cleaned_emails.txt"), caption="✅ Cleaned email list!"
    )


# ----------------------------
#  MAIN ENTRY POINT
# ----------------------------
async def main():
    print("🤖 Bot is running... Ready to clean emails!")

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN not set in environment variables!")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    await app.run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Fix for Python 3.12+/Render environment
        if "no current event loop" in str(e).lower():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main())
        else:
            raise
