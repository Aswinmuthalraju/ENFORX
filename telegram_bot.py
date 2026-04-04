"""
ENFORX Telegram Bot
Receives trade commands from an allowed user, passes them through run_pipeline(),
and replies with the result.

Usage:
    python3 telegram_bot.py

Prerequisites:
    TELEGRAM_BOT_TOKEN and ALLOWED_TELEGRAM_USER_ID must be set in .env
"""

from __future__ import annotations
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from main import run_pipeline
from logger_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

BOT_TOKEN          = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID    = int(os.getenv("ALLOWED_TELEGRAM_USER_ID", "0"))


def _format_result(result: dict) -> str:
    """Format pipeline result into a concise Telegram reply."""
    outcome = result.get("status") or result.get("outcome", "UNKNOWN")
    lines = [f"*ENFORX Pipeline Result*\n`{outcome}`\n"]

    if outcome == "SUCCESS":
        exec_r = result.get("execution_result", {})
        er_status = exec_r.get("status", "NO_TRADE")
        lines.append(f"Trade: `{er_status}`")
        if exec_r.get("order_id"):
            lines.append(f"Order ID: `{exec_r['order_id']}`")
        if exec_r.get("symbol"):
            lines.append(
                f"Symbol: {exec_r['symbol']} | Qty: {exec_r.get('qty')} | "
                f"Side: {exec_r.get('side')}"
            )
        lines.append(f"Audit: `{result.get('audit_entry_id', 'n/a')}`")
    else:
        details = result.get("details")
        if details:
            lines.append(f"Reason: {str(details)[:200]}")
        leader = result.get("leader_decision") or {}
        for reason in leader.get("reasons", []):
            lines.append(f"• {reason}")

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(
        "ENFORX pipeline ready.\n"
        "Send a trade command, e.g.:\n"
        "  Buy 1 share of AAPL\n"
        "  Sell 2 shares of MSFT"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != ALLOWED_USER_ID:
        logger.warning("Rejected message from unauthorized user %s", user.id)
        await update.message.reply_text("Unauthorized.")
        return

    text = update.message.text.strip()
    if not text:
        return

    logger.info("Telegram command from %s: %r", user.id, text)
    await update.message.reply_text("Processing through ENFORX pipeline...")

    try:
        result = run_pipeline(text)
        reply = _format_result(result)
    except Exception as exc:
        logger.exception("Pipeline error for Telegram command %r", text)
        reply = f"Pipeline error: {exc}"

    await update.message.reply_text(reply, parse_mode="Markdown")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    if not ALLOWED_USER_ID:
        raise RuntimeError("ALLOWED_TELEGRAM_USER_ID is not set in .env")

    logger.info("Starting ENFORX Telegram bot (allowed user: %s)", ALLOWED_USER_ID)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
