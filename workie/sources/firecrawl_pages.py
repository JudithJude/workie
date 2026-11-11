"""Listing / career pages scraped with Firecrawl (v2 API).

1. Each listing page -> list of jobs (JSON extraction).
2. Each NEW job's own page -> full text + links, so we can check its language and
   find the employer's real apply link (aggregators often link to themselves).
Jobs already on the board reuse their stored details, so credits are only spent once.
"""
import logging
import os
import time
from urllib.parse import urljoin, urlparse

from .. import store
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
                    "job_url": {"type": "string"},
                    "posted_date": {"type": "string"},
                },
                "required": ["title", "company", "job_url"],
            },
        }
    },
    "required": ["jobs"],
}
PROMPT = ("Extract every job listed on this page. job_url must be the absolute link to that "
          "job's own detail page as shown on the page; leave it empty if there is none. "
          "posted_date as YYYY-MM-DD if shown. Do not invent values.")

# Hosts that are job boards themselves, never the employer's application page.
AGGREGATORS = ("workingstudentjobs.de", "englishjobs.de", "berlinstartupjobs.com", "joblyst.tech",
               "arbeitnow.com", "jobs.de", "stepstone.de", "indeed.com", "glassdoor", "linkedin.com",
               "xing.com", "google.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
               "youtube.com", "t.co", "bit.ly")
ATS_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "personio.de", "personio.com",
             "smartrecruiters.com", "myworkdayjobs.com", "recruitee.com", "join.com", "softgarden.io",
             "softgarden.de", "workable.com", "teamtailor.com", "bamboohr.com", "successfactors.com",
             "successfactors.eu", "dvinci-easy.com", "onlyfy.jobs", "rexx-systems.com", "workday.com")


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


_DELAY = 6  # seconds between Firecrawl calls (free plan has a low rate limit)


def _scrape(url: str, headers: dict, formats: list) -> dict:
    time.sleep(_DELAY)
    resp = post_json(API, headers=headers, timeout=180, payload={
        "url": url, "onlyMainContent": True, "formats": formats})
    return (resp or {}).get("data") or {}


def _employer_link(links: list[str], company: str, page_url: str) -> str:
    """Pick the employer's apply link from a job page: an ATS link first, then the company's site."""
    page_host = _host(page_url)
    tokens = [t for t in company.lower().replace("-", " ").split() if len(t) >= 3]
    best = ""
    for raw in links or []:
        link = urljoin(page_url, raw)
        h = _host(link)
        if not h or h == page_host or any(a in h for a in AGGREGATORS):
            continue
        if any(h == a or h.endswith("." + a) for a in ATS_HOSTS):
            return link
        if not best and any(t in h.split(".")[0] or t in h for t in tokens) and \
                any(w in link.lower() for w in ("job", "career", "karriere", "apply", "stellen", "position")):
            best = link
    return best


def fetch(cfg: dict) -> list[Job]:
    c = cfg.get("firecrawl", {})
    key = os.getenv("FIRECRAWL_API_KEY")
    if not c.get("enabled", True) or not key:
        if c.get("enabled", True):
            log.info("firecrawl: skipped (no FIRECRAWL_API_KEY)")
        return []
    headers = {"Authorization": f"Bearer {key}"}
    global _DELAY
    _DELAY = c.get("delay_seconds", 6)
    known = store.load()
    budget = c.get("max_details", 40)
    jobs = []
    for url in c.get("urls", []):
        data = _scrape(url, headers, [{"type": "json", "schema": SCHEMA, "prompt": PROMPT}])
        payload = data.get("json") or data.get("extract") or {}
        found = payload.get("jobs", []) if isinstance(payload, dict) else []
        log.info("firecrawl %s: %d", url, len(found))
        for j in found:
            job_url = urljoin(url, j.get("job_url") or j.get("apply_url") or "")
            job = Job(
                title=j.get("title", ""),
                company=j.get("company", ""),
                # Berlin-only listing pages often omit the city on each card.
                location=j.get("location", "") or ("Berlin" if "berlin" in url.lower() else ""),
                description=j.get("summary", ""),
                apply_url=job_url,
                source=f"Firecrawl: {_host(url)}",
                posted_at=to_iso_date(j.get("posted_date")),
            )
            old = known.get(job.id)
            if old and old.description:
                job.description, job.apply_url = old.description, old.apply_url
            elif job_url and budget > 0:
                budget -= 1
                page = _scrape(job_url, headers, ["markdown", "links"])
                job.description = (page.get("markdown") or job.description)[:8000]
                job.apply_url = _employer_link(page.get("links"), job.company, job_url) or job_url
                job.__post_init__()  # re-clean the new description
            jobs.append(job)
    log.info("firecrawl: %d raw, %d detail pages left in budget", len(jobs), budget)
    return jobs
