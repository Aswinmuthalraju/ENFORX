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
import asyncio
import logging
import os
import sys
import re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent / "core" / "src"))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from main import run_pipeline
from logger_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

BOT_TOKEN          = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID    = int(os.getenv("ALLOWED_TELEGRAM_USER_ID", "0"))


def _format_result(result: dict) -> str:
    """Format pipeline result into a rich Telegram reply with icons and detailed reasoning."""
    outcome = result.get("status") or result.get("outcome", "UNKNOWN")
    
    if "BLOCK" in str(outcome).upper() or "ERROR" in str(outcome).upper():
        icon = "🚫"
    elif outcome == "SUCCESS":
        icon = "✅"
    else:
        icon = "⚠️"

    lines = [f"{icon} *ENFORX Pipeline Result*", f"`{outcome}`", ""]

    if outcome == "SUCCESS":
        exec_r = result.get("execution_result", {})
        er_status = exec_r.get("status", "NO_TRADE")
        lines.append(f"Trade Status: `{er_status}`")
        if exec_r.get("order_id"):
            lines.append(f"Order ID: `{exec_r['order_id']}`")
        if exec_r.get("symbol"):
            lines.append(f"Symbol: `{exec_r['symbol']}`")
            lines.append(f"Qty: `{exec_r.get('qty')}` | Side: `{exec_r.get('side')}`")
        lines.append(f"Audit ID: `{result.get('audit_entry_id', 'n/a')}`")
    else:
        blocked_at = result.get("blocked_at") or ""
        if blocked_at:
            lines.append(f"🔒 Blocked at: `{blocked_at}`")

        details = result.get("details") or ""
        if details:
            if isinstance(details, list):
                for d in details:
                    lines.append(f"• {str(d)[:300]}")
            else:
                lines.append(f"Reason: {str(details)[:500]}")

        leader = result.get("leader_decision") or {}
        for reason in leader.get("reasons", []):
            lines.append(f"• {reason}")

        # Ticker validation message
        sid = result.get("sid") or {}
        scope = sid.get("scope") or {}
        tickers = scope.get("tickers") or []
        allowed = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ", "VOO", "IVV"]
        if tickers and not any(t in allowed for t in tickers):
            lines.append(f"\nℹ️ Ticker `{tickers}` is not allowed.")
            lines.append(f"Allowed: `AAPL, TSLA, NVDA, SPY, QQQ, VOO, IVV`")
        
        qty = scope.get("max_quantity") or 0
        if qty >= 10:
            lines.append(f"\n⚠️ Quantity must be below 10. You requested `{qty}` shares. Maximum is 9.")

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(
        "🛡 ENFORX Trading Bot Initialized.\n\n"
        "Send a trade command to process it through the 10-layer safety pipeline.\n"
        "Example: `Buy 1 share of AAPL`"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    help_text = (
        "ENFORX Trading Bot Commands:\n"
        "/start — Initialize the bot\n"
        "/status — Check system health\n"
        "/help — Show this help\n\n"
        "Trade Commands:\n"
        "• Buy N shares of TICKER\n"
        "• Sell N shares of TICKER\n\n"
        "Allowed tickers: `AAPL (Apple Inc.), TSLA (Tesla Inc.), NVDA (NVIDIA Corp), "
        "SPY (SPDR S&P 500 ETF Trust), QQQ (Invesco QQQ Trust), "
        "VOO (Vanguard S&P 500 ETF), IVV (iShares Core S&P 500 ETF)`.\n"
        "Maximum quantity: 9 shares per order (must be below 10)."
    )
    await update.message.reply_text(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    
    status_msg = "🔍 *ENFORX System Health*\n\n"
    
    # Ollama
    try:
        from llm_client import OpenClawClient
        client = OpenClawClient()
        status_msg += f"• Ollama (LLM): `{'CONNECTED' if client.is_available() else 'OFFLINE'}`\n"
    except Exception:
        status_msg += "• Ollama (LLM): `ERROR`\n"

    # Alpaca
    try:
        from alpaca_client import AlpacaClient
        ac = AlpacaClient()
        if ac._api:
            acc = ac.get_account()
            status_msg += f"• Alpaca Paper: `CONNECTED` (Cash: `${acc.get('cash', '?')}`)\n"
        else:
            status_msg += "• Alpaca Paper: `NOT CONFIGURED`\n"
    except Exception:
        status_msg += "• Alpaca Paper: `OFFLINE`\n"

    # Policy
    policy_path = Path(__file__).parent.parent / "core" / "enforx-policy.json"
    status_msg += f"• Policy File: `{'FOUND' if policy_path.exists() else 'MISSING'}`\n"
    
    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != ALLOWED_USER_ID:
        logger.warning("Rejected message from unauthorized user %s", user.id)
        await update.message.reply_text("Unauthorized.")
        return

    text = update.message.text.strip()
    if not text:
        return

    # Basic input validation
    if not re.search(r"\b(buy|sell)\b", text.lower()):
        await update.message.reply_text("⚠️ Please send a trade command. Example: `Buy 2 shares of AAPL`")
        return

    logger.info("Telegram command from %s: %r", user.id, text)
    await update.message.reply_text("⏳ Processing through ENFORX pipeline...")

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_pipeline, text)
        try:
            reply = _format_result(result)
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception as fmt_exc:
            logger.exception("Formatting error")
            await update.message.reply_text(f"Result (raw): `{str(result)[:500]}`")
    except Exception as exc:
        logger.exception("Pipeline error for Telegram command %r", text)
        await update.message.reply_text(f"Pipeline error: `{type(exc).__name__}: {str(exc)[:300]}`")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    if not ALLOWED_USER_ID:
        raise RuntimeError("ALLOWED_TELEGRAM_USER_ID is not set in .env")

    logger.info("Starting ENFORX Telegram bot (allowed user: %s)", ALLOWED_USER_ID)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
