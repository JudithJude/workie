"""Fraud and legitimacy checks. Any hard flag rejects the job."""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlparse

from .models import Job

RED_FLAGS = {
    r"\bwhats\s?app\b": "Asks to apply via WhatsApp",
    r"\btelegram\b": "Asks to apply via Telegram",
    r"\b(signal|wechat)\s+(me|us|number)\b": "Asks to apply via messaging app",
    r"(registration|processing|training|application|onboarding|starter)\s+(fee|kit|payment)": "Asks for a fee",
    r"\b(pay|send)\s+(us\s+)?(a\s+)?(fee|deposit)\b": "Asks for a fee",
    r"(bank|account)\s+(details|information|number)": "Asks for bank details",
    r"\b(iban|routing number)\b": "Asks for bank details",
    r"(send|upload|provide)\s+(a\s+)?(copy\s+of\s+)?(your\s+)?(passport|id card|ausweis|social security)": "Asks for ID up front",
    r"\b(western union|moneygram|gift ?cards?|bitcoin|crypto(currency)? (payment|wallet))\b": "Payment red flag",
    r"\b(reshipping|re-shipping|package forwarding|parcel forwarding)\b": "Reshipping scam pattern",
    r"(no experience|no interview).{0,40}(€|eur|euro)\s?\d{3,}\s?(per|/)\s?(day|week)": "Unrealistic pay promise",
    r"\b(earn|verdienen)\s+(up to\s+)?(€|eur)?\s?\d{3,}\s?(€|eur)?\s?(per|/|pro)\s?(day|tag)\b": "Unrealistic pay promise",
}
_RED = [(re.compile(p, re.I), reason) for p, reason in RED_FLAGS.items()]
_FREEMAIL = re.compile(r"[\w.+-]+@(gmail|googlemail|yahoo|hotmail|outlook|gmx|web|icloud|aol|proton(mail)?)\.\w+", re.I)
_HOURLY = re.compile(r"(€|eur)\s?(\d{2,3})(?:[.,]\d+)?\s?(?:/|per|pro)\s?(?:hour|hr|h|stunde|std)\b"
                     r"|(\d{2,3})(?:[.,]\d+)?\s?(?:€|eur|euro)\s?(?:/|per|pro)\s?(?:hour|hr|h|stunde|std)\b", re.I)
MAX_STUDENT_HOURLY = 45


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _company_tokens(company: str) -> list[str]:
    stop = {"gmbh", "ag", "se", "kg", "ug", "co", "the", "group", "berlin", "germany", "deutschland", "inc", "ltd"}
    return [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) >= 3 and t not in stop]


ATS_SOURCES = ("(Greenhouse)", "(Lever)", "(Ashby)")


def trusted_apply_url(job: Job, trusted_hosts: list[str]) -> bool:
    host = _host(job.apply_url)
    if not host or not job.apply_url.startswith("https://"):
        return False
    if job.source.endswith(ATS_SOURCES):
        return True  # link came from the employer's own applicant-tracking board
    if any(host == h or host.endswith("." + h) for h in trusted_hosts):
        return True
    # Employer's own domain, e.g. careers.zalando.com for "Zalando SE", n26.com for "N26".
    labels = host.split(".")[:-1]  # drop TLD
    return any(lbl == t or (len(t) >= 4 and lbl.startswith(t))
               for t in _company_tokens(job.company) for lbl in labels)


def check(job: Job, cfg: dict, today: date | None = None) -> str | None:
    """Return a rejection reason, or None if the job looks legitimate."""
    today = today or date.today()
    text = f"{job.title} {job.description}"

    if len(job.company) < 2 or job.company.lower() in {"confidential", "anonymous", "n/a", "unknown"}:
        return "No identifiable company"
    if not job.apply_url:
        return "No apply link"
    if not trusted_apply_url(job, cfg.get("trusted_apply_hosts", [])):
        return f"Apply link on untrusted domain ({_host(job.apply_url) or 'invalid'})"
    for rx, reason in _RED:
        if rx.search(text):
            return reason
    if _FREEMAIL.search(text):
        return "Contact is a personal email address"
    for m in _HOURLY.finditer(text):
        val = int(m.group(2) or m.group(3))
        if val > MAX_STUDENT_HOURLY:
            return f"Unrealistic hourly pay (€{val}/h)"
    if job.posted_at:
        if date.fromisoformat(job.posted_at) < today - timedelta(days=cfg.get("max_age_days", 30)):
            return "Posting too old"
    else:
        job.flags.append("Posting date unknown")
    return None
