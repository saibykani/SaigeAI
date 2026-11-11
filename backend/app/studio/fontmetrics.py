"""Glyph widths (1/1000 em) of the standard PDF fonts for printable ASCII (from the Adobe AFM files).

Used to wrap lines, centre text and right-align dates exactly, without embedding fonts or native libraries.
Characters outside ASCII use an average width.
"""

_ORDER = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

_W = {
    "Helvetica": [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, *[556] * 10, 278, 278, 584, 584, 584, 556,
                  1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944,
                  667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
                  556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584],
    "Helvetica-Bold": [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, *[556] * 10, 333, 333, 584, 584, 584,
                       611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722,
                       667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278,
                       889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584],
    "Times-Roman": [250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564, 250, 333, 250, 278, *[500] * 10, 278, 278, 564, 564, 564, 444,
                    921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722, 556, 722, 667, 556, 611, 722, 722, 944,
                    722, 722, 611, 333, 278, 333, 469, 500, 333, 444, 500, 444, 500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500, 500,
                    500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541],
    "Times-Bold": [250, 333, 555, 500, 500, 1000, 833, 278, 333, 333, 500, 570, 250, 333, 250, 278, *[500] * 10, 333, 333, 570, 570, 570, 500,
                   930, 722, 667, 722, 722, 667, 611, 778, 778, 389, 500, 778, 667, 944, 722, 778, 611, 778, 722, 556, 667, 722, 722, 1000,
                   722, 722, 667, 333, 278, 333, 581, 500, 333, 500, 556, 444, 556, 444, 333, 500, 556, 278, 333, 556, 278, 833, 556, 500,
                   556, 556, 444, 389, 333, 556, 500, 722, 500, 500, 444, 394, 220, 394, 520],
}
_W["Helvetica-Oblique"] = _W["Helvetica"]
_W["Times-Italic"] = _W["Times-Roman"]
WIDTHS = {font: dict(zip(_ORDER, ws, strict=True)) for font, ws in _W.items()}
_EXTRA = {"•": 350, "–": 556, "—": 1000, "·": 278, "’": 222, "“": 333, "”": 333}


def width(text: str, font: str, size: float) -> float:
    table = WIDTHS.get(font, WIDTHS["Helvetica"])
    return sum(table.get(ch, _EXTRA.get(ch, 556)) for ch in text) * size / 1000


def wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Greedy word wrap by measured width."""
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        trial = f"{cur} {w}" if cur else w
        if cur and width(trial, font, size) > max_width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]
