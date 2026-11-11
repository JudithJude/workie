"""Arbeitnow public job board API (free, no key)."""
import logging

from ..http import get_json
from ..models import Job, to_iso_date

log = logging.getLogger("workie")
API = "https://www.arbeitnow.com/api/job-board-api"


def fetch(cfg: dict) -> list[Job]:
    c = cfg.get("arbeitnow", {})
    if not c.get("enabled", True):
        return []
    jobs = []
    for page in range(1, c.get("pages", 10) + 1):
        data = get_json(API, params={"page": page})
        if not data or not data.get("data"):
            break
        for j in data["data"]:
            jobs.append(Job(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                location=j.get("location", ""),
                description=j.get("description", "") + " " + " ".join(j.get("job_types", [])),
                apply_url=j.get("url", ""),
                source="Arbeitnow",
                posted_at=to_iso_date(j.get("created_at")),
                remote=bool(j.get("remote")),
            ))
        if not (data.get("links") or {}).get("next"):
            break
    log.info("arbeitnow: %d raw", len(jobs))
    return jobs
