"""A tiny dependency-free PDF writer for post carousels (dark slides, one accent colour, Helvetica).
LinkedIn shows a PDF as a swipeable document post, so this works on any server with no imaging libraries."""

import textwrap
import zlib


def _esc(t: str) -> str:
    t = t.encode("cp1252", "replace").decode("cp1252")
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _rgb(c: tuple[int, int, int]) -> str:
    return " ".join(f"{v / 255:.3f}" for v in c)


def slides_pdf(slides: list[tuple[str, list[str]]], series: str, footer: str, accent: tuple[int, int, int]) -> bytes:
    """slides: (heading, lines). Page size 540x675 pt (4:5, like LinkedIn document posts)."""
    W, H = 540, 675
    objs: list[bytes] = []
    pages: list[int] = []

    def add(b: bytes) -> int:
        objs.append(b)
        return len(objs)

    font_r = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_b = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, (head, lines) in enumerate(slides):
        ops = [f"{_rgb((10, 10, 12))} rg 0 0 {W} {H} re f", f"{_rgb(accent)} rg 0 0 7 {H} re f",
               f"BT /F2 12 Tf {_rgb(accent)} rg 40 {H - 50} Td ({_esc(f'{series.upper()}  ·  {i + 1}/{len(slides)}')}) Tj ET"]
        y = H - (200 if i == 0 else 130)
        size = 34 if i == 0 else 44
        for line in textwrap.wrap(head, 22 if i == 0 else 16)[:4]:
            ops.append(f"BT /F2 {size} Tf 0.96 0.96 0.97 rg 40 {y} Td ({_esc(line)}) Tj ET")
            y -= size + 10
        y -= 20
        for text in lines:
            for line in textwrap.wrap(text, 34)[:10]:
                ops.append(f"BT /F1 20 Tf 0.80 0.80 0.83 rg 40 {y} Td ({_esc(line)}) Tj ET")
                y -= 28
            y -= 12
        ops.append(f"0.16 0.16 0.18 RG 1 w 40 70 m {W - 40} 70 l S")
        ops.append(f"BT /F1 12 Tf 0.6 0.6 0.63 rg 40 48 Td ({_esc(footer)}) Tj ET")
        stream = zlib.compress("\n".join(ops).encode("latin-1", "replace"))
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        pages.append(add(f"<< /Type /Page /Parent PAGES /MediaBox [0 0 {W} {H}] /Contents {content} 0 R "
                         f"/Resources << /Font << /F1 {font_r} 0 R /F2 {font_b} 0 R >> >> >>".encode()))
    kids = " ".join(f"{p} 0 R" for p in pages)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    objs = [o.replace(b"/Parent PAGES", f"/Parent {pages_id} 0 R".encode()) for o in objs]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
