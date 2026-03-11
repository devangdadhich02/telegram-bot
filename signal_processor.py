"""
Signal processing and Buy/Sell recommendation logic.
Applies configurable thresholds (RSI, MACD, liquidation) and produces a single tag.
"""

from dataclasses import dataclass
from typing import Optional

import config


# Trigger types we support (aligned with client requirements)
TRIGGER_RSI = "RSI"
TRIGGER_MACD = "MACD"
TRIGGER_LIQUIDATION = "liquidation"


@dataclass
class ProcessedSignal:
    """A signal ready to be sent to Telegram."""
    asset_pair: str
    timeframe: str
    trigger_type: str  # RSI, MACD, liquidation
    numerical_values: str  # e.g. "RSI=28.5" or "Long liq: $1.2M, Short liq: $0.8M"
    timestamp: str
    recommendation: str  # "Buy" or "Sell"
    raw_payload: Optional[dict] = None  # Original webhook payload if any


def recommend_from_rsi(rsi_value: Optional[float]) -> str:
    """
    Map RSI to Buy/Sell using configured thresholds.
    RSI < oversold -> Buy; RSI > overbought -> Sell; else neutral (we still send as info).
    """
    if rsi_value is None:
        return "—"
    if rsi_value <= config.RSI_OVERSOLD:
        return "Buy"
    if rsi_value >= config.RSI_OVERBOUGHT:
        return "Sell"
    return "—"


def recommend_from_macd(side: Optional[str]) -> str:
    """
    Map MACD crossover to Buy/Sell.
    'buy' / 'long' / 'bullish' -> Buy; 'sell' / 'short' / 'bearish' -> Sell.
    """
    if not side:
        return "—"
    s = str(side).strip().lower()
    if s in ("buy", "long", "bullish", "bull"):
        return "Buy"
    if s in ("sell", "short", "bearish", "bear"):
        return "Sell"
    return "—"


def recommend_from_liquidation(
    long_liq_usd: float, short_liq_usd: float
) -> str:
    """
    Liquidation spike interpretation:
    - Large long liquidations often occur in sell-offs -> can precede bounce (Buy).
    - Large short liquidations often occur in squeezes -> can precede pullback (Sell).
    Client can adjust logic; this is a simple heuristic.
    """
    if long_liq_usd >= short_liq_usd and long_liq_usd > 0:
        return "Buy"   # Longs liquidated -> potential reversal up
    if short_liq_usd > long_liq_usd and short_liq_usd > 0:
        return "Sell"  # Shorts liquidated -> potential reversal down
    return "—"


def process_tradingview_webhook(payload: dict) -> Optional[ProcessedSignal]:
    """
    Parse TradingView webhook JSON and build a ProcessedSignal.
    Expects flexible payload: symbol, timeframe, trigger (RSI/MACD), value, side, etc.
    """
    # Normalize common keys (TradingView uses {{ticker}}, custom fields for RSI/MACD)
    symbol = (
        payload.get("symbol")
        or payload.get("ticker")
        or payload.get("asset")
        or "UNKNOWN"
    )
    if isinstance(symbol, dict):
        symbol = str(symbol)
    symbol = str(symbol).strip()

    timeframe = (
        payload.get("timeframe")
        or payload.get("interval")
        or payload.get("timeframe_name")
        or "—"
    )
    timeframe = str(timeframe).strip()

    trigger = (
        payload.get("trigger")
        or payload.get("trigger_type")
        or payload.get("indicator")
        or "signal"
    )
    trigger = str(trigger).strip().upper()
    if trigger == "SIGNAL":
        # Infer from strategy order action if present
        side = payload.get("side") or payload.get("strategy_order_action") or payload.get("action")
        if side:
            trigger = "MACD"  # Treat as MACD-style signal
    if trigger not in (TRIGGER_RSI, TRIGGER_MACD):
        trigger = TRIGGER_MACD  # Default for strategy alerts

    # Numerical values string
    parts = []
    price = payload.get("close") or payload.get("price")
    if price is not None:
        parts.append(f"Price: {price}")
    rsi = payload.get("rsi") or payload.get("RSI")
    if rsi is not None:
        try:
            rsi_f = float(rsi)
            parts.append(f"RSI: {rsi_f:.2f}")
        except (TypeError, ValueError):
            parts.append(f"RSI: {rsi}")
    macd = payload.get("macd") or payload.get("MACD")
    if macd is not None:
        parts.append(f"MACD: {macd}")
    numerical = ", ".join(parts) if parts else "—"

    # Recommendation
    if trigger == TRIGGER_RSI:
        try:
            rsi_val = float(rsi) if rsi is not None else None
        except (TypeError, ValueError):
            rsi_val = None
        recommendation = recommend_from_rsi(rsi_val)
    else:
        side = payload.get("side") or payload.get("strategy_order_action") or payload.get("action")
        recommendation = recommend_from_macd(side)

    # Timestamp
    ts = payload.get("time") or payload.get("timestamp") or payload.get("alert_time")
    if ts is None:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
    timestamp = str(ts)

    return ProcessedSignal(
        asset_pair=symbol,
        timeframe=timeframe,
        trigger_type=trigger,
        numerical_values=numerical or "—",
        timestamp=timestamp,
        recommendation=recommendation,
        raw_payload=payload,
    )


def process_liquidation_signal(
    exchange: str,
    symbol: str,
    timeframe: str,
    long_liq_usd: float,
    short_liq_usd: float,
    interval_label: str = "1h",
) -> ProcessedSignal:
    """Build a ProcessedSignal from Coinglass liquidation data."""
    from datetime import datetime, timezone
    recommendation = recommend_from_liquidation(long_liq_usd, short_liq_usd)
    numerical = (
        f"Long liq: ${long_liq_usd:,.0f}, Short liq: ${short_liq_usd:,.0f}"
    )
    asset = f"{exchange}:{symbol}"
    return ProcessedSignal(
        asset_pair=asset,
        timeframe=interval_label,
        trigger_type=TRIGGER_LIQUIDATION,
        numerical_values=numerical,
        timestamp=datetime.now(timezone.utc).isoformat(),
        recommendation=recommendation,
        raw_payload=None,
    )
