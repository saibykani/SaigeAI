"""Fetch a job description from a public ATS job link (Greenhouse, Lever, Ashby) via their official public APIs.

No scraping: only the documented public job-board endpoints are called. Other sites (LinkedIn, Naukri, Indeed)
are not fetched; the user pastes the text instead."""

import html
import re

from app.careers.providers import http_client

_GH = re.compile(r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/([\w-]+)/jobs/(\d+)", re.I)
_GH_EMBED = re.compile(r"greenhouse\.io/embed/job_app\?(?:.*&)?for=([\w-]+)&(?:.*&)?token=(\d+)", re.I)
_LEVER = re.compile(r"https?://jobs\.(?:eu\.)?lever\.co/([\w.-]+)/([0-9a-f-]{36})", re.I)
_ASHBY = re.compile(r"https?://jobs\.ashbyhq\.com/([\w.%-]+)/([0-9a-f-]{36})", re.I)


class JobLinkError(Exception):
    pass


def _text(markup: str) -> str:
    s = html.unescape(markup or "")
    s = re.sub(r"(?i)<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", s)
    s = re.sub(r"(?i)<\s*li[^>]*>", "• ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def _nice(board: str) -> str:
    return re.sub(r"[-_]+", " ", board).strip().title()


def supported(url: str) -> bool:
    return any(rx.search(url or "") for rx in (_GH, _GH_EMBED, _LEVER, _ASHBY))


async def fetch(url: str) -> dict:
    """{jd_text, title, company, source} for a supported job link, else JobLinkError."""
    url = (url or "").strip()
    async with http_client() as c:
        if m := (_GH.search(url) or _GH_EMBED.search(url)):
            board, jid = m.group(1), m.group(2)
            r = await c.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}")
            if r.status_code != 200:
                raise JobLinkError("Greenhouse didn't return this job. It may be closed.")
            d = r.json()
            company = (d.get("company_name") or "").strip() or _nice(board)
            loc = (d.get("location") or {}).get("name") or ""
            body = _text(d.get("content") or "")
            return {"jd_text": f"{d.get('title', '')}\n{loc}\n\n{body}".strip(), "title": d.get("title") or "", "company": company,
                    "source": "greenhouse"}
        if m := _LEVER.search(url):
            org, jid = m.group(1), m.group(2)
            r = await c.get(f"https://api.lever.co/v0/postings/{org}/{jid}")
            if r.status_code != 200:
                raise JobLinkError("Lever didn't return this job. It may be closed.")
            d = r.json()
            desc = d.get("descriptionPlain") or _text(d.get("description") or "")
            parts = [d.get("text") or "", (d.get("categories") or {}).get("location") or "", "", desc]
            for lst in d.get("lists") or []:
                parts += ["", lst.get("text") or "", _text(lst.get("content") or "")]
            parts += ["", d.get("additionalPlain") or ""]
            return {"jd_text": "\n".join(parts).strip(), "title": d.get("text") or "", "company": _nice(org), "source": "lever"}
        if m := _ASHBY.search(url):
            org, jid = m.group(1), m.group(2)
            r = await c.get(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
            if r.status_code != 200:
                raise JobLinkError("Ashby didn't return this job board.")
            job = next((j for j in r.json().get("jobs", []) if j.get("id") == jid or jid in (j.get("jobUrl") or "")), None)
            if not job:
                raise JobLinkError("This Ashby job isn't listed any more.")
            body = job.get("descriptionPlain") or _text(job.get("descriptionHtml") or "")
            return {"jd_text": f"{job.get('title', '')}\n{job.get('location', '')}\n\n{body}".strip(), "title": job.get("title") or "",
                    "company": _nice(org), "source": "ashby"}
    raise JobLinkError("Paste a Greenhouse, Lever or Ashby job link. For LinkedIn, Naukri or other sites, paste the job text instead.")
