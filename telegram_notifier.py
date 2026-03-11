"""
Telegram notification sender with formatted messages and error handling.
Sends concise alerts (asset, timeframe, trigger, values, Buy/Sell) to a chat or channel.
"""

import logging
import time
from collections import deque
from typing import Optional

import requests

import config
from signal_processor import ProcessedSignal

logger = logging.getLogger(__name__)

# Telegram Bot API base URL
TELEGRAM_API_BASE = "https://api.telegram.org/bot"


def format_signal_message(signal: ProcessedSignal) -> str:
    """
    Build a concise notification text for Telegram (plain text, no markdown by default
    to avoid parse errors with special characters in symbols).
    """
    lines = [
        f"🪙 {signal.asset_pair}  ·  {signal.timeframe}",
        f"Trigger: {signal.trigger_type}",
        signal.numerical_values,
        f"Time: {signal.timestamp}",
        f"Recommendation: {signal.recommendation}",
    ]
    return "\n".join(lines)


def send_telegram_message(text: str) -> bool:
    """
    Send a plain text message to the configured Telegram chat.
    Returns True on success, False on failure (logs error).
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured; skipping send")
        return False
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        logger.error("Telegram API error: %s %s", r.status_code, r.text)
        return False
    except requests.RequestException as e:
        logger.exception("Failed to send Telegram message: %s", e)
        return False


def notify_signal(signal: ProcessedSignal) -> bool:
    """Format and send a ProcessedSignal to Telegram."""
    text = format_signal_message(signal)
    return send_telegram_message(text)


# -----------------------------------------------------------------------------
# Anti-spam: cooldown per (asset, trigger) and global rate limit
# -----------------------------------------------------------------------------
_last_alert_times: dict = {}  # (asset_pair, trigger_type) -> last send time
_alert_timestamps: deque = deque(maxlen=100)  # recent alert times for rate limit


def _cooldown_key(asset_pair: str, trigger_type: str) -> tuple:
    return (asset_pair.strip().upper(), trigger_type.strip().upper())


def should_throttle_cooldown(asset_pair: str, trigger_type: str) -> bool:
    """True if we are still within cooldown for this asset+trigger."""
    key = _cooldown_key(asset_pair, trigger_type)
    last = _last_alert_times.get(key)
    if last is None:
        return False
    return (time.time() - last) < config.ALERT_COOLDOWN_SECONDS


def should_throttle_rate_limit() -> bool:
    """True if we have already sent MAX_ALERTS_PER_MINUTE in the last minute."""
    now = time.time()
    cutoff = now - 60
    # Drop old entries
    while _alert_timestamps and _alert_timestamps[0] < cutoff:
        _alert_timestamps.popleft()
    return len(_alert_timestamps) >= config.MAX_ALERTS_PER_MINUTE


def record_alert_sent(asset_pair: str, trigger_type: str) -> None:
    """Record that an alert was sent for cooldown and rate limit."""
    key = _cooldown_key(asset_pair, trigger_type)
    now = time.time()
    _last_alert_times[key] = now
    _alert_timestamps.append(now)


def notify_signal_with_throttle(signal: ProcessedSignal) -> bool:
    """
    Send notification only if cooldown and rate limit allow.
    Returns True if message was sent, False if skipped or failed.
    """
    if should_throttle_rate_limit():
        logger.info("Rate limit: skipping alert (max per minute reached)")
        return False
    if should_throttle_cooldown(signal.asset_pair, signal.trigger_type):
        logger.info(
            "Cooldown: skipping alert for %s %s",
            signal.asset_pair,
            signal.trigger_type,
        )
        return False
    ok = notify_signal(signal)
    if ok:
        record_alert_sent(signal.asset_pair, signal.trigger_type)
    return ok
