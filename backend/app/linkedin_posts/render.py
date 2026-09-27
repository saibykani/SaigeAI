"""Images for LinkedIn posts: a square card (PNG) or a swipeable carousel (multi-page PDF).
Drawn with Pillow's bundled scalable font, so it renders the same on any server."""

import io
import textwrap

THEME_COLOURS = {  # one accent per series (single hue on a dark card)
    "tip": (48, 209, 88), "mistake": (255, 159, 10), "checklist": (100, 210, 255), "interview": (191, 90, 242),
    "tool": (255, 214, 10), "learned": (99, 230, 190), "career": (255, 69, 58),
}


def _font(size: int):
    from PIL import ImageFont  # imported lazily: the API starts even if imaging is unavailable

    return ImageFont.load_default(size=size)


def _wrap(draw, text: str, size: int, width_px: int) -> list[str]:
    f = _font(size)
    avg = max(1, int(draw.textlength("abcdefghijklmnopqrstuvwxyz", font=f) / 26))
    return textwrap.wrap(text, width=max(8, width_px // avg))


def _base(w: int, h: int, accent: tuple[int, int, int]):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), (10, 10, 12))
    d = ImageDraw.Draw(img)
    for i in range(0, 380, 4):  # soft single-hue glow in the top-right corner
        a = max(0, 26 - i // 15)
        d.ellipse((w - 300 - i, -300 - i, w + 300 + i, 300 + i), outline=tuple(int(c * a / 100) + 10 for c in accent))
    d.rectangle((0, 0, 14, h), fill=accent)
    return img, d


def card(post: dict, name: str, role: str) -> bytes:
    """1080x1080 PNG: series label, title, up to three points, author footer."""
    accent = THEME_COLOURS.get(post.get("theme", ""), (48, 209, 88))
    img, d = _base(1080, 1080, accent)
    d.text((80, 80), post.get("series", "").upper(), font=_font(34), fill=accent)
    y = 150
    for line in _wrap(d, post.get("title", ""), 68, 900)[:3]:
        d.text((80, y), line, font=_font(68), fill=(245, 245, 247), stroke_width=1, stroke_fill=(245, 245, 247))
        y += 84
    y += 30
    for pt in post.get("points", [])[:3]:
        d.ellipse((80, y + 14, 96, y + 30), fill=accent)
        for j, line in enumerate(_wrap(d, pt, 36, 820)[:4]):
            d.text((120, y + j * 46), line, font=_font(36), fill=(200, 200, 208))
        y += 46 * min(4, len(_wrap(d, pt, 36, 820))) + 34
    d.line((80, 950, 1000, 950), fill=(40, 40, 44), width=2)
    d.text((80, 975), name or "", font=_font(34), fill=(245, 245, 247))
    d.text((80, 1020), role or "", font=_font(26), fill=(152, 152, 159))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def carousel(post: dict, name: str, role: str) -> bytes:
    """Portrait slides (1080x1350) saved as one PDF: LinkedIn shows it as a swipeable document post."""
    accent = THEME_COLOURS.get(post.get("theme", ""), (48, 209, 88))
    pages = []
    slides = post.get("slides") or [(post.get("title", ""), post.get("points", []))]
    for i, (head, lines) in enumerate(slides):
        img, d = _base(1080, 1350, accent)
        d.text((80, 80), f"{post.get('series', '')} · {i + 1}/{len(slides)}", font=_font(30), fill=accent)
        y = 220 if i else 420
        big = 88 if i == 0 else 110
        for line in _wrap(d, head, big, 900)[:4]:
            d.text((80, y), line, font=_font(big), fill=(245, 245, 247), stroke_width=1, stroke_fill=(245, 245, 247))
            y += big + 18
        for text in lines:
            for line in _wrap(d, text, 44, 900)[:8]:
                d.text((80, y + 40), line, font=_font(44), fill=(205, 205, 212))
                y += 58
        d.text((80, 1250), f"{name}  ·  {role}", font=_font(28), fill=(152, 152, 159))
        pages.append(img)
    out = io.BytesIO()
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return out.getvalue()
