from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_text(raw: str | None) -> str:
    """Strip HTML (including escaped HTML) and collapse whitespace."""
    if not raw:
        return ""
    text = html.unescape(html.unescape(raw))
    text = _TAG.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\((m|f|w|d|x|all genders?)(/[mfwdx])*\)", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@dataclass
class Job:
    title: str
    company: str
    location: str
    description: str
    apply_url: str
    source: str
    posted_at: str | None = None          # ISO date YYYY-MM-DD
    remote: bool = False
    category: str = ""                    # "Data" | "Side job" | "Other"
    flags: list[str] = field(default_factory=list)  # soft warnings shown on board
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        self.title = clean_text(self.title)
        self.company = clean_text(self.company)
        self.location = clean_text(self.location)
        self.description = clean_text(self.description)

    @property
    def id(self) -> str:
        key = f"{_norm(self.company)}|{_norm(self.title)}"
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        d = {k: v for k, v in d.items() if k != "id"}
        return cls(**d)


def to_iso_date(value) -> str | None:
    """Accept unix seconds/ms, ISO strings or dates; return YYYY-MM-DD."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 1e12 else value
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, OSError):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", str(value))
        return m.group(1) if m else None
