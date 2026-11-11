from workie.sources import bundesagentur, firecrawl_pages
from workie.run import load_config


def test_employer_link_prefers_ats():
    links = ["/jobs/other", "https://www.linkedin.com/company/x", "https://deliveryhero.com",
             "https://job-boards.greenhouse.io/deliveryhero/jobs/123"]
    got = firecrawl_pages._employer_link(links, "Delivery Hero", "https://www.workingstudentjobs.de/job/1")
    assert got == "https://job-boards.greenhouse.io/deliveryhero/jobs/123"


def test_employer_link_company_careers_site():
    links = ["https://careers.ionos.com/job/working-student-security", "https://twitter.com/ionos"]
    got = firecrawl_pages._employer_link(links, "IONOS", "https://www.workingstudentjobs.de/job/2")
    assert got == "https://careers.ionos.com/job/working-student-security"


def test_employer_link_none():
    assert firecrawl_pages._employer_link(["https://www.workingstudentjobs.de/x"], "Foo", "https://www.workingstudentjobs.de/j") == ""


def test_bundesagentur_v6_shape(monkeypatch):
    bundesagentur._working_path = None
    def fake(url, params=None, headers=None, **_):
        if url.endswith("/pc/v6/jobs"):
            return {"ergebnisse": [{"referenznummer": "123-X", "stellenangebotsTitel": "Working Student Data",
                                    "arbeitgeberName": "Foo GmbH", "arbeitsorte": [{"ort": "Berlin"}],
                                    "veroeffentlichungsdatum": "2026-11-10"}]}
        if "jobdetails" in url:
            return {"stellenangebotsBeschreibung": "English description"}
        return None
    monkeypatch.setattr(bundesagentur, "get_json", fake)
    jobs = bundesagentur.fetch(load_config())
    assert len(jobs) == 1
    j = jobs[0]
    assert (j.title, j.company, j.location, j.posted_at, j.description) == \
        ("Working Student Data", "Foo GmbH", "Berlin", "2026-11-10", "English description")
    assert j.apply_url.endswith("/123-X")


def test_firecrawl_enriches_new_jobs(monkeypatch, tmp_path):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setattr(firecrawl_pages, "CACHE", tmp_path / "cache.json")
    calls = []
    def fake_post(url, payload, headers=None, **_):
        calls.append(payload["url"])
        if payload["url"].endswith("/listing"):
            return {"data": {"json": {"jobs": [{"title": "Working Student BI", "company": "Metergrid",
                                                 "job_url": "/job/9"}]}}}
        return {"data": {"markdown": "We are hiring a working student in Berlin. English is our language.",
                         "links": ["https://metergrid.jobs.personio.de/job/9"]}}
    monkeypatch.setattr(firecrawl_pages, "post_json", fake_post)
    cfg = load_config(); cfg["firecrawl"]["delay_seconds"] = 0; cfg["firecrawl"]["urls"] = ["https://www.workingstudentjobs.de/berlin/listing"]
    jobs = firecrawl_pages.fetch(cfg)
    assert calls == ["https://www.workingstudentjobs.de/berlin/listing", "https://www.workingstudentjobs.de/job/9"]
    assert jobs[0].apply_url == "https://metergrid.jobs.personio.de/job/9"
    assert "English is our language" in jobs[0].description

    # second run: page comes from cache, no detail scrape
    calls.clear()
    jobs = firecrawl_pages.fetch(cfg)
    assert calls == ["https://www.workingstudentjobs.de/berlin/listing"]
    assert jobs[0].apply_url == "https://metergrid.jobs.personio.de/job/9"
