# Workie: Berlin student job board

A daily pipeline that collects **English-language student and side jobs in Berlin**, drops anything fraudulent or German-required, and publishes a job board on GitHub Pages. A local script tailors your CV to a job, honestly, and exports ATS-friendly files with no AI metadata.

```
Sources ──► normalize ──► filter ──► fraud check ──► dedupe ──► data/jobs.json ──► site/index.html
 Arbeitnow API              Berlin      trusted apply link    company+title        (GitHub Pages)
 Bundesagentur API          student/    no fees/bank/ID/WhatsApp
 Employer ATS (Greenhouse,  side job    no personal emails
   Lever, Ashby)            English     realistic pay, ≤30 days old
 Firecrawl (listing pages)  no German req.
```

## Setup (about 10 minutes)

1. **Create a GitHub repo** and push this folder. Make it **public** if you're on a free plan; GitHub Pages on private repos needs a paid plan. Your CV never goes to GitHub (`cv/` is git-ignored).
   ```bash
   git init && git add . && git commit -m "Workie"
   git branch -M main
   git remote add origin https://github.com/<you>/workie.git
   git push -u origin main
   ```
2. **Add your Firecrawl key** under Settings → Secrets and variables → Actions → New secret, named `FIRECRAWL_API_KEY`. It's optional; without it the Firecrawl source is skipped.
3. **Turn on Pages:** Settings → Pages → Source: **GitHub Actions**.
4. **First run:** Actions → *Daily job refresh* → **Run workflow**. Your board is then live at `https://<you>.github.io/workie/`.

After that it runs every morning (~06:17 Berlin).

## Tailoring your CV

```bash
pip install -r requirements.txt
# put your full CV as text/markdown in cv/master_cv.md
export ANTHROPIC_API_KEY=sk-ant-...
git pull                                  # get today's jobs
python -m workie.tailor <job_id>          # "Tailor CV" on the board copies this command
python -m workie.tailor --jd-file job.txt # or any job description you saved
```

Output is in `cv/out/`: a `.docx`, a `.pdf` and a `.review.txt`.

- **No lying.** Claude may only reorder, trim and lightly reword what's in your master CV. A code check then removes any skill that isn't in your CV and any bullet that doesn't trace back to one of yours, and flags heavy rewording as `CHECK`.
- **Gaps** the job asks for that you don't have are listed in the review file, not added to the CV.
- **ATS-friendly:** single column, standard headings, real text (no tables or images).
- **Clean metadata:** the author is your name only. There are no tool names (python-docx, ReportLab, Microsoft, Claude) and no comments or keywords.

Read the `.docx` before you send it.

## Tuning (`config.yaml`)

- **Add employers:** put a company's board token under `ats:`. For example, `job-boards.greenhouse.io/zalando` gives the token `zalando` under `greenhouse:`. These links come from the employer itself, so they're the most trustworthy source.
- **Add pages for Firecrawl** under `firecrawl.urls`.
- **Keywords** for data roles and side jobs (barista, warehouse, delivery, etc.) are under `keywords:`.
- **Trusted apply domains:** `trusted_apply_hosts:`. Jobs whose apply link goes anywhere else are rejected, unless the link is on the employer's own domain.

Every run lists what it rejected and why at the bottom of the board, so you can check it isn't too strict.

## Notes

- **LinkedIn, Indeed and Glassdoor aren't scraped**, because their terms forbid it and they block bots. Their links are still trusted when another source points to them.
- **Bundesagentur listings** are mostly in German, so most get filtered out. The few English ones that remain are usually good.
- **Firecrawl cost:** 3 pages a day uses roughly 15–30 credits a day.
- **Tests:** `python -m pytest`.
