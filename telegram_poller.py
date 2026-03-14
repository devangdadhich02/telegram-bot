"""
Background thread that polls Telegram for updates.
When a user sends /start, adds them to subscribers and sends a welcome message.
When they send /stop, removes them and sends goodbye.
"""

import logging
import threading
import time
from typing import Any, Dict, List

import requests

import config
from subscribed_chats import add_subscriber, remove_subscriber

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

WELCOME_MESSAGE = (
    "👋 Welcome!\n\n"
    "You're subscribed to trading signals. You'll receive RSI, MACD, and liquidation alerts here when conditions are met.\n\n"
    "Send /stop to unsubscribe from signals."
)

GOODBYE_MESSAGE = "You've been unsubscribed. Send /start anytime to receive signals again."

REPLY_WHEN_SUBSCRIBED = (
    "✅ You're subscribed. Trading signals (RSI, MACD, liquidation) will appear here automatically when conditions are met.\n\n"
    "Send /stop to unsubscribe."
)
REPLY_WHEN_NOT_SUBSCRIBED = "Send /start to subscribe and receive trading signals here."


def _send_message(chat_id: int, text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        return r.status_code == 200
    except requests.RequestException as e:
        logger.warning("Failed to send to %s: %s", chat_id, e)
        return False


def _process_update(update: Dict[str, Any]) -> None:
    """Handle one update: /start -> add + welcome, /stop -> remove + goodbye."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat = message.get("chat")
    text = (message.get("text") or "").strip().lower()
    if not chat:
        return
    chat_id = chat.get("id")
    if chat_id is None:
        return
    # Only private chats can subscribe (so we don't add groups by mistake)
    if chat.get("type") != "private":
        return

    if text == "/start":
        if add_subscriber(chat_id):
            logger.info("New subscriber: chat_id=%s", chat_id)
        _send_message(chat_id, WELCOME_MESSAGE)
    elif text in ("/stop", "/unsubscribe"):
        if remove_subscriber(chat_id):
            logger.info("Unsubscribed: chat_id=%s", chat_id)
        _send_message(chat_id, GOODBYE_MESSAGE)
    else:
        # Reply to any other message so the bot doesn't feel unresponsive
        from subscribed_chats import load_subscribed_chat_ids
        if chat_id in load_subscribed_chat_ids():
            _send_message(chat_id, REPLY_WHEN_SUBSCRIBED)
        else:
            _send_message(chat_id, REPLY_WHEN_NOT_SUBSCRIBED)


def _poll_once(offset: int) -> int:
    """Fetch updates, process them, return next offset."""
    if not config.TELEGRAM_BOT_TOKEN:
        return offset
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(
            url,
            params={"timeout": 50, "offset": offset},
            timeout=60,
        )
        if r.status_code != 200:
            return offset
        data = r.json()
        if not data.get("ok"):
            return offset
        updates: List[Dict[str, Any]] = data.get("result") or []
        next_offset = offset
        for u in updates:
            next_offset = max(next_offset, u.get("update_id", 0) + 1)
            try:
                _process_update(u)
            except Exception as e:
                logger.exception("Error processing update: %s", e)
        return next_offset
    except requests.RequestException as e:
        logger.warning("getUpdates failed: %s", e)
        return offset


def _poll_loop() -> None:
    offset = 0
    while True:
        try:
            offset = _poll_once(offset)
        except Exception as e:
            logger.exception("Poller error: %s", e)
        time.sleep(0.5)


def start_poller_thread() -> None:
    """Start the Telegram updates poller in a daemon thread."""
    if not config.ENABLE_SUBSCRIBER_MODE or not config.TELEGRAM_BOT_TOKEN:
        logger.info("Telegram subscriber poller disabled (ENABLE_SUBSCRIBER_MODE or token)")
        return
    t = threading.Thread(target=_poll_loop, daemon=True, name="telegram-poller")
    t.start()
    logger.info("Telegram subscriber poller started (/start to subscribe, signals to all subscribers)")
