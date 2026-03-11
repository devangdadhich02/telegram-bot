"""
Coinglass API poller for liquidation data.
Polls at most once per minute (configurable) to stay within API limits.
Detects liquidation spikes and emits signals when threshold is exceeded.
"""

import logging
import threading
import time
from typing import List, Tuple

import requests

import config
from signal_processor import (
    TRIGGER_LIQUIDATION,
    process_liquidation_signal,
    ProcessedSignal,
)
from telegram_notifier import notify_signal_with_throttle

logger = logging.getLogger(__name__)


def fetch_liquidation_history(
    exchange: str, symbol: str, interval: str = "1h", limit: int = 2
) -> List[dict]:
    """
    Call Coinglass liquidation history API.
    Returns list of { time, long_liquidation_usd, short_liquidation_usd }.
    """
    if not config.COINGLASS_API_KEY:
        return []
    url = f"{config.COINGLASS_BASE_URL}/api/futures/liquidation/history"
    headers = {"CG-API-KEY": config.COINGLASS_API_KEY}
    params = {
        "exchange": exchange,
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning("Coinglass API %s: %s", r.status_code, r.text[:200])
            return []
        data = r.json()
        if data.get("code") != "0":
            logger.warning("Coinglass error: %s", data.get("msg", data))
            return []
        return data.get("data") or []
    except requests.RequestException as e:
        logger.exception("Coinglass request failed: %s", e)
        return []


def parse_liquidation_amount(val) -> float:
    """Parse liquidation value (string or number) to float USD."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def check_liquidation_spike(
    exchange: str, symbol: str
) -> List[ProcessedSignal]:
    """
    Fetch recent 1h liquidation data; if total (long+short) exceeds
    LIQUIDATION_SPIKE_USD, produce a ProcessedSignal for the latest bucket.
    """
    rows = fetch_liquidation_history(exchange, symbol, interval="1h", limit=2)
    if not rows:
        return []
    # Use most recent bucket
    latest = rows[0]
    long_liq = parse_liquidation_amount(latest.get("long_liquidation_usd"))
    short_liq = parse_liquidation_amount(latest.get("short_liquidation_usd"))
    total = long_liq + short_liq
    if total < config.LIQUIDATION_SPIKE_USD:
        return []
    signal = process_liquidation_signal(
        exchange=exchange,
        symbol=symbol,
        timeframe="1h",
        long_liq_usd=long_liq,
        short_liq_usd=short_liq,
        interval_label="1h",
    )
    return [signal]


def run_poller_once() -> None:
    """Check all configured Coinglass symbols and send alerts for spikes."""
    if not config.ENABLE_COINGLASS_LIQUIDATION or not config.COINGLASS_API_KEY:
        return
    for exchange, symbol in config.COINGLASS_SYMBOLS:
        try:
            signals = check_liquidation_spike(exchange, symbol)
            for sig in signals:
                notify_signal_with_throttle(sig)
        except Exception as e:
            logger.exception("Error checking %s %s: %s", exchange, symbol, e)


def run_poller_loop() -> None:
    """
    Run Coinglass poll in a loop with COINGLASS_POLL_INTERVAL seconds between runs.
    Designed to be started in a background thread.
    """
    logger.info(
        "Coinglass poller started (interval=%ss)",
        config.COINGLASS_POLL_INTERVAL,
    )
    while True:
        try:
            run_poller_once()
        except Exception as e:
            logger.exception("Poller loop error: %s", e)
        time.sleep(config.COINGLASS_POLL_INTERVAL)


def start_poller_thread() -> threading.Thread:
    """Start the Coinglass poller in a daemon thread."""
    t = threading.Thread(target=run_poller_loop, daemon=True)
    t.start()
    return t
