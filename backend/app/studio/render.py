"""Resume templates and file formats for ATS Studio.

Every template is single column with standard section headings and real, selectable text (no tables,
images or text boxes), so applicant tracking systems parse it reliably. Templates differ in typography,
colour, header style and section order. Formats: DOCX (python-docx), PDF (dependency-free writer with the
standard PDF fonts), HTML, Markdown and plain text.
"""

import html
import io
import re
import zlib
from dataclasses import dataclass

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.schemas.resume import ParsedResume
from app.studio import fontmetrics as fm


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    font: str                      # DOCX / HTML font
    pdf_font: str                  # "Helvetica" or "Times"
    accent: tuple[int, int, int]
    name_size: int
    body_size: float
    centered: bool
    order: tuple[str, ...]
    heading: str                   # "rule" (line under), "bar" (accent bar left), "plain", "caps"
    band: bool = False             # dark header band with the name in white
    compact: bool = False


ORDER = ("summary", "skills", "experience", "projects", "education", "certifications")
SKILLS_FIRST = ("summary", "skills", "experience", "projects", "certifications", "education")
TEMPLATES = {t.id: t for t in (
    Template("modern", "Modern", "Sans-serif, deep-green accent, thin rules, dates on the right. A clean all-rounder.",
             "Calibri", "Helvetica", (22, 101, 52), 24, 10.5, False, ORDER, "rule"),
    Template("banner", "Banner", "Dark header band with your name in white, orange section bars. Stands out, still ATS-safe.",
             "Calibri", "Helvetica", (194, 65, 12), 24, 10.5, False, SKILLS_FIRST, "bar", band=True),
    Template("classic", "Classic", "Centered serif name, black headings with rules. Safe for every recruiter and ATS.",
             "Georgia", "Times", (25, 25, 25), 22, 10.5, True, ORDER, "rule"),
    Template("minimal", "Minimal", "Lots of white space, small-caps headings, one quiet accent.",
             "Helvetica", "Helvetica", (64, 64, 64), 22, 10, False, ORDER, "caps"),
    Template("skills_first", "Skills-first", "Key skills for this job right under your name: best for QA, SDET and engineering roles.",
             "Calibri", "Helvetica", (126, 34, 206), 22, 10.5, False, SKILLS_FIRST, "bar"),
    Template("executive", "Executive", "Large serif name, generous spacing, summary-led. For senior roles.",
             "Garamond", "Times", (120, 53, 15), 26, 11, True, ORDER, "rule"),
    Template("compact", "Compact", "Tighter spacing and smaller type: fits more on one page.",
             "Arial", "Helvetica", (40, 40, 40), 18, 9.5, False, ORDER, "plain", compact=True),
)}
FORMATS = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "pdf": "application/pdf",
           "html": "text/html; charset=utf-8", "md": "text/markdown; charset=utf-8", "txt": "text/plain; charset=utf-8"}
HEADINGS = {"summary": "Professional Summary", "skills": "Skills", "experience": "Experience", "projects": "Projects",
            "education": "Education", "certifications": "Certifications"}


# ------------------------------------------------------------------ neutral structure

def _contact(r: ParsedResume) -> list[str]:
    links = [re.sub(r"^https?://(www\.)?", "", x).rstrip("/") for x in (r.links.linkedin, r.links.github, r.links.portfolio) if x]
    return [x for x in (r.email, r.phone, r.location) if x] + links


def _dates(e) -> str:
    return " – ".join(x for x in (e.start_date, "Present" if e.is_current else e.end_date) if x)


def _edu(ed) -> tuple[str, str]:
    deg = f"{ed.degree} in {ed.field}" if ed.field and ed.degree else (ed.degree or ed.raw or "")
    years = " – ".join(str(y) for y in (ed.start_year, ed.end_year) if y)
    return ", ".join(x for x in (deg, ed.institution) if x), years


Row = tuple[str, str, str]  # (kind, text, right-hand text)


