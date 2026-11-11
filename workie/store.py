"""JSON store: data/jobs.json (board) and data/rejected.json (last run's rejections)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .models import Job

DATA = Path(__file__).resolve().parent.parent / "data"
JOBS = DATA / "jobs.json"
REJECTED = DATA / "rejected.json"


def load() -> dict[str, Job]:
    if not JOBS.exists():
        return {}
    return {d["id"]: Job.from_dict(d) for d in json.loads(JOBS.read_text())}


def merge(existing: dict[str, Job], fresh: list[Job], today: date) -> tuple[dict[str, Job], int]:
    """Upsert fresh jobs (dedupe by company+title). Returns (store, new_count)."""
    stamp = today.isoformat()
    new = 0
    for job in fresh:
        old = existing.get(job.id)
        job.last_seen = stamp
        job.first_seen = old.first_seen if old else stamp
        if not old:
            new += 1
        existing[job.id] = job
    return existing, new


def visible(store: dict[str, Job], today: date, hide_after_days: int) -> list[Job]:
    cutoff = (today - timedelta(days=hide_after_days)).isoformat()
    jobs = [j for j in store.values() if j.last_seen >= cutoff]
    return sorted(jobs, key=lambda j: (j.first_seen, j.posted_at or ""), reverse=True)


def save(store: dict[str, Job], rejected: list[dict], today: date, keep_days: int = 60):
    DATA.mkdir(exist_ok=True)
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    rows = [j.to_dict() for j in store.values() if j.last_seen >= cutoff]
    rows.sort(key=lambda d: d["first_seen"], reverse=True)
    JOBS.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    REJECTED.write_text(json.dumps(rejected, ensure_ascii=False, indent=1))
