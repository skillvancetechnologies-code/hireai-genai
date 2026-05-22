"""Pre-warm the explanation cache before demo day.

W5/W6 task. Iterates over all (candidate_id, job_id) pairs in the
demo flow and generates explanations so live demo calls are 100%
cache hits with zero LLM latency.

W1 stub - real implementation lands when G3's generator is live.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
logging.basicConfig(level="INFO")


def main() -> int:
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.web_backend_url}/applications?limit=2000", timeout=10)
        resp.raise_for_status()
        apps = resp.json()
    except Exception as e:
        log.error("Could not fetch applications from web backend: %s", e)
        log.error("This is expected in W1 - web team's /api/applications isn't live yet.")
        return 1

    log.info("Loaded %d (candidate, job) pairs to pre-cache.", len(apps))
    log.info("TODO (W5): call generate_explanation() for each pair.")
    # for app_row in apps:
    #     generate_explanation(app_row["candidate_id"], app_row["job_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
