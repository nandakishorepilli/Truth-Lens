"""Text normalization and offset-preserving sentence segmentation."""
from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BULLET = re.compile(r"^[ \t]*(?:[-*\u2022]|\d{1,3}[.)])[ \t]+")
_BOUNDARY = re.compile(r"""[.!?]+["')\]]*\s+""")
_ABBREV = {"dr", "mr", "mrs", "ms", "prof", "vs", "e.g", "i.e", "u.s", "u.k", "inc", "ltd", "fig", "approx", "jr", "sr"}


def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL.sub("", t).strip()


def _split_line(body: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _BOUNDARY.finditer(body):
        nxt = body[m.end():m.end() + 1]
        if not nxt or not (nxt.isupper() or nxt.isdigit() or nxt in "\"'(["):
            continue
        prev = re.search(r"([A-Za-z][A-Za-z.]*)$", body[start:m.start()])
        if body[m.start()] == "." and prev:
            tok = prev.group(1)
            if tok.lower() in _ABBREV or (len(tok) == 1 and tok.isupper()):
                continue
        spans.append((start, m.start() + len(m.group().rstrip())))
        start = m.end()
    spans.append((start, len(body)))
    return [(s, e) for s, e in spans if body[s:e].strip()]


def iter_segments(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of sentences, honoring lines and list bullets."""
    out, offset = [], 0
    for line in text.split("\n"):
        line_start, offset = offset, offset + len(line) + 1
        if not line.strip():
            continue
        b = _BULLET.match(line)
        body_start = b.end() if b else 0
        for s, e in _split_line(line[body_start:]):
            seg = line[body_start + s:body_start + e]
            lead = len(seg) - len(seg.lstrip())
            out.append((line_start + body_start + s + lead, line_start + body_start + s + len(seg.rstrip())))
    return out
