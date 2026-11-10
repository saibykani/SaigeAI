"""Resume templates and file formats for ATS Studio.

Every template is single column with standard section headings and real text (no tables, images or
text boxes), so applicant tracking systems read it reliably. Templates differ in typography, spacing
and section order only. Formats: DOCX (python-docx), PDF (dependency-free writer, standard fonts), HTML,
Markdown and plain text.
"""

import html
import io
import re
import textwrap
import zlib
from dataclasses import dataclass

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from app.schemas.resume import ParsedResume


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    font: str          # DOCX/HTML font
    pdf_font: str      # Helvetica or Times
    accent: tuple[int, int, int]
    name_size: int
    body_size: float
    centered: bool
    order: tuple[str, ...]
    rule: bool         # line under headings


ORDER = ("summary", "skills", "experience", "projects", "education", "certifications")
TEMPLATES = {t.id: t for t in (
    Template("classic", "Classic", "Centered name, serif type, black headings. Safe for every recruiter and ATS.",
             "Georgia", "Times", (20, 20, 20), 20, 10.5, True, ORDER, True),
    Template("modern", "Modern", "Clean sans-serif with one dark-green accent and thin rules.",
             "Calibri", "Helvetica", (22, 101, 52), 22, 10.5, False, ORDER, True),
    Template("compact", "Compact", "Tighter spacing and smaller type: fits more on one page.",
             "Arial", "Helvetica", (40, 40, 40), 17, 9.5, False, ORDER, False),
    Template("skills_first", "Skills-first", "Skills and tools above experience: best for tester and engineering roles.",
             "Calibri", "Helvetica", (154, 52, 18), 21, 10.5, False,
             ("skills", "summary", "experience", "projects", "certifications", "education"), True),
    Template("executive", "Executive", "Larger name, generous spacing, summary-led. For senior roles.",
             "Garamond", "Times", (30, 30, 30), 24, 11, True, ORDER, True),
)}
FORMATS = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "pdf": "application/pdf",
           "html": "text/html; charset=utf-8", "md": "text/markdown; charset=utf-8", "txt": "text/plain; charset=utf-8"}
HEADINGS = {"summary": "Professional Summary", "skills": "Skills", "experience": "Experience", "projects": "Projects",
            "education": "Education", "certifications": "Certifications"}


# ------------------------------------------------------------------ neutral structure

def _contact(r: ParsedResume) -> list[str]:
    return [x for x in (r.email, r.phone, r.location, r.links.linkedin, r.links.github, r.links.portfolio) if x]


def _dates(e) -> str:
    return " – ".join(x for x in (e.start_date, "Present" if e.is_current else e.end_date) if x)


def _edu_line(ed) -> str:
    years = " – ".join(str(y) for y in (ed.start_year, ed.end_year) if y)
    return ", ".join(x for x in (f"{ed.degree} in {ed.field}" if ed.field and ed.degree else ed.degree, ed.institution, years) if x) or ed.raw


