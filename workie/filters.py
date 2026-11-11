"""Relevance filters: Berlin, student/side job, English-friendly."""
from __future__ import annotations

import re

from langdetect import DetectorFactory, LangDetectException, detect_langs

from .models import Job

DetectorFactory.seed = 0  # deterministic language detection

# Phrases that make a job a student job even if they only appear in the text.
STRONG_STUDENT = ["working student", "werkstudent", "werkstudentin", "student assistant",
                  "studentische hilfskraft", "student job", "minijob", "mini-job", "aushilfe",
                  "enrolled student", "immatrikuliert", "eingeschrieben"]
PART_TIME = ["part-time", "part time", "teilzeit", "minijob", "mini-job", "aushilfe",
             "20 hours", "20h", "flexible hours", "520", "556", "603", "student"]

GERMAN_REQUIRED = [
    r"flie(ß|ss)end(e|es)?\s+deutsch", r"fluent\s+(in\s+)?german", r"native\s+german",
    r"german\s*\(?\s*(c1|c2|b2)", r"(c1|c2|b2)[\s-]*(level\s+)?german",
    r"german\s+(is\s+)?(required|mandatory|a must|essential)",
    r"(excellent|very good|strong|good)\s+(command of\s+)?german",
    r"(sehr\s+)?gute\s+deutschkenntnisse", r"verhandlungssicher(e|es)?\s+deutsch",
    r"deutsch\s+(auf\s+)?(c1|c2|b2|muttersprach)", r"muttersprache\s+deutsch",
    r"german[- ]speaking", r"must\s+speak\s+german", r"business\s+fluent\s+german",
]
_GERMAN_REQ = re.compile("|".join(GERMAN_REQUIRED), re.I)
_GERMAN_TITLE_WORDS = re.compile(
    r"\b(und|mit|für|im|der|die|das|bereich|mitarbeiter|kaufm|sachbearbeiter|"
    r"verkäufer|reinigungskraft|servicekraft|lagerhelfer|fahrer)\b", re.I)


_SENIOR = re.compile(r"\b(senior|sr\.?|lead|head|principal|staff|director|vp|manager|teamleiter|leitung)\b", re.I)


def _kw(words) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)


def is_berlin(job: Job) -> bool:
    loc = job.location.lower()
    if "berlin" in loc:
        return True
    remote_de = job.remote and (not loc or any(w in loc for w in ("germany", "deutschland", "remote")))
    return remote_de


def english_status(job: Job) -> str:
    """Return 'english', 'german' or 'unknown'."""
    text = job.description
    if len(text) >= 200:
        try:
            langs = detect_langs(text[:3000])
            top = langs[0]
            if top.lang == "en" and top.prob >= 0.7:
                return "english"
            return "german" if top.lang == "de" else "other"
        except LangDetectException:
            pass
    return "german" if _GERMAN_TITLE_WORDS.search(job.title) else "unknown"


def german_required(job: Job) -> bool:
    return bool(_GERMAN_REQ.search(job.description) or _GERMAN_REQ.search(job.title))


def categorize(job: Job, cfg: dict) -> str | None:
    """Return 'Data', 'Side job', 'Other student job', or None if not a student/side job."""
    kw = cfg["keywords"]
    title, text = job.title, f"{job.title} {job.description}"
    # "Senior Data Engineer" is out, but "Working Student Product Manager" stays in.
    if _SENIOR.search(title) and not _kw(kw["student"]).search(title):
        return None
    studentish = bool(_kw(kw["student"]).search(title) or _kw(STRONG_STUDENT).search(text))
    side_title = bool(_kw(kw["side_job"]).search(title))
    part_time = bool(_kw(PART_TIME).search(text))

    if studentish and _kw(kw["data"]).search(title):
        return "Data"
    if side_title and (studentish or part_time):
        return "Side job"
    if studentish:
        return "Other student job"
    return None


def check(job: Job, cfg: dict) -> str | None:
    """Return a rejection reason, or None if the job passes. Sets job.category."""
    if not is_berlin(job):
        return "Not in Berlin"
    cat = categorize(job, cfg)
    if not cat:
        return "Not a student or side job"
    job.category = cat
    if german_required(job):
        return "German required"
    lang = english_status(job)
    if lang in ("german", "other"):
        return "Posting not in English"
    if lang == "unknown":
        job.flags.append("Language not confirmed: check the posting")
    return None
