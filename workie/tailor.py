"""Tailor your CV to one job, honestly, and export ATS-friendly DOCX + PDF with no AI metadata.

Usage:
  python -m workie.tailor <job_id>              # job from data/jobs.json (id shown on the board)
  python -m workie.tailor --jd-file posting.txt # any job description saved as text

Needs ANTHROPIC_API_KEY and your master CV in cv/master_cv.md (git-ignored, never uploaded).
Output goes to cv/out/.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CV_DIR = ROOT / "cv"
MASTER = CV_DIR / "master_cv.md"
OUT = CV_DIR / "out"
MODEL = os.getenv("WORKIE_MODEL", "claude-sonnet-5-5")

SYSTEM = """You tailor a CV to a job description. Hard rules:
1. NEVER invent anything. Every job, title, company, date, degree, tool, skill, number and
   achievement must already be in the master CV. Do not inflate numbers or seniority.
2. You MAY: reorder sections, reorder bullets so the most relevant come first, lightly reword a
   bullet to use the job's vocabulary where it is truthfully the same thing (e.g. "built reports"
   -> "built BI dashboards" only if the master CV shows dashboards), drop less relevant bullets,
   and rewrite the summary using only facts from the CV.
3. Where the job wants something the candidate lacks, surface the closest TRUE transferable
   experience instead, and list the gap in notes_for_candidate. Never claim the missing skill.
4. Plain ATS-friendly content: no tables, icons or graphics; standard headings.
Return ONLY JSON matching this shape:
{"name": str, "contact": [str], "summary": str,
 "skills": [{"group": str, "items": [str]}],
 "experience": [{"role": str, "company": str, "location": str, "dates": str, "bullets": [str]}],
 "education": [{"degree": str, "school": str, "dates": str, "details": [str]}],
 "other_sections": [{"heading": str, "lines": [str]}],
 "notes_for_candidate": [str]}"""


# ---------- inputs ----------

def load_job(job_id: str | None, jd_file: str | None) -> tuple[str, str]:
    if jd_file:
        text = Path(jd_file).read_text()
        return Path(jd_file).stem, text
    jobs = json.loads((ROOT / "data" / "jobs.json").read_text())
    for j in jobs:
        if j["id"] == job_id:
            jd = f"{j['title']} at {j['company']} ({j['location']})\n\n{j['description']}"
            return f"{j['company']}-{j['title']}", jd
    sys.exit(f"Job {job_id} not found in data/jobs.json")


def ask_claude(master: str, jd: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content":
                   f"<master_cv>\n{master}\n</master_cv>\n\n<job_description>\n{jd}\n</job_description>"}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        sys.exit("Model did not return JSON:\n" + text[:500])
    return json.loads(m.group(0))


# ---------- honesty guard ----------

def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]{2,}", s.lower()))


def honesty_check(cv: dict, master: str) -> list[str]:
    """Remove skills not in the master CV; flag bullets/roles that don't trace back to it."""
    warnings = []
    master_l = master.lower()
    master_lines = [l.strip("-•* ").strip() for l in master.splitlines() if len(l.strip()) > 20]
    master_words = _words(master)

    for g in cv.get("skills", []):
        keep = []
        for item in g.get("items", []):
            if item.lower() in master_l:
                keep.append(item)
            else:
                warnings.append(f"Removed skill not in master CV: {item}")
        g["items"] = keep
    cv["skills"] = [g for g in cv.get("skills", []) if g["items"]]

    for exp in cv.get("experience", []):
        for f in ("company", "role"):
            if exp.get(f) and exp[f].lower() not in master_l:
                warnings.append(f"CHECK {f} not found verbatim in master CV: {exp[f]}")
        keep = []
        for b in exp.get("bullets", []):
            best = max((difflib.SequenceMatcher(None, b.lower(), l.lower()).ratio() for l in master_lines), default=0)
            new_words = _words(b) - master_words
            if best < 0.35 and len(new_words) > 4:
                warnings.append(f"Removed bullet that doesn't trace back to your CV: {b}")
                continue
            if best < 0.45 or len(new_words) > 4:
                warnings.append(f"CHECK bullet (reworded a lot; new words {sorted(new_words)[:6]}): {b}")
            keep.append(b)
        exp["bullets"] = keep
    return warnings


# ---------- export (ATS-friendly, metadata scrubbed) ----------

def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:60]


