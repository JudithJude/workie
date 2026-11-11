"""Bundesagentur für Arbeit Jobsuche API (official German job board, public key)."""
import base64
import logging

from ..http import get_json
from ..models import Job, to_iso_date

log = logging.getLogger("workie")
BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}
DETAIL_PAGE = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
DESC_KEYS = ("stellenangebotsBeschreibung", "stellenbeschreibung", "beschreibung")


def _search(params):
    data = get_json(f"{BASE}/pc/v4/jobs", params=params, headers=HEADERS) or {}
    return data.get("stellenangebote") or []


def _description(refnr: str) -> str:
    code = base64.b64encode(refnr.encode()).decode()
    d = get_json(f"{BASE}/pc/v4/jobdetails/{code}", headers=HEADERS) or {}
    for k in DESC_KEYS:
        if isinstance(d.get(k), str):
            return d[k]
    # Fallback: longest string field in the response.
    strings = [v for v in d.values() if isinstance(v, str)]
    return max(strings, key=len, default="")


def fetch(cfg: dict) -> list[Job]:
    c = cfg.get("bundesagentur", {})
    if not c.get("enabled", True):
        return []
    base = {"wo": c.get("where", "Berlin"), "umkreis": c.get("radius_km", 25),
            "angebotsart": 1, "size": 100, "page": 1}
    raw = {}
    for q in c.get("queries", []):
        for item in _search({**base, "was": q}):
            raw[item.get("refnr")] = item
    if c.get("minijob"):
        for item in _search({**base, "arbeitszeit": "mj"}):
            raw[item.get("refnr")] = item

    jobs = []
    budget = c.get("max_details", 60)
    for refnr, item in raw.items():
        if not refnr:
            continue
        desc = ""
        if budget > 0:
            desc = _description(refnr)
            budget -= 1
        place = (item.get("arbeitsort") or {}).get("ort", "")
        jobs.append(Job(
            title=item.get("titel") or item.get("beruf", ""),
            company=item.get("arbeitgeber", ""),
            location=place,
            description=desc,
            # Official BA page; it links on to the employer's own application.
            apply_url=item.get("externeUrl") or DETAIL_PAGE.format(refnr=refnr),
            source="Bundesagentur für Arbeit",
            posted_at=to_iso_date(item.get("aktuelleVeroeffentlichungsdatum")
                                  or item.get("eintrittsdatum")),
        ))
    log.info("bundesagentur: %d raw", len(jobs))
    return jobs
