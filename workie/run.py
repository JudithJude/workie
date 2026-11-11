"""Daily pipeline: fetch -> filter -> fraud check -> dedupe -> store -> build board.

Usage: python -m workie.run
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from . import board, filters, fraud, store
from .models import Job
from .sources import ALL

log = logging.getLogger("workie")
ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path = ROOT / "config.yaml") -> dict:
    return yaml.safe_load(path.read_text())


def process(raw: list[Job], cfg: dict, today: date) -> tuple[list[Job], list[dict]]:
    kept, rejected, seen = [], [], set()
    for job in raw:
        if job.id in seen:
            continue
        seen.add(job.id)
        reason = filters.check(job, cfg)
        if reason in ("Not in Berlin", "Not a student or side job"):
            continue  # irrelevant, not worth logging
        reason = reason or fraud.check(job, cfg, today)
        if reason:
            rejected.append({"id": job.id, "title": job.title, "company": job.company, "source": job.source,
                             "url": job.apply_url, "reason": reason})
        else:
            kept.append(job)
    return kept, rejected


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config()
    today = date.today()

    raw: list[Job] = []
    for name, fetch in ALL.items():
        try:
            raw.extend(fetch(cfg))
        except Exception:  # one broken source must not kill the run
            log.exception("source %s failed", name)

    kept, rejected = process(raw, cfg, today)
    db = store.load()
    for r in rejected:  # a job that now fails a check leaves the board immediately
        db.pop(r["id"], None)
    db, new = store.merge(db, kept, today)
    store.save(db, rejected, today)
    shown = store.visible(db, today, cfg.get("hide_after_unseen_days", 3))
    board.build(shown, rejected, today)

    log.info("raw=%d kept=%d new=%d rejected=%d shown=%d", len(raw), len(kept), new, len(rejected), len(shown))
    for reason, n in Counter(r["reason"].split(" (")[0] for r in rejected).most_common():
        log.info("  rejected: %-40s %d", reason, n)


if __name__ == "__main__":
    main()
