import zipfile

from workie import tailor

MASTER = """# Alex Sample
alex@example.com | Berlin
## Skills
Python, SQL, dbt, Metabase, Airflow
## Experience
### Analytics Engineer, Foo Technologies (2023-2025)
- Built dbt models and Metabase dashboards used by sales and operations teams
- Automated daily reporting pipelines in Airflow, cutting manual work for the team
- Worked with customers to collect requirements for new data products
## Education
BSc Economics, University of Lagos
"""

MODEL_OUT = {
    "name": "Alex Sample", "contact": ["alex@example.com", "Berlin"],
    "summary": "Analytics engineer with dbt, SQL and Python experience.",
    "skills": [{"group": "Data", "items": ["Python", "SQL", "dbt", "Tableau"]}],
    "experience": [{"role": "Analytics Engineer", "company": "Foo Technologies", "location": "Lagos",
                    "dates": "2023-2025", "bullets": [
                        "Built dbt models and Metabase dashboards used by sales and operations teams",
                        "Led a team of 12 engineers deploying Kubernetes clusters on AWS globally"]}],
    "education": [{"degree": "BSc Economics", "school": "University of Lagos", "dates": "", "details": []}],
    "other_sections": [], "notes_for_candidate": ["Job asks for Tableau; you have Metabase."]}


def test_honesty_and_export(tmp_path):
    cv = {**MODEL_OUT, "skills": [dict(g) for g in MODEL_OUT["skills"]]}
    warnings = tailor.honesty_check(cv, MASTER)
    assert "Tableau" not in cv["skills"][0]["items"]          # invented skill removed
    assert any("Removed skill" in w and "Tableau" in w for w in warnings)
    assert any(w.startswith("Removed bullet") and "Kubernetes" in w for w in warnings)  # invented bullet removed
    assert len(cv["experience"][0]["bullets"]) == 1
    assert not any("Built dbt models" in w for w in warnings)  # real bullet passes

    docx, pdf = tmp_path / "cv.docx", tmp_path / "cv.pdf"
    tailor.write_docx(cv, docx)
    tailor.write_pdf(cv, pdf)

    with zipfile.ZipFile(docx) as z:
        meta = (z.read("docProps/core.xml") + z.read("docProps/app.xml")).decode()
    for bad in ("python-docx", "Microsoft", "Claude", "Anthropic", "AI"):
        assert bad not in meta, bad
    assert "Alex Sample" in meta

    raw = pdf.read_bytes()
    for bad in (b"ReportLab", b"reportlab", b"Claude", b"Anthropic"):
        assert bad not in raw, bad
