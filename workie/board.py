"""Build the static job board: site/index.html (served by GitHub Pages)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import Job

SITE = Path(__file__).resolve().parent.parent / "site"

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workie · Berlin student jobs</title>
<style>
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e4e2db;--acc:#1f5f4a;--warn:#9a5b00}
@media(prefers-color-scheme:dark){:root{--bg:#141413;--card:#1f1f1d;--ink:#f0efe9;--mute:#a19f97;--line:#33322f;--acc:#6fc3a3;--warn:#e0a640}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
main{max-width:860px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:24px;margin:0}.sub{color:var(--mute);margin:2px 0 16px;font-size:13px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
input{flex:1 1 220px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font:inherit}
.chip{padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);cursor:pointer;font:inherit;font-size:13px}
.chip.on{background:var(--acc);border-color:var(--acc);color:var(--bg)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:10px}
.t{font-weight:600;font-size:16px}.meta{color:var(--mute);font-size:13px}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);margin-right:4px}
.new{border-color:var(--acc);color:var(--acc)}.flag{color:var(--warn);font-size:12px;margin-top:4px}
details{margin-top:6px}summary{cursor:pointer;color:var(--mute);font-size:13px}
.desc{font-size:13px;white-space:pre-line;max-height:320px;overflow:auto;margin-top:6px}
.act{display:flex;gap:8px;margin-top:10px}
.btn{padding:8px 14px;border-radius:10px;border:1px solid var(--acc);text-decoration:none;font-size:14px;cursor:pointer;font:inherit}
.primary{background:var(--acc);color:var(--bg)}.ghost{background:none;color:var(--acc)}
.empty{color:var(--mute);text-align:center;padding:40px 0}
.rej{font-size:12px;color:var(--mute)}.rej li{margin:2px 0}
</style></head><body><main>
<h1>Workie</h1>
<p class="sub">English student & side jobs in Berlin · updated __UPDATED__ · __COUNT__ verified jobs</p>
<div class="bar"><input id="q" placeholder="Search title, company, skill…" autocomplete="off"></div>
<div class="bar" id="cats"></div>
<div id="list"></div>
<details class="card"><summary>Rejected this run (__REJ__)</summary><ul class="rej" id="rej"></ul></details>
</main>
<script>
const JOBS=__JOBS__, REJ=__REJECTED__, TODAY="__TODAY__";
const cats=["All","Data","Side job","Other student job"];let cat="All";
const esc=s=>(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function render(){
  const q=document.getElementById("q").value.toLowerCase();
  const rows=JOBS.filter(j=>(cat==="All"||j.category===cat)&&(!q||(j.title+" "+j.company+" "+j.description).toLowerCase().includes(q)));
  document.getElementById("list").innerHTML=rows.length?rows.map(j=>`
  <div class="card">
    <div class="t">${esc(j.title)}</div>
    <div class="meta">${esc(j.company)} · ${esc(j.location)} · via ${esc(j.source)}${j.posted_at?" · posted "+j.posted_at:""}</div>
    <div style="margin-top:6px"><span class="tag">${esc(j.category)}</span>${j.first_seen===TODAY?'<span class="tag new">New</span>':""}</div>
    ${j.flags.map(f=>`<div class="flag">⚠ ${esc(f)}</div>`).join("")}
    ${j.description?`<details><summary>Description</summary><div class="desc">${esc(j.description)}</div></details>`:""}
    <div class="act">
      <a class="btn primary" href="${esc(j.apply_url)}" target="_blank" rel="noopener noreferrer">Apply</a>
      <button class="btn ghost" onclick="copyCmd('${j.id}',this)">Tailor CV</button>
    </div>
  </div>`).join(""):'<p class="empty">No jobs match.</p>';
}
function copyCmd(id,b){
  const cmd="python -m workie.tailor "+id;
  navigator.clipboard?.writeText(cmd).then(()=>{b.textContent="Copied: "+cmd;setTimeout(()=>b.textContent="Tailor CV",2500)},()=>prompt("Run this in your repo:",cmd));
}
document.getElementById("cats").innerHTML=cats.map(c=>`<button class="chip${c===cat?" on":""}" data-c="${c}">${c} (${c==="All"?JOBS.length:JOBS.filter(j=>j.category===c).length})</button>`).join("");
document.getElementById("cats").onclick=e=>{const c=e.target.dataset.c;if(!c)return;cat=c;document.querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x.dataset.c===c));render()};
document.getElementById("q").oninput=render;
document.getElementById("rej").innerHTML=REJ.map(r=>`<li>${esc(r.company)} – ${esc(r.title)}: <b>${esc(r.reason)}</b></li>`).join("")||"<li>None</li>";
render();
</script></body></html>"""


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build(jobs: list[Job], rejected: list[dict], today: date) -> Path:
    SITE.mkdir(exist_ok=True)
    html = (TEMPLATE
            .replace("__JOBS__", _js([j.to_dict() for j in jobs]))
            .replace("__REJECTED__", _js(rejected))
            .replace("__TODAY__", today.isoformat())
            .replace("__UPDATED__", today.strftime("%d %b %Y"))
            .replace("__COUNT__", str(len(jobs)))
            .replace("__REJ__", str(len(rejected))))
    out = SITE / "index.html"
    out.write_text(html)
    (SITE / "jobs.json").write_text(_js([j.to_dict() for j in jobs]))
    return out
