"""
Configuration loader for the Telegram Trading Signals Bot.
Reads from environment variables (via .env) with sensible defaults.
"""

import os
from typing import List, Tuple

# Load .env if present (no-op if python-dotenv not used or file missing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_bool(key: str, default: bool = True) -> bool:
    v = os.environ.get(key, "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


# -----------------------------------------------------------------------------
# Telegram
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = _get_str("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get_str("TELEGRAM_CHAT_ID")
# When True: anyone who /start the bot gets welcome and receives signals in private chat.
# Subscribers are stored in SUBSCRIBED_CHATS_FILE. TELEGRAM_CHAT_ID is optional (e.g. group to also broadcast).
ENABLE_SUBSCRIBER_MODE = _get_bool("ENABLE_SUBSCRIBER_MODE", True)
SUBSCRIBED_CHATS_FILE = _get_str("SUBSCRIBED_CHATS_FILE", "subscribed_chats.json")

# -----------------------------------------------------------------------------
# Webhook server (TradingView)
# -----------------------------------------------------------------------------
WEBHOOK_PORT = _get_int("WEBHOOK_PORT", 80)
WEBHOOK_HOST = _get_str("WEBHOOK_HOST", "0.0.0.0")

# -----------------------------------------------------------------------------
# Coinglass
# -----------------------------------------------------------------------------
COINGLASS_API_KEY = _get_str("COINGLASS_API_KEY")
COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com"
COINGLASS_POLL_INTERVAL = max(60, _get_int("COINGLASS_POLL_INTERVAL", 60))


def get_coinglass_symbols() -> List[Tuple[str, str]]:
    """
    Parse COINGLASS_SYMBOLS into list of (exchange, symbol) pairs.
    Format: exchange:pair e.g. Binance:BTCUSDT,Binance:ETHUSDT
    """
    raw = _get_str("COINGLASS_SYMBOLS", "Binance:BTCUSDT")
    out = []
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            ex, sym = part.split(":", 1)
            out.append((ex.strip(), sym.strip()))
    return out if out else [("Binance", "BTCUSDT")]


COINGLASS_SYMBOLS = get_coinglass_symbols()

# -----------------------------------------------------------------------------
# Thresholds
# -----------------------------------------------------------------------------
RSI_OVERSOLD = _get_int("RSI_OVERSOLD", 30)
RSI_OVERBOUGHT = _get_int("RSI_OVERBOUGHT", 70)
LIQUIDATION_SPIKE_USD = _get_int("LIQUIDATION_SPIKE_USD", 5_000_000)
ALERT_COOLDOWN_SECONDS = _get_int("ALERT_COOLDOWN_SECONDS", 300)

# -----------------------------------------------------------------------------
# Anti-spam
# -----------------------------------------------------------------------------
MAX_ALERTS_PER_MINUTE = _get_int("MAX_ALERTS_PER_MINUTE", 10)
ENABLE_TRADINGVIEW_WEBHOOK = _get_bool("ENABLE_TRADINGVIEW_WEBHOOK", True)
ENABLE_COINGLASS_LIQUIDATION = _get_bool("ENABLE_COINGLASS_LIQUIDATION", True)

# -----------------------------------------------------------------------------
# Chart snapshot (optional)
# -----------------------------------------------------------------------------
# If ENABLE_CHART_IMAGE is true and CHART_IMAGE_API_BASE is set, the bot will
# attempt to generate a chart image for each alert and send it as a photo with
# caption instead of plain text. CHART_IMAGE_API_BASE should point to a service
# that returns a PNG/JPEG when called with symbol/interval query parameters.
ENABLE_CHART_IMAGE = _get_bool("ENABLE_CHART_IMAGE", False)
CHART_IMAGE_API_BASE = _get_str("CHART_IMAGE_API_BASE")
CHART_IMAGE_API_KEY = _get_str("CHART_IMAGE_API_KEY")


def validate_config() -> List[str]:
    """Return list of configuration errors (empty if valid)."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is required")
    if not ENABLE_SUBSCRIBER_MODE and not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID is required when ENABLE_SUBSCRIBER_MODE is false")
    if ENABLE_COINGLASS_LIQUIDATION and not COINGLASS_API_KEY:
        errors.append("COINGLASS_API_KEY is required when ENABLE_COINGLASS_LIQUIDATION is true")
    return errors