def sections(r: ParsedResume, t: Template) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(heading, [(kind, text)])] where kind is p (paragraph), b (bullet), h (item heading), m (item meta)."""
    out = []
    for key in t.order:
        rows: list[tuple[str, str]] = []
        if key == "summary" and r.summary:
            rows = [("p", r.summary)]
        elif key == "skills" and r.skills:
            rows = [("p", ", ".join(r.skills))]
            if r.tools and t.id == "skills_first":
                rows.insert(0, ("p", "Key for this role: " + ", ".join(r.tools)))
        elif key == "experience":
            for e in r.experience:
                rows.append(("h", " — ".join(x for x in (e.title, e.company) if x)))
                meta = " | ".join(x for x in (e.location, _dates(e)) if x)
                if meta:
                    rows.append(("m", meta))
                rows += [("b", b) for b in e.achievements + e.responsibilities]
                if e.technologies:
                    rows.append(("m", "Tools: " + ", ".join(e.technologies)))
        elif key == "projects":
            for pr in r.projects:
                rows.append(("h", pr.name + (f" ({', '.join(pr.technologies)})" if pr.technologies else "")))
                rows += [("b", h) for h in pr.highlights]
        elif key == "education":
            rows = [("p", _edu_line(ed)) for ed in r.education]
        elif key == "certifications":
            rows = [("b", c) for c in r.certifications]
        if rows:
            out.append((HEADINGS[key], rows))
    return out


# ------------------------------------------------------------------ DOCX

def to_docx(r: ParsedResume, t: Template) -> bytes:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = t.font, Pt(t.body_size)
    st.paragraph_format.space_after = Pt(1 if t.id == "compact" else 2)
    for s in doc.sections:
        s.left_margin = s.right_margin = Pt(46 if t.id == "compact" else 54)
        s.top_margin = s.bottom_margin = Pt(36 if t.id == "compact" else 46)
    accent = RGBColor(*t.accent)
    p = doc.add_paragraph()
    run = p.add_run(r.name or "Your Name")
    run.bold, run.font.size = True, Pt(t.name_size)
    if t.centered:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if _contact(r):
        c = doc.add_paragraph(" | ".join(_contact(r)))
        if t.centered:
            c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for head, rows in sections(r, t):
        h = doc.add_paragraph()
        hr = h.add_run(head.upper())
        hr.bold, hr.font.size, hr.font.color.rgb = True, Pt(t.body_size + 1), accent
        h.paragraph_format.space_before = Pt(6 if t.id == "compact" else 10)
        if t.rule:
            _bottom_border(h)
        for kind, text in rows:
            if kind == "b":
                doc.add_paragraph(text, style="List Bullet")
            elif kind == "h":
                doc.add_paragraph().add_run(text).bold = True
            elif kind == "m":
                m = doc.add_paragraph().add_run(text)
                m.italic, m.font.size = True, Pt(t.body_size - 0.5)
            else:
                doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _bottom_border(paragraph) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    ppr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "1"), ("w:color", "999999")):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    ppr.append(bdr)


# ------------------------------------------------------------------ PDF (no native dependencies)

def _esc(s: str) -> str:
    s = s.replace("—", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def to_pdf(r: ParsedResume, t: Template) -> bytes:
    W, H = 595, 842  # A4
    margin = 46 if t.id == "compact" else 54
    size = t.body_size
    lead = size * (1.3 if t.id != "compact" else 1.22)
    reg, bold, ital = (("Times-Roman", "Times-Bold", "Times-Italic") if t.pdf_font == "Times"
                       else ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"))
    width_chars = lambda sz, indent=0: max(20, int((W - 2 * margin - indent) / (sz * (0.47 if t.pdf_font == "Times" else 0.5))))  # noqa: E731
    pages: list[list[str]] = [[]]
    y = H - margin

    def need(h: float) -> None:
        nonlocal y
        if y - h < margin:
            pages.append([])
            y = H - margin

    def text(s: str, x: float, font: str, sz: float, rgb=(0, 0, 0), center: bool = False) -> None:
        nonlocal y
        need(sz * 1.3)
        if center:
            x = (W - len(s) * sz * 0.5) / 2
        col = " ".join(f"{v / 255:.3f}" for v in rgb)
        pages[-1].append(f"BT {col} rg /{font} {sz} Tf {x:.1f} {y - sz:.1f} Td ({_esc(s)}) Tj ET")
        y -= sz * 1.3 if sz > size else lead

    text(r.name or "Your Name", margin, "F2", t.name_size, center=t.centered)
    y -= 4
    for line in textwrap.wrap(" | ".join(_contact(r)), width_chars(size - 0.5)) or []:
        text(line, margin, "F1", size - 0.5, (70, 70, 70), center=t.centered)
    for head, rows in sections(r, t):
        y -= 6 if t.id == "compact" else 9
        need(size * 3)
        text(head.upper(), margin, "F2", size + 1, t.accent)
        if t.rule:
            pages[-1].append(f"0.6 0.6 0.6 RG 0.5 w {margin} {y + 2:.1f} m {W - margin} {y + 2:.1f} l S")
            y -= 3
        for kind, s in rows:
            if kind == "b":
                lines = textwrap.wrap(s, width_chars(size, 12))
                for i, ln in enumerate(lines):
                    text(("\u2022 " if i == 0 else "  ") + ln, margin + (4 if i == 0 else 9), "F1", size)
            elif kind == "h":
                y -= 2
                for ln in textwrap.wrap(s, width_chars(size)):
                    text(ln, margin, "F2", size)
            elif kind == "m":
                for ln in textwrap.wrap(s, width_chars(size - 0.5)):
                    text(ln, margin, "F3", size - 0.5, (80, 80, 80))
            else:
                for ln in textwrap.wrap(s, width_chars(size)):
                    text(ln, margin, "F1", size)

    objs: list[bytes] = []

    def add(b: bytes) -> int:
        objs.append(b)
        return len(objs)

    fonts = [add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{f} /Encoding /WinAnsiEncoding >>".encode()) for f in (reg, bold, ital)]
    pages_id = len(objs) + 1 + 2 * len(pages)  # reserved after content + page objects
    page_ids = []
    for ops in pages:
        raw = zlib.compress("\n".join(ops).encode("cp1252", "replace"))
        cid = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(raw) + raw + b"\nendstream")
        page_ids.append(add((f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W} {H}] /Contents {cid} 0 R "
                             f"/Resources << /Font << /F1 {fonts[0]} 0 R /F2 {fonts[1]} 0 R /F3 {fonts[2]} 0 R >> >> >>").encode()))
    add(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>".encode())
    title = _esc(f"{r.name or 'Resume'}")
    info = add(f"<< /Title ({title}) /Producer (Saige AI) >>".encode())
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

def to_html(r: ParsedResume, t: Template) -> str:
    e = html.escape
    acc = "#" + "".join(f"{v:02x}" for v in t.accent)
    body = [f"<h1>{e(r.name or 'Your Name')}</h1>", f"<p class='contact'>{e(' | '.join(_contact(r)))}</p>"]
    for head, rows in sections(r, t):
        body.append(f"<h2>{e(head)}</h2>")
        ul = False
        for kind, s in rows:
            if kind == "b" and not ul:
                body.append("<ul>")
                ul = True
            if kind != "b" and ul:
                body.append("</ul>")
                ul = False
            body.append({"b": f"<li>{e(s)}</li>", "h": f"<p class='item'><strong>{e(s)}</strong></p>",
                         "m": f"<p class='meta'>{e(s)}</p>"}.get(kind, f"<p>{e(s)}</p>"))
        if ul:
            body.append("</ul>")
    align = "center" if t.centered else "left"
    css = (f"body{{font-family:{t.font},Arial,sans-serif;font-size:{t.body_size}pt;color:#111;max-width:760px;margin:32px auto;padding:0 24px;"
           f"line-height:1.4}}h1{{font-size:{t.name_size}pt;margin:0;text-align:{align}}}.contact{{color:#444;text-align:{align};margin:4px 0 8px}}"
           f"h2{{font-size:{t.body_size + 1}pt;text-transform:uppercase;color:{acc};margin:14px 0 4px;"
           + ("border-bottom:1px solid #999;" if t.rule else "") + "}ul{margin:2px 0 6px 18px;padding:0}.item{margin:6px 0 0}"
           ".meta{color:#555;font-style:italic;margin:0}p{margin:2px 0}@media print{body{margin:0}}")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(r.name or 'Resume')}</title>"
            f"<style>{css}</style></head><body>{''.join(body)}</body></html>")


def to_md(r: ParsedResume, t: Template) -> str:
    out = [f"# {r.name or 'Your Name'}", " | ".join(_contact(r)), ""]
    for head, rows in sections(r, t):
        out += [f"## {head}", ""]
        for kind, s in rows:
            out.append({"b": f"- {s}", "h": f"**{s}**", "m": f"*{s}*"}.get(kind, s))
        out.append("")
    return "\n".join(out)


def to_txt(r: ParsedResume, t: Template) -> str:
    out = [(r.name or "Your Name").upper(), " | ".join(_contact(r)), ""]
    for head, rows in sections(r, t):
        out += [head.upper(), "-" * len(head)]
        for kind, s in rows:
            out.append({"b": f"  * {s}"}.get(kind, s))
        out.append("")
    return "\n".join(out)


def render(r: ParsedResume, template: str, fmt: str) -> bytes:
    t = TEMPLATES.get(template, TEMPLATES["modern"])
    if fmt == "docx":
        return to_docx(r, t)
    if fmt == "pdf":
        return to_pdf(r, t)
    return {"html": to_html, "md": to_md, "txt": to_txt}[fmt](r, t).encode("utf-8")


def filename(name: str | None, company: str | None, date: str, fmt: str) -> str:
    """Firstname_Lastname_Company_YYYY-MM-DD.ext"""
    def clean(s: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40]
    parts = [clean(name or "Resume"), clean(company or ""), date]
    return "_".join(p for p in parts if p) + f".{fmt}"
