"""Duplicate job detection (spec section 14).

Signals, strongest first: same source + external id, same canonical URL, then same company with
a near-identical title, compatible location and similar description text. Matching jobs collapse
into one canonical record that keeps every source reference.
"""

import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

_COMPANY_SUFFIX = re.compile(
    r"\b(inc|ltd|llc|pvt|private|limited|corp|corporation|co|plc|gmbh|technologies|technology|"
    r"solutions|software|services|india|global)\b\.?")


def company_key(name: str) -> str:
    s = _COMPANY_SUFFIX.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9]+", "", s)


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return None
    host = parts.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parts.path) or "/"
    # Tracking parameters and fragments never identify a different job.
    return urlunsplit(("https", host, path.lower(), "", ""))


def _norm_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)  # "(Remote)", "[Hyderabad]"
    t = re.sub(r"\b(sr|snr)\b\.?", "senior", t)
    t = re.sub(r"\b(jr)\b\.?", "junior", t)
    return re.sub(r"[^a-z0-9+#]+", " ", t).strip()


def _shingles(text: str, k: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9+#]+", text.lower())
    return {tuple(words[i:i + k]) for i in range(max(len(words) - k + 1, 1))} if words else set()


def text_similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm_title(a), _norm_title(b)).ratio()


def _loc_compatible(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True
    ta = set(re.findall(r"[a-z]+", a.lower())) - {"india", "remote", "hybrid", "office"}
    tb = set(re.findall(r"[a-z]+", b.lower())) - {"india", "remote", "hybrid", "office"}
    return not ta or not tb or bool(ta & tb)


def is_duplicate(candidate: dict, existing: dict) -> tuple[bool, str]:
    for src in existing.get("sources", []):
        if candidate.get("source_job_id") and src.get("source") == candidate.get("source") and \
                src.get("source_job_id") == candidate.get("source_job_id"):
            return True, "same source job id"
        if candidate.get("url_key") and src.get("url_key") == candidate["url_key"]:
            return True, "same job URL"
    if candidate.get("company_key") != existing.get("company_key"):
        return False, ""
    t_sim = title_similarity(candidate["title"], existing["title"])
    d_sim = text_similarity(candidate.get("description", ""), existing.get("description", ""))
    if t_sim >= 0.9 and _loc_compatible(candidate.get("location"), existing.get("location")) and d_sim >= 0.5:
        return True, f"same company, title {t_sim:.0%} and description {d_sim:.0%} similar"
    if t_sim >= 0.75 and d_sim >= 0.85:
        return True, f"same company, description {d_sim:.0%} identical"
    return False, ""
