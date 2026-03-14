"""
Telegram Trading Signals Bot - Main entry point.
Runs the TradingView webhook server (FastAPI + Uvicorn) and (optionally) the Coinglass poller thread.
Designed for 24/7 operation on a VPS or inside Docker.
"""

import logging
import sys

import uvicorn

import config
from coinglass_poller import start_poller_thread
from telegram_poller import start_poller_thread as start_telegram_poller
from webhook_server import app

# -----------------------------------------------------------------------------
# Logging: well visible for debugging, without flooding
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Validate config, start Coinglass poller if enabled, then run webhook server."""
    errors = config.validate_config()
    if errors:
        for e in errors:
            logger.error("Config: %s", e)
        sys.exit(1)

    # Start Coinglass poller in background (no-op if disabled or no API key)
    if config.ENABLE_COINGLASS_LIQUIDATION and config.COINGLASS_API_KEY:
        start_poller_thread()
    else:
        logger.info("Coinglass liquidation polling disabled or no API key")

    # Start Telegram /start subscriber poller (welcome message + subscribe list)
    if config.ENABLE_SUBSCRIBER_MODE:
        start_telegram_poller()

    logger.info(
        "Starting webhook server (FastAPI) on %s:%s",
        config.WEBHOOK_HOST,
        config.WEBHOOK_PORT,
    )
    uvicorn.run(
        app,
        host=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