def sections(r: ParsedResume, t: Template) -> list[tuple[str, list[Row]]]:
    """[(heading, rows)]; kind: p paragraph, b bullet, h item heading (right = dates), s sub-line (italic), k key/value line."""
    out = []
    for key in t.order:
        rows: list[Row] = []
        if key == "summary" and r.summary:
            rows = [("p", r.summary, "")]
        elif key == "skills" and r.skills:
            from app.studio.polish import group_skills

            key_skills = [s for s in r.tools if s in r.skills]
            if len(key_skills) >= 2:
                rows.append(("k", "Core skills for this role: " + ", ".join(key_skills), ""))
            groups = group_skills(r.skills)
            if len(groups) <= 1:
                rows.append(("p", ", ".join(r.skills), ""))
            else:
                rows += [("k", f"{label}: " + ", ".join(items), "") for label, items in groups]
        elif key == "experience":
            for e in r.experience:
                rows.append(("h", e.title or e.company or "", _dates(e)))
                sub = " · ".join(x for x in (e.company if e.title else None, e.location) if x)
                if sub:
                    rows.append(("s", sub, ""))
                rows += [("b", b, "") for b in e.achievements + e.responsibilities]
                if e.technologies:
                    rows.append(("s", "Tools: " + ", ".join(e.technologies), ""))
        elif key == "projects":
            for pr in r.projects:
                rows.append(("h", pr.name, ""))
                if pr.technologies:
                    rows.append(("s", ", ".join(pr.technologies), ""))
                rows += [("b", h, "") for h in pr.highlights]
        elif key == "education":
            rows = [("h", *_edu(ed)) for ed in r.education]
        elif key == "certifications":
            rows = [("b", c, "") for c in r.certifications]
        if rows:
            out.append((HEADINGS[key], rows))
    return out


# ------------------------------------------------------------------ DOCX

def _shade(paragraph, hex_fill: str) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    for k, v in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", hex_fill)):
        shd.set(qn(k), v)
    ppr.append(shd)


def _border(paragraph, side: str, color: str, size: str = "6", space: str = "1") -> None:
    ppr = paragraph._p.get_or_add_pPr()
    bdr = ppr.find(qn("w:pBdr"))
    if bdr is None:
        bdr = OxmlElement("w:pBdr")
        ppr.append(bdr)
    el = OxmlElement(f"w:{side}")
    for k, v in (("w:val", "single"), ("w:sz", size), ("w:space", space), ("w:color", color)):
        el.set(qn(k), v)
    bdr.append(el)


def to_docx(r: ParsedResume, t: Template, headline: str | None = None) -> bytes:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = t.font, Pt(t.body_size)
    st.paragraph_format.space_after = Pt(1 if t.compact else 2)
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Pt(42 if t.compact else 50)
    sec.top_margin = sec.bottom_margin = Pt(32 if t.compact else 40)
    width = sec.page_width - sec.left_margin - sec.right_margin
    accent = RGBColor(*t.accent)
    hexacc = "".join(f"{v:02X}" for v in t.accent)
    align = WD_ALIGN_PARAGRAPH.CENTER if t.centered else WD_ALIGN_PARAGRAPH.LEFT

    p = doc.add_paragraph()
    p.alignment = align
    run = p.add_run(r.name or "Your Name")
    run.bold, run.font.size = True, Pt(t.name_size)
    if t.band:
        _shade(p, "18181B")
        run.font.color.rgb = RGBColor(255, 255, 255)
    if headline:
        hp = doc.add_paragraph()
        hp.alignment = align
        hr = hp.add_run(headline)
        hr.font.size, hr.font.color.rgb = Pt(t.body_size + 1.5), (RGBColor(255, 255, 255) if t.band else accent)
        if t.band:
            _shade(hp, "18181B")
    if _contact(r):
        cp = doc.add_paragraph("  •  ".join(_contact(r)))
        cp.alignment = align
        if t.band:
            _shade(cp, "18181B")
            for rn in cp.runs:
                rn.font.color.rgb = RGBColor(220, 220, 220)
        cp.paragraph_format.space_after = Pt(6)

    for head, rows in sections(r, t):
        h = doc.add_paragraph()
        text = head if t.heading == "caps" else head.upper()
        hr = h.add_run(text)
        hr.bold, hr.font.size, hr.font.color.rgb = True, Pt(t.body_size + 1.5), accent
        if t.heading == "caps":
            hr.font.small_caps = True
        h.paragraph_format.space_before = Pt(6 if t.compact else 11)
        h.paragraph_format.space_after = Pt(3)
        if t.heading == "rule":
            _border(h, "bottom", "A3A3A3", "4")
        elif t.heading == "bar":
            _border(h, "left", hexacc, "24", "6")
        for kind, s, right in rows:
            if kind == "b":
                doc.add_paragraph(s, style="List Bullet")
            elif kind == "h":
                hp = doc.add_paragraph()
                hp.paragraph_format.space_before = Pt(4)
                hp.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
                hp.add_run(s).bold = True
                if right:
                    dr = hp.add_run(f"\t{right}")
                    dr.font.color.rgb = RGBColor(90, 90, 90)
            elif kind == "s":
                sr = doc.add_paragraph().add_run(s)
                sr.italic, sr.font.size, sr.font.color.rgb = True, Pt(t.body_size - 0.5), RGBColor(80, 80, 80)
            elif kind == "k":
                kp = doc.add_paragraph()
                label, _, rest = s.partition(": ")
                if rest:
                    kp.add_run(label + ": ").bold = True
                    kp.add_run(rest)
                else:
                    kp.add_run(s)
            else:
                doc.add_paragraph(s)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ PDF (no native dependencies)

