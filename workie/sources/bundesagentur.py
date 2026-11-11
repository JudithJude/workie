"""Bundesagentur für Arbeit Jobsuche API (official German job board, public key).

The BA moves this API between versions without notice, so we try several search
endpoints and read field names defensively.
"""
import base64
import logging

from ..http import get_json
from ..models import Job, to_iso_date

log = logging.getLogger("workie")
BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}
SEARCH_PATHS = ["/pc/v6/jobs", "/pc/v4/app/jobs", "/pc/v4/jobs"]
DETAIL_PATHS = ["/pc/v4/jobdetails/{code}", "/pc/v3/jobdetails/{code}"]
DETAIL_PAGE = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
DESC_KEYS = ("stellenangebotsBeschreibung", "stellenbeschreibung", "beschreibung")

_working_path = None


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return default


def _items(data) -> list[dict]:
    if not isinstance(data, dict):
        return []
    for k in ("stellenangebote", "ergebnisse", "jobs", "results"):
        if isinstance(data.get(k), list):
            return data[k]
    lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
    return lists[0] if lists else []


def _search(params):
    global _working_path
    paths = [_working_path] if _working_path else SEARCH_PATHS
    for p in paths:
        data = get_json(f"{BASE}{p}", params=params, headers=HEADERS, retries=2)
        if data is not None:
            if _working_path is None:
                _working_path = p
                items = _items(data)
                log.info("bundesagentur: using %s; top keys %s; item keys %s",
                         p, list(data)[:8], list(items[0])[:15] if items else [])
            return _items(data)
    return []


def _location(item: dict) -> str:
    ort = item.get("arbeitsort")
    if isinstance(ort, dict):
        return ort.get("ort", "")
    orte = item.get("arbeitsorte")
    if isinstance(orte, list) and orte and isinstance(orte[0], dict):
        return orte[0].get("ort", "")
    return _first(item, "ort", "arbeitsortOrt")


def _description(refnr: str) -> str:
    code = base64.b64encode(refnr.encode()).decode()
    for p in DETAIL_PATHS:
        d = get_json(BASE + p.format(code=code), headers=HEADERS, retries=1)
        if isinstance(d, dict) and d:
            for k in DESC_KEYS:
                if isinstance(d.get(k), str):
                    return d[k]
            strings = [v for v in d.values() if isinstance(v, str)]
            return max(strings, key=len, default="")
    return ""


def fetch(cfg: dict) -> list[Job]:
    c = cfg.get("bundesagentur", {})
    if not c.get("enabled", True):
        return []
    base = {"wo": c.get("where", "Berlin"), "umkreis": c.get("radius_km", 25),
            "angebotsart": 1, "size": 100, "page": 1}
    raw = {}
    for q in c.get("queries", []):
        for item in _search({**base, "was": q}):
            raw[_first(item, "refnr", "referenznummer")] = item
    if c.get("minijob"):
        for item in _search({**base, "arbeitszeit": "mj"}):
            raw[_first(item, "refnr", "referenznummer")] = item

    jobs = []
    budget = c.get("max_details", 60)
    for refnr, item in raw.items():
        if not refnr:
            continue
        desc = ""
        if budget > 0:
            desc = _description(refnr)
            budget -= 1
        jobs.append(Job(
            title=_first(item, "titel", "stellenangebotsTitel", "beruf"),
            company=_first(item, "arbeitgeber", "arbeitgeberName", "firma"),
            location=_location(item),
            description=desc,
            # Official BA page; it links on to the employer's own application.
            apply_url=item.get("externeUrl") or DETAIL_PAGE.format(refnr=refnr),
            source="Bundesagentur für Arbeit",
            posted_at=to_iso_date(_first(item, "aktuelleVeroeffentlichungsdatum",
                                         "veroeffentlichungsdatum", "modifikationsTimestamp",
                                         "eintrittsdatum", default=None)),
        ))
    log.info("bundesagentur: %d raw", len(jobs))
    return jobs