def write_docx(cv: dict, path: Path):
    from docx import Document
    from docx.shared import Pt
    from datetime import datetime

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading(cv["name"], level=0)
    doc.add_paragraph(" | ".join(cv.get("contact", [])))
    if cv.get("summary"):
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(cv["summary"])
    if cv.get("skills"):
        doc.add_heading("Skills", level=1)
        for g in cv["skills"]:
            p = doc.add_paragraph()
            p.add_run(f"{g['group']}: ").bold = True
            p.add_run(", ".join(g["items"]))
    if cv.get("experience"):
        doc.add_heading("Experience", level=1)
        for e in cv["experience"]:
            p = doc.add_paragraph()
            p.add_run(f"{e['role']}, {e['company']}").bold = True
            p.add_run(f"  {e.get('location', '')}  {e.get('dates', '')}".rstrip())
            for b in e.get("bullets", []):
                doc.add_paragraph(b, style="List Bullet")
    if cv.get("education"):
        doc.add_heading("Education", level=1)
        for ed in cv["education"]:
            p = doc.add_paragraph()
            p.add_run(f"{ed['degree']}, {ed['school']}").bold = True
            p.add_run(f"  {ed.get('dates', '')}")
            for d in ed.get("details", []):
                doc.add_paragraph(d, style="List Bullet")
    for s in cv.get("other_sections", []):
        doc.add_heading(s["heading"], level=1)
        for line in s.get("lines", []):
            doc.add_paragraph(line, style="List Bullet")

    # Scrub metadata: only your name as author, no tool names, no comments.
    cp = doc.core_properties
    cp.author = cv["name"]
    cp.last_modified_by = cv["name"]
    cp.title = f"{cv['name']} CV"
    for f in ("comments", "keywords", "subject", "category", "content_status", "identifier", "version"):
        setattr(cp, f, "")
    now = datetime.now().replace(microsecond=0)
    cp.created = cp.modified = now
    cp.revision = 1
    doc.save(path)
    _scrub_docx_app_xml(path)


def _scrub_docx_app_xml(path: Path):
    """python-docx's template carries docProps/app.xml naming an application; blank it."""
    import zipfile
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/app.xml":
                data = re.sub(rb"<Application>.*?</Application>", b"<Application></Application>", data)
                data = re.sub(rb"<AppVersion>.*?</AppVersion>", b"", data)
                data = re.sub(rb"<Template>.*?</Template>", b"", data)
                data = re.sub(rb"<Company>.*?</Company>", b"", data)
            zout.writestr(item, data)
    tmp.replace(path)


def write_pdf(cv: dict, path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape as x

    body = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=13)
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, leading=22)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=2)
    bullets = lambda items: ListFlowable([ListItem(Paragraph(x(i), body), leftIndent=10) for i in items],
                                         bulletType="bullet", leftIndent=12, bulletFontSize=7)
    s = [Paragraph(x(cv["name"]), h1), Paragraph(x(" | ".join(cv.get("contact", []))), body)]
    if cv.get("summary"):
        s += [Paragraph("Summary", h2), Paragraph(x(cv["summary"]), body)]
    if cv.get("skills"):
        s.append(Paragraph("Skills", h2))
        s += [Paragraph(f"<b>{x(g['group'])}:</b> {x(', '.join(g['items']))}", body) for g in cv["skills"]]
    if cv.get("experience"):
        s.append(Paragraph("Experience", h2))
        for e in cv["experience"]:
            s.append(Paragraph(f"<b>{x(e['role'])}, {x(e['company'])}</b>  {x(e.get('location', ''))}  {x(e.get('dates', ''))}", body))
            s += [bullets(e.get("bullets", [])), Spacer(1, 4)]
    if cv.get("education"):
        s.append(Paragraph("Education", h2))
        for ed in cv["education"]:
            s.append(Paragraph(f"<b>{x(ed['degree'])}, {x(ed['school'])}</b>  {x(ed.get('dates', ''))}", body))
            if ed.get("details"):
                s.append(bullets(ed["details"]))
    for sec in cv.get("other_sections", []):
        s += [Paragraph(x(sec["heading"]), h2), bullets(sec.get("lines", []))]

    # Metadata: your name only; no creator/producer tool names.
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"{cv['name']} CV", author=cv["name"], subject="", keywords="",
                            creator="", producer="")
    doc.build(s)
    _scrub_pdf(path)


def _scrub_pdf(path: Path):
    """Blank ReportLab's comment banners (same byte length, so the PDF stays valid)."""
    raw = path.read_bytes()
    for m in re.finditer(rb"ReportLab [Gg]enerated PDF document[^\n]*", raw):
        raw = raw[:m.start()] + b" " * (m.end() - m.start()) + raw[m.end():]
    path.write_bytes(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--jd-file")
    a = ap.parse_args(argv)
    if not (a.job_id or a.jd_file):
        ap.error("give a job id or --jd-file")
    if not MASTER.exists():
        sys.exit(f"Put your CV as plain text/markdown in {MASTER}")

    label, jd = load_job(a.job_id, a.jd_file)
    master = MASTER.read_text()
    cv = ask_claude(master, jd)
    warnings = honesty_check(cv, master)

    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / f"{_safe(cv['name'])}_CV_{_safe(label)}"
    write_docx(cv, base.with_suffix(".docx"))
    write_pdf(cv, base.with_suffix(".pdf"))
    report = ["Gaps / notes:"] + [f"  - {n}" for n in cv.get("notes_for_candidate", [])]
    report += ["Honesty check:"] + ([f"  - {w}" for w in warnings] or ["  - all content traces back to your master CV"])
    base.with_suffix(".review.txt").write_text("\n".join(report))
    print(f"Saved {base}.docx and .pdf\n" + "\n".join(report))
    print("\nRead the .docx before sending. Anything marked CHECK needs your eyes.")


if __name__ == "__main__":
    main()