def _esc(s: str) -> str:
    s = s.replace("—", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _rgb(c: tuple[int, int, int]) -> str:
    return " ".join(f"{v / 255:.3f}" for v in c)


def to_pdf(r: ParsedResume, t: Template, headline: str | None = None) -> bytes:
    W, H = 595, 842  # A4
    margin = 42 if t.compact else 50
    size = t.body_size
    lead = size * (1.22 if t.compact else 1.34)
    times = t.pdf_font == "Times"
    reg, bold, ital = ("Times-Roman", "Times-Bold", "Times-Italic") if times else ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique")
    face = {"F1": reg, "F2": bold, "F3": ital}

    def tw(s: str, font: str, sz: float) -> float:
        return fm.width(s, face[font], sz)

    def wrap(s: str, sz: float, indent: float = 0, font: str = "F1") -> list[str]:
        return fm.wrap(s, face[font], sz, W - 2 * margin - indent)

    pages: list[list[str]] = [[]]
    y = H - margin

    def need(h: float) -> None:
        nonlocal y
        if y - h < margin:
            pages.append([])
            y = H - margin

    def put(s: str, x: float, font: str, sz: float, rgb=(17, 17, 17), *, center: bool = False, right: bool = False,
            advance: bool = True) -> None:
        nonlocal y
        need(sz * 1.3)
        if center:
            x = (W - tw(s, font, sz)) / 2
        elif right:
            x = W - margin - tw(s, font, sz)
        pages[-1].append(f"BT {_rgb(rgb)} rg /{font} {sz} Tf {x:.1f} {y - sz:.1f} Td ({_esc(s)}) Tj ET")
        if advance:
            y -= sz * 1.28 if sz > size + 1 else lead

    contact = "  |  ".join(_contact(r))
    if t.band:
        lines = 2 + (1 if headline else 0) + len(wrap(contact, size - 0.5))
        band_h = t.name_size * 1.3 + (lines - 1) * lead + 26
        pages[-1].append(f"{_rgb((24, 24, 27))} rg 0 {H - band_h:.1f} {W} {band_h:.1f} re f")
        pages[-1].append(f"{_rgb(t.accent)} rg 0 {H - band_h - 4:.1f} {W} 4 re f")
        y = H - 22
        put(r.name or "Your Name", margin, "F2", t.name_size, (255, 255, 255))
        if headline:
            put(headline, margin, "F1", size + 1.5, (255, 255, 255))
        for ln in wrap(contact, size - 0.5):
            put(ln, margin, "F1", size - 0.5, (212, 212, 216))
        y = H - band_h - 14
    else:
        put(r.name or "Your Name", margin, "F2", t.name_size, center=t.centered)
        if headline:
            put(headline, margin, "F1", size + 1.5, t.accent, center=t.centered)
        for ln in wrap(contact, size - 0.5):
            put(ln, margin, "F1", size - 0.5, (82, 82, 82), center=t.centered)

    for head, rows in sections(r, t):
        y -= 5 if t.compact else 9
        need(size * 3.2)
        label = head if t.heading == "caps" else head.upper()
        if t.heading == "bar":
            pages[-1].append(f"{_rgb(t.accent)} rg {margin} {y - size - 2:.1f} 3.2 {size + 3:.1f} re f")
            put(label, margin + 9, "F2", size + 1.5, t.accent)
        else:
            put(label.upper() if t.heading == "caps" else label, margin, "F2", size + (0.5 if t.heading == "caps" else 1.5), t.accent)
        if t.heading == "rule":
            pages[-1].append(f"0.64 0.64 0.64 RG 0.6 w {margin} {y - 1:.1f} m {W - margin} {y - 1:.1f} l S")
        y -= 3
        for kind, s, right in rows:
            if kind == "b":
                for i, ln in enumerate(wrap(s, size, 14)):
                    put(("•  " if i == 0 else "") + ln, margin + (4 if i == 0 else 13), "F1", size)
            elif kind == "h":
                y -= 2
                if right:
                    put(right, 0, "F1", size - 0.5, (90, 90, 90), right=True, advance=False)
                for ln in wrap(s, size, tw(right, "F1", size - 0.5) + 14 if right else 0, "F2"):
                    put(ln, margin, "F2", size)
            elif kind == "s":
                for ln in wrap(s, size - 0.5):
                    put(ln, margin, "F3", size - 0.5, (82, 82, 82))
            elif kind == "k":
                label, sep, rest = s.partition(": ")
                if not sep:
                    for ln in wrap(s, size):
                        put(ln, margin, "F1", size)
                    continue
                lab_w = tw(label + ": ", "F2", size)
                first, *more = fm.wrap(rest, reg, size, W - 2 * margin - lab_w)
                put(label + ":", margin, "F2", size, advance=False)
                put(first, margin + lab_w, "F1", size)
                for ln in fm.wrap(" ".join(more), reg, size, W - 2 * margin) if more else []:
                    put(ln, margin, "F1", size)
            else:
                for ln in wrap(s, size):
                    put(ln, margin, "F1", size)

    objs: list[bytes] = []

    def add(b: bytes) -> int:
        objs.append(b)
        return len(objs)

    fonts = [add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{f} /Encoding /WinAnsiEncoding >>".encode()) for f in (reg, bold, ital)]
    pages_id = len(objs) + 1 + 2 * len(pages)
    page_ids = []
    for ops in pages:
        raw = zlib.compress("\n".join(ops).encode("cp1252", "replace"))
        cid = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(raw) + raw + b"\nendstream")
        page_ids.append(add((f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W} {H}] /Contents {cid} 0 R "
                             f"/Resources << /Font << /F1 {fonts[0]} 0 R /F2 {fonts[1]} 0 R /F3 {fonts[2]} 0 R >> >> >>").encode()))
    add(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>".encode())
    info = add(f"<< /Title ({_esc(r.name or 'Resume')}) /Author ({_esc(r.name or '')}) /Producer (Saige AI) >>".encode())
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    out.write("".join(f"{o:010d} 00000 n \n" for o in offsets).encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


# ------------------------------------------------------------------ HTML / Markdown / text

def to_html(r: ParsedResume, t: Template, headline: str | None = None) -> str:
    e = html.escape
    acc = "#" + "".join(f"{v:02x}" for v in t.accent)
    head = [f"<h1>{e(r.name or 'Your Name')}</h1>"]
    if headline:
        head.append(f"<p class='headline'>{e(headline)}</p>")
    head.append(f"<p class='contact'>{'<span>•</span>'.join(e(x) for x in _contact(r))}</p>")
    body = [f"<header class='{'band' if t.band else ''}'>{''.join(head)}</header>"]
    for title, rows in sections(r, t):
        body.append(f"<section><h2>{e(title)}</h2>")
        ul = False
        for kind, s, right in rows:
            if kind == "b" and not ul:
                body.append("<ul>")
                ul = True
            if kind != "b" and ul:
                body.append("</ul>")
                ul = False
            if kind == "b":
                body.append(f"<li>{e(s)}</li>")
            elif kind == "h":
                body.append(f"<div class='item'><strong>{e(s)}</strong><span class='date'>{e(right)}</span></div>")
            elif kind == "s":
                body.append(f"<p class='sub'>{e(s)}</p>")
            elif kind == "k":
                label, _, rest = s.partition(": ")
                body.append(f"<p><strong>{e(label)}:</strong> {e(rest)}</p>" if rest else f"<p>{e(s)}</p>")
            else:
                body.append(f"<p>{e(s)}</p>")
        if ul:
            body.append("</ul>")
        body.append("</section>")
    align = "center" if t.centered else "left"
    h2 = {"rule": "border-bottom:1px solid #a3a3a3;padding-bottom:2px;text-transform:uppercase;letter-spacing:.06em",
          "bar": f"border-left:4px solid {acc};padding-left:9px;text-transform:uppercase;letter-spacing:.06em",
          "caps": "font-variant:small-caps;letter-spacing:.12em;font-weight:600",
          "plain": "text-transform:uppercase;letter-spacing:.04em"}[t.heading]
    band = ("header.band{background:#18181b;color:#fff;margin:-36px -40px 18px;padding:28px 40px 20px;border-bottom:4px solid "
            f"{acc}}}header.band .headline{{color:#fff}}header.band .contact{{color:#d4d4d8}}") if t.band else ""
    css = (f"body{{font-family:'{t.font}',Arial,sans-serif;font-size:{t.body_size}pt;color:#171717;background:#fff;max-width:780px;"
           f"margin:0 auto;padding:36px 40px;line-height:1.42}}header{{text-align:{align};margin-bottom:10px}}"
           f"h1{{font-size:{t.name_size}pt;margin:0;letter-spacing:-.01em}}.headline{{color:{acc};font-size:{t.body_size + 1.5}pt;margin:2px 0 4px}}"
           f".contact{{color:#525252;font-size:{t.body_size - 0.5}pt;margin:0}}.contact span{{margin:0 8px;color:#a3a3a3}}"
           f"h2{{font-size:{t.body_size + 1.5}pt;color:{acc};margin:{12 if t.compact else 18}px 0 6px;{h2}}}"
           ".item{display:flex;justify-content:space-between;gap:12px;margin-top:7px}.date{color:#5a5a5a;white-space:nowrap}"
           ".sub{color:#525252;font-style:italic;margin:0}ul{margin:3px 0 6px 18px;padding:0}li{margin:1px 0}p{margin:2px 0}"
           f"{band}@media print{{body{{padding:0}}header.band{{margin:0 0 18px}}}}")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(r.name or 'Resume')}</title>"
            f"<style>{css}</style></head><body>{''.join(body)}</body></html>")


