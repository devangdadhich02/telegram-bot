"""
AI-powered chat reply using OpenAI API.
When ENABLE_AI_CHAT is true, user messages get an intelligent reply instead of a fixed message.
"""

import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a helpful assistant for a Telegram trading signals bot. "
    "Users receive automated alerts (RSI, MACD, liquidation) here. "
    "Answer briefly and clearly. You can explain what the bot does, how to use /start and /stop, "
    "or answer general trading/signals questions in a simple way. Keep replies concise (a few sentences)."
)


def get_ai_reply(user_message: str) -> Optional[str]:
    """
    Send user message to OpenAI chat completions and return the assistant reply.
    Returns None if API key missing, request fails, or response is empty.
    """
    if not config.OPENAI_API_KEY or not user_message.strip():
        return None
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.OPENAI_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message.strip()},
        ],
        "max_tokens": 300,
    }
    try:
        r = requests.post(
            OPENAI_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        if r.status_code != 200:
            logger.warning("OpenAI API error: %s %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        choices = data.get("choices")
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content")
        if content and isinstance(content, str):
            return content.strip()
        return None
    except requests.RequestException as e:
        logger.warning("OpenAI request failed: %s", e)
        return None
