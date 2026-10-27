"""Apple Vision observations -> text lines in reading order."""

LINE_TOLERANCE = 0.008
"""Max vertical gap between word centres on one line, in Vision's normalised page height
(about half a text line on an A4 page)."""


def to_lines(observations: list) -> str:
    """observations: (text, confidence, (x, y, w, h)) as ocrmac returns them, normalised,
    origin bottom-left. Top to bottom; a word joins the current line while its centre is
    within LINE_TOLERANCE of the line's first word; each line reads left to right."""
    ordered = sorted(observations, key=lambda o: -(o[2][1] + o[2][3] / 2))
    lines: list[list[tuple[float, str]]] = []
    top = None
    for text, _, (x, y, _w, h) in ordered:
        middle = y + h / 2
        if top is None or top - middle > LINE_TOLERANCE:
            lines.append([])
            top = middle
        lines[-1].append((x, text))
    return "\n".join(" ".join(text for _, text in sorted(line)) for line in lines)
