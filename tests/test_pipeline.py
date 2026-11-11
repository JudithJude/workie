from datetime import date

import pytest

from workie import filters, fraud
from workie.models import Job
from workie.run import load_config, process

CFG = load_config()
TODAY = date(2026, 11, 11)
EN = ("We are looking for a working student to support our analytics team. You will build "
      "dashboards in SQL and Python, clean data, and help the team answer business questions. "
      "You are enrolled at a university in Berlin and can work 20 hours per week. English is our "
      "working language; German is a plus but not required.")


def job(**kw):
    base = dict(title="Working Student Data Analytics (m/f/d)", company="Acme Analytics GmbH",
                location="Berlin", description=EN, apply_url="https://job-boards.greenhouse.io/acme/jobs/1",
                source="test", posted_at="2026-11-05")
    base.update(kw)
    return Job(**base)


def reason(j):
    return filters.check(j, CFG) or fraud.check(j, CFG, TODAY)


def test_good_data_job_passes():
    j = job()
    assert reason(j) is None
    assert j.category == "Data"


def test_side_job_category():
    j = job(title="Barista (part-time, students welcome)",
            description=EN.replace("analytics team", "cafe team"))
    assert reason(j) is None
    assert j.category == "Side job"


@pytest.mark.parametrize("kw,expected", [
    (dict(location="Munich"), "Not in Berlin"),
    (dict(title="Senior Data Engineer"), "Not a student or side job"),
    (dict(description=EN + " Fluent German (C1) is required."), "German required"),
    (dict(description=EN + " Sehr gute Deutschkenntnisse."), "German required"),
    (dict(apply_url="https://bit.ly/abc"), "Apply link on untrusted domain"),
    (dict(apply_url=""), "No apply link"),
    (dict(company=""), "No identifiable company"),
    (dict(description=EN + " Apply via WhatsApp +49 151 000000."), "Asks to apply via WhatsApp"),
    (dict(description=EN + " A small registration fee of 50 EUR applies."), "Asks for a fee"),
    (dict(description=EN + " Please send your bank details and a copy of your passport."), "Asks for bank details"),
    (dict(description=EN + " Contact hr.acme.jobs@gmail.com"), "Contact is a personal email address"),
    (dict(description=EN + " Pay: 95 €/hour."), "Unrealistic hourly pay"),
    (dict(posted_at="2026-08-01"), "Posting too old"),
])
def test_rejections(kw, expected):
    assert (reason(job(**kw)) or "").startswith(expected)


def test_german_posting_rejected():
    de = ("Wir suchen eine Werkstudentin oder einen Werkstudenten für unser Analytics-Team. Du "
          "unterstützt bei der Erstellung von Berichten und Dashboards und arbeitest eng mit dem "
          "Controlling zusammen. Du bist an einer Hochschule in Berlin eingeschrieben.")
    assert reason(job(title="Werkstudent Data Analytics", description=de)) == "Posting not in English"


def test_employer_own_domain_trusted():
    assert reason(job(apply_url="https://careers.acmeanalytics.com/jobs/42")) is None


def test_normal_pay_ok():
    assert reason(job(description=EN + " We pay 15 €/hour.")) is None


def test_dedupe_by_company_and_title():
    a = job()
    b = job(title="Working Student Data Analytics (w/m/d)", source="other")
    kept, _ = process([a, b], CFG, TODAY)
    assert len(kept) == 1


def test_bi_does_not_match_bike():
    # "bi" must be a whole word, so "Bike courier" is a side job, not a data job
    j = job(title="Bike courier (minijob)", description=EN.replace("analytics team", "delivery team"))
    assert reason(j) is None
    assert j.category == "Side job"


def test_student_manager_title_kept():
    j = job(title="Working Student Product Manager")
    assert reason(j) is None


def test_lookalike_domain_rejected():
    # "acme" inside an unrelated domain must not count as the employer's site
    assert reason(job(apply_url="https://jobs-acme-hiring.xyz/apply")).startswith("Apply link on untrusted domain")