def to_md(r: ParsedResume, t: Template, headline: str | None = None) -> str:
    out = [f"# {r.name or 'Your Name'}"] + ([f"**{headline}**"] if headline else []) + [" | ".join(_contact(r)), ""]
    for head, rows in sections(r, t):
        out += [f"## {head}", ""]
        for kind, s, right in rows:
            out.append({"b": f"- {s}", "h": f"**{s}**" + (f" — {right}" if right else ""), "s": f"*{s}*"}.get(kind, s))
        out.append("")
    return "\n".join(out)


def to_txt(r: ParsedResume, t: Template, headline: str | None = None) -> str:
    out = [(r.name or "Your Name").upper()] + ([headline] if headline else []) + [" | ".join(_contact(r)), ""]
    for head, rows in sections(r, t):
        out += [head.upper(), "-" * len(head)]
        for kind, s, right in rows:
            out.append({"b": f"  * {s}", "h": s + (f"  ({right})" if right else "")}.get(kind, s))
        out.append("")
    return "\n".join(out)


def render(r: ParsedResume, template: str, fmt: str, headline: str | None = None) -> bytes:
    t = TEMPLATES.get(template, TEMPLATES["modern"])
    if fmt == "docx":
        return to_docx(r, t, headline)
    if fmt == "pdf":
        return to_pdf(r, t, headline)
    return {"html": to_html, "md": to_md, "txt": to_txt}[fmt](r, t, headline).encode("utf-8")


def filename(name: str | None, company: str | None, date: str, fmt: str) -> str:
    """First_Last_YYYY-MM-DD_Company.ext"""
    def clean(s: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40]
    words = (name or "").split()
    person = f"{words[0]} {words[-1]}" if len(words) >= 2 else (name or "Resume")
    return "_".join(p for p in (clean(person), date, clean(company or "")) if p) + f".{fmt}"
