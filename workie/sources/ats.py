"""Employer applicant-tracking boards with public JSON APIs.

These come straight from the employer, so they are the most trustworthy source.
"""
import logging

from ..http import get_json
from ..models import Job, to_iso_date

log = logging.getLogger("workie")


def _greenhouse(token):
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                    params={"content": "true"}) or {}
    for j in data.get("jobs", []):
        yield Job(
            title=j.get("title", ""),
            company=j.get("company_name") or token,
            location=(j.get("location") or {}).get("name", ""),
            description=j.get("content", ""),
            apply_url=j.get("absolute_url", ""),
            source=f"{token} (Greenhouse)",
            posted_at=to_iso_date(j.get("first_published") or j.get("updated_at")),
        )


def _lever(company):
    data = get_json(f"https://api.lever.co/v0/postings/{company}",
                    params={"mode": "json"}) or []
    for j in data:
        cats = j.get("categories") or {}
        yield Job(
            title=j.get("text", ""),
            company=company,
            location=cats.get("location", "") or ", ".join(cats.get("allLocations", []) or []),
            description=j.get("descriptionPlain", "") + " " + j.get("additionalPlain", ""),
            apply_url=j.get("applyUrl") or j.get("hostedUrl", ""),
            source=f"{company} (Lever)",
            posted_at=to_iso_date(j.get("createdAt")),
            remote=(j.get("workplaceType") == "remote"),
        )


def _ashby(name):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{name}") or {}
    for j in data.get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", []) or []]
        yield Job(
            title=j.get("title", ""),
            company=name,
            location=", ".join(l for l in locs if l),
            description=j.get("descriptionPlain") or j.get("descriptionHtml", ""),
            apply_url=j.get("applyUrl") or j.get("jobUrl", ""),
            source=f"{name} (Ashby)",
            posted_at=to_iso_date(j.get("publishedAt")),
            remote=bool(j.get("isRemote")),
        )


def fetch(cfg: dict) -> list[Job]:
    c = cfg.get("ats", {}) or {}
    jobs = []
    for fn, key in ((_greenhouse, "greenhouse"), (_lever, "lever"), (_ashby, "ashby")):
        for token in c.get(key, []) or []:
            jobs.extend(fn(token))
    log.info("ats: %d raw", len(jobs))
    return jobs
