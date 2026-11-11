"""Feeds real-shaped API payloads through the whole pipeline (no network)."""
import json
from datetime import date

from workie import board, http, store
from workie.run import load_config, process
from workie.sources import arbeitnow, ats, bundesagentur

EN = ("We are looking for a working student to support our analytics team with SQL, Python and "
      "dashboards. You are enrolled at a university and can work up to 20 hours per week. Our "
      "working language is English and German is a plus.")

ARBEITNOW = {"data": [
    {"slug": "a", "company_name": "Datafox GmbH", "title": "Working Student Data Analyst (m/w/d)",
     "description": f"<p>{EN}</p>", "remote": False, "url": "https://www.arbeitnow.com/jobs/companies/datafox/a",
     "tags": ["Data"], "job_types": ["Working Student"], "location": "Berlin", "created_at": 1794382274},
    {"slug": "b", "company_name": "Scam Ltd", "title": "Student job – easy money",
     "description": f"<p>{EN} Contact us on Telegram.</p>", "remote": False,
     "url": "https://www.arbeitnow.com/jobs/companies/scam/b", "tags": [], "job_types": [],
     "location": "Berlin", "created_at": 1794382274},
], "links": {"next": None}}

BA_SEARCH = {"stellenangebote": [
    {"refnr": "10000-1", "titel": "Barista (Minijob) – English speaking café", "arbeitgeber": "Bean There GmbH",
     "arbeitsort": {"ort": "Berlin"}, "aktuelleVeroeffentlichungsdatum": "2026-11-09"}]}
BA_DETAIL = {"stellenangebotsBeschreibung": "Our café in Kreuzberg is hiring a part-time barista on a "
             "minijob basis. Students welcome, flexible hours, English-speaking team, training provided. "
             "You enjoy coffee, are friendly with guests and can work weekend shifts."}

GREENHOUSE = {"jobs": [{"title": "Working Student – Business Intelligence", "company_name": "N26",
              "location": {"name": "Berlin"}, "content": "&lt;p&gt;" + EN + "&lt;/p&gt;",
              "absolute_url": "https://n26.com/en/careers/positions/123", "first_published": "2026-11-01T10:00:00Z"}]}


def fake_get_json(url, params=None, headers=None, **_):
    if "arbeitnow" in url:
        return ARBEITNOW
    if "/pc/v4/jobs" in url:
        return BA_SEARCH if (params or {}).get("was") == "Working Student" else {"stellenangebote": []}
    if "jobdetails" in url:
        return BA_DETAIL
    if "greenhouse" in url:
        return GREENHOUSE
    return None


def test_full_run(monkeypatch, tmp_path):
    for mod in (arbeitnow, bundesagentur, ats):
        monkeypatch.setattr(mod, "get_json", fake_get_json)
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.setattr(store, "JOBS", tmp_path / "jobs.json")
    monkeypatch.setattr(store, "REJECTED", tmp_path / "rejected.json")
    monkeypatch.setattr(board, "SITE", tmp_path / "site")

    cfg = load_config()
    today = date(2026, 11, 11)
    raw = arbeitnow.fetch(cfg) + bundesagentur.fetch(cfg) + ats.fetch(cfg)
    kept, rejected = process(raw, cfg, today)

    titles = {j.title: j.category for j in kept}
    assert titles == {"Working Student Data Analyst (m/w/d)": "Data",
                      "Barista (Minijob) – English speaking café": "Side job",
                      "Working Student – Business Intelligence": "Data"}
    assert [r["reason"] for r in rejected] == ["Asks to apply via Telegram"]

    db, new = store.merge(store.load(), kept, today)
    assert new == 3
    store.save(db, rejected, today)
    html = board.build(store.visible(db, today, 3), rejected, today).read_text()
    assert "Datafox" in html and "3 verified jobs" in html

    # second day: same jobs are not "new"
    db2, new2 = store.merge(store.load(), kept, date(2026, 11, 12))
    assert new2 == 0 and len(db2) == 3
