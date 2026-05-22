"""Slack posting helper.

Single entry point: `post_to_slack(text)`. Reads the webhook URL from
`settings.slack_webhook_url`. If the webhook is unset (offline dev,
CI, weekend hacking), no-ops and logs the message instead — never
raises so the nightly cron stays green.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


def post_to_slack(text: str, *, timeout: float = 5.0) -> bool:
    """Returns True if posted, False if no-op'd (no webhook configured)
    or if the post failed. Never raises."""
    webhook = get_settings().slack_webhook_url
    if not webhook:
        log.info("[slack no-op, no webhook] %s", text)
        return False
    try:
        r = httpx.post(webhook, json={"text": text}, timeout=timeout)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("Slack post failed: %s", e)
        return False
