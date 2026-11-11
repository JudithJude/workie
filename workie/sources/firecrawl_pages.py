"""Listing / career pages scraped with Firecrawl's JSON extraction (v2 API)."""
import logging
import os

from ..http import post_json
from ..models import Job, to_iso_date

log = logging.getLogger("workie")
API = "https://api.firecrawl.dev/v2/scrape"

SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "summary": {"type": "string"},
                    "apply_url": {"type": "string"},
                    "posted_date": {"type": "string"},
                },
                "required": ["title", "company", "apply_url"],
            },
        }
    },
    "required": ["jobs"],
}
PROMPT = ("Extract every job listed on this page. apply_url must be the absolute link "
          "to that job's own posting or application page as shown on the page; leave it "
          "empty if there is none. posted_date as YYYY-MM-DD if shown. Do not invent values.")


def _extract(resp: dict) -> list[dict]:
    data = (resp or {}).get("data") or {}
    payload = data.get("json") or data.get("extract") or {}
    return payload.get("jobs", []) if isinstance(payload, dict) else []


def fetch(cfg: dict) -> list[Job]:
    c = cfg.get("firecrawl", {})
    key = os.getenv("FIRECRAWL_API_KEY")
    if not c.get("enabled", True) or not key:
        if c.get("enabled", True):
            log.info("firecrawl: skipped (no FIRECRAWL_API_KEY)")
        return []
    headers = {"Authorization": f"Bearer {key}"}
    jobs = []
    for url in c.get("urls", []):
        resp = post_json(API, headers=headers, payload={
            "url": url,
            "onlyMainContent": True,
            "formats": [{"type": "json", "schema": SCHEMA, "prompt": PROMPT}],
        })
        found = _extract(resp)
        log.info("firecrawl %s: %d", url, len(found))
        for j in found:
            jobs.append(Job(
                title=j.get("title", ""),
                company=j.get("company", ""),
                # Berlin-only listing pages often omit the city on each card.
                location=j.get("location", "") or ("Berlin" if "berlin" in url.lower() else ""),
                description=j.get("summary", ""),
                apply_url=j.get("apply_url", ""),
                source=f"Firecrawl: {url.split('/')[2]}",
                posted_at=to_iso_date(j.get("posted_date")),
            ))
    return jobs
