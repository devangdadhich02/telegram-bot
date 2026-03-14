"""
Telegram notification sender with formatted messages and error handling.
Sends concise alerts (asset, timeframe, trigger, values, Buy/Sell) to a chat or channel.
"""

import logging
import time
from collections import deque
from typing import Optional, Union

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
    If the original payload includes advanced fields such as TP/SL, leverage, pattern,
    they are appended when present so TradingView strategies can enrich the message.
    """
    lines = [
        f"🪙 {signal.asset_pair}  ·  {signal.timeframe}",
        f"Trigger: {signal.trigger_type}",
        signal.numerical_values,
        f"Time: {signal.timestamp}",
        f"Recommendation: {signal.recommendation}",
    ]

    payload = signal.raw_payload or {}
    # Optional advanced fields from TradingView strategy/indicator
    pattern = payload.get("pattern") or payload.get("chart_pattern")
    leverage = payload.get("leverage")
    entry = payload.get("entry")
    sl = payload.get("sl") or payload.get("stop_loss")
    tp1 = payload.get("tp1")
    tp2 = payload.get("tp2")
    tp3 = payload.get("tp3")
    gain = payload.get("gain_percent") or payload.get("gain_pct")

    if pattern:
        lines.append(f"Pattern: {pattern}")
    if leverage:
        lines.append(f"Leverage: {leverage}")
    if entry or sl:
        parts = []
        if entry:
            parts.append(f"Entry: {entry}")
        if sl:
            parts.append(f"SL: {sl}")
        lines.append(", ".join(parts))
    if tp1 or tp2 or tp3:
        tp_parts = []
        if tp1:
            tp_parts.append(f"TP1: {tp1}")
        if tp2:
            tp_parts.append(f"TP2: {tp2}")
        if tp3:
            tp_parts.append(f"TP3: {tp3}")
        lines.append(", ".join(tp_parts))
    if gain:
        lines.append(f"Gain: {gain}")

    return "\n".join(lines)


def send_telegram_message_to_chat(chat_id: Union[str, int], text: str) -> bool:
    """
    Send a plain text message to a specific chat_id.
    Returns True on success, False on failure (logs error).
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram not configured; skipping send")
        return False
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        logger.error("Telegram API error for chat_id=%s: %s %s", chat_id, r.status_code, r.text)
        return False
    except requests.RequestException as e:
        logger.exception("Failed to send Telegram message to %s: %s", chat_id, e)
        return False


def send_telegram_message(text: str) -> bool:
    """
    Send a plain text message to the configured Telegram chat (single chat mode).
    Returns True if at least one send succeeded.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram not configured; skipping send")
        return False
    if config.ENABLE_SUBSCRIBER_MODE:
        from subscribed_chats import get_subscribed_chat_ids
        chat_ids = list(get_subscribed_chat_ids())
        if config.TELEGRAM_CHAT_ID:
            try:
                extra = int(config.TELEGRAM_CHAT_ID)
                if extra not in chat_ids:
                    chat_ids.append(extra)
            except ValueError:
                if config.TELEGRAM_CHAT_ID not in chat_ids:
                    chat_ids.append(config.TELEGRAM_CHAT_ID)
        if not chat_ids:
            logger.warning("No subscribers and no TELEGRAM_CHAT_ID; skipping send")
            return False
        ok_count = sum(1 for cid in chat_ids if send_telegram_message_to_chat(cid, text))
        logger.info("Telegram sendMessage to %s chats (ok=%s)", len(chat_ids), ok_count)
        return ok_count > 0
    if not config.TELEGRAM_CHAT_ID:
        return False
    ok = send_telegram_message_to_chat(config.TELEGRAM_CHAT_ID, text)
    if ok:
        logger.info("Telegram sendMessage OK (chat_id=%s)", config.TELEGRAM_CHAT_ID)
    return ok


def _generate_chart_image(signal: ProcessedSignal) -> Optional[bytes]:
    """
    Optionally call an external chart snapshot service to get a TradingView-style
    chart image as PNG/JPEG bytes. The service URL and API key are configured
    via .env (CHART_IMAGE_API_BASE, CHART_IMAGE_API_KEY).
    """
    if not config.ENABLE_CHART_IMAGE:
        return None
    if not config.CHART_IMAGE_API_BASE:
        logger.warning("Chart image enabled but CHART_IMAGE_API_BASE is empty")
        return None

    params = {
        "symbol": signal.asset_pair,
        "interval": signal.timeframe,
    }
    headers = {}
    if config.CHART_IMAGE_API_KEY:
        headers["X-API-KEY"] = config.CHART_IMAGE_API_KEY

    try:
        resp = requests.get(
            config.CHART_IMAGE_API_BASE,
            params=params,
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 200 and resp.content:
            return resp.content
        logger.error(
            "Chart image API error: %s %s", resp.status_code, resp.text[:200]
        )
        return None
    except requests.RequestException as e:
        logger.exception("Failed to fetch chart image: %s", e)
        return None


def send_telegram_photo_to_chat(chat_id: Union[str, int], caption: str, image_bytes: bytes) -> bool:
    """Send a photo with caption to a specific chat_id. Returns True on success."""
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption}
    files = {"photo": ("chart.png", image_bytes)}
    try:
        r = requests.post(url, data=data, files=files, timeout=20)
        return r.status_code == 200
    except requests.RequestException:
        return False


def send_telegram_photo_with_caption(
    caption: str, image_bytes: bytes
) -> bool:
    """
    Send a photo with caption to configured chat(s).
    In subscriber mode: all subscribers + optional TELEGRAM_CHAT_ID.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram not configured; skipping send")
        return False
    if config.ENABLE_SUBSCRIBER_MODE:
        from subscribed_chats import get_subscribed_chat_ids
        chat_ids = list(get_subscribed_chat_ids())
        if config.TELEGRAM_CHAT_ID:
            try:
                extra = int(config.TELEGRAM_CHAT_ID)
                if extra not in chat_ids:
                    chat_ids.append(extra)
            except ValueError:
                if config.TELEGRAM_CHAT_ID not in chat_ids:
                    chat_ids.append(config.TELEGRAM_CHAT_ID)
        if not chat_ids:
            logger.warning("No subscribers; skipping photo send")
            return False
        ok_count = sum(
            1 for cid in chat_ids
            if send_telegram_photo_to_chat(cid, caption, image_bytes)
        )
        logger.info("Telegram sendPhoto to %s chats (ok=%s)", len(chat_ids), ok_count)
        return ok_count > 0
    if not config.TELEGRAM_CHAT_ID:
        return False
    return send_telegram_photo_to_chat(config.TELEGRAM_CHAT_ID, caption, image_bytes)


def notify_signal(signal: ProcessedSignal) -> bool:
    """
    Format and send a ProcessedSignal to Telegram.
    If chart snapshots are enabled and a chart image can be generated, send it
    as a photo with caption; otherwise fall back to plain text.
    """
    text = format_signal_message(signal)

    image_bytes = _generate_chart_image(signal)
    if image_bytes:
        return send_telegram_photo_with_caption(text, image_bytes)

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
