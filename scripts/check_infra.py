"""Quick infra check. Pings Redis through app.core.cache so we use
the same connection path the LLM wrapper does.

Exit code 0 = Redis up, 1 = down (memory fallback in use)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.cache import _get_client  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    client = _get_client()
    if client is None:
        print(f"Redis: DOWN (url={settings.redis_url}) - using memory fallback")
        return 1
    try:
        client.ping()
    except Exception as e:
        print(f"Redis: DOWN (ping failed: {e})")
        return 1
    print(f"Redis: UP (url={settings.redis_url})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
