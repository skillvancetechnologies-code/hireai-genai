"""Compatibility wrapper for the Week 3 copilot intent parser."""

from app.modules.copilot.intent import (  # noqa: F401
    IntentParseError,
    _parse_with_rules,
    _validate_intent,
    parse_query,
)
