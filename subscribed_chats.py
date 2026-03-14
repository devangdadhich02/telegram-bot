"""
Persist and manage list of Telegram chat IDs that subscribed via /start.
Used when ENABLE_SUBSCRIBER_MODE is true: signals are sent to all subscribers.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Set

import config

logger = logging.getLogger(__name__)


def _path() -> Path:
    return Path(config.SUBSCRIBED_CHATS_FILE)


def load_subscribed_chat_ids() -> Set[int]:
    """Load set of chat IDs from file. Returns empty set if file missing or invalid."""
    p = _path()
    if not p.exists():
        return set()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = data.get("chat_ids", data) if isinstance(data, dict) else data
        return set(int(x) for x in ids if isinstance(x, (int, str)) and str(x).lstrip("-").isdigit())
    except Exception as e:
        logger.warning("Could not load subscribed chats from %s: %s", p, e)
        return set()


def save_subscribed_chat_ids(chat_ids: Set[int]) -> None:
    """Write list of chat IDs to file."""
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"chat_ids": sorted(chat_ids)}, f, indent=0)
    except Exception as e:
        logger.exception("Could not save subscribed chats to %s: %s", p, e)


def add_subscriber(chat_id: int) -> bool:
    """Add chat_id to subscribers; returns True if added (new)."""
    ids = load_subscribed_chat_ids()
    if chat_id in ids:
        return False
    ids.add(chat_id)
    save_subscribed_chat_ids(ids)
    return True


def remove_subscriber(chat_id: int) -> bool:
    """Remove chat_id from subscribers; returns True if removed."""
    ids = load_subscribed_chat_ids()
    if chat_id not in ids:
        return False
    ids.discard(chat_id)
    save_subscribed_chat_ids(ids)
    return True


def get_subscribed_chat_ids() -> List[int]:
    """Return list of subscribed chat IDs (for sending signals)."""
    return sorted(load_subscribed_chat_ids())
