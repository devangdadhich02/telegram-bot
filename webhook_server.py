"""
FastAPI webhook server for TradingView alerts.
Receives POST JSON with RSI/MACD (or strategy) data and forwards to Telegram
after processing and throttling.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

import config
from signal_processor import process_tradingview_webhook
from telegram_notifier import notify_signal_with_throttle

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Telegram Trading Signals Bot",
    description="Webhook receiver for TradingView alerts (RSI, MACD) and notification gateway to Telegram.",
    version="1.0.0",
)


@app.get("/health")
def health() -> Dict[str, Any]:
    """Liveness/readiness check for Docker and VPS."""
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """
    TradingView webhook endpoint.
    Expects JSON body with at least: symbol/ticker, and optionally
    trigger (RSI/MACD), timeframe, close, rsi, macd, side/action.
    Also accepts form-encoded body with 'payload', 'data', or 'json' field containing JSON.
    """
    if not config.ENABLE_TRADINGVIEW_WEBHOOK:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "reason": "webhook disabled"},
        )

    payload: Optional[Dict[str, Any]] = None
    content_type = request.headers.get("content-type", "")

    # Prefer JSON body
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as e:
            logger.warning("Webhook JSON parse error: %s", e)

    # Fallback: form-encoded with JSON in a field (e.g. payload, data, json)
    if payload is None:
        try:
            form = await request.form()
            if form:
                raw = form.get("payload") or form.get("data") or form.get("json")
                if isinstance(raw, str):
                    payload = json.loads(raw)
                if payload is None:
                    payload = dict(form)
        except Exception as e:
            logger.warning("Webhook form parse error: %s", e)

    if not payload or not isinstance(payload, dict):
        logger.warning("Webhook received empty or invalid body")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "reason": "invalid payload"},
        )

    try:
        signal = process_tradingview_webhook(payload)
    except Exception as e:
        logger.exception("Error processing webhook: %s", e)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": "processing error"},
        )

    if signal is None:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "reason": "could not build signal"},
        )

    sent = notify_signal_with_throttle(signal)
    if sent:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "message": "alert sent"},
        )
    return JSONResponse(
        status_code=200,
        content={"ok": True, "message": "alert skipped (throttle)"},
    )
