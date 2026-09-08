"""Scrape Sonny Moore's NFL power ratings.

Verified page format (https://sonnymoorepowerratings.com/nfl-foot.htm):
a fixed-width text block inside the page like

    1 SEATTLE SEAHAWKS            17    3    0   87.07   98.02

columns: rank, TEAM NAME, W, L, T, SOS, PR. PR differences are
point-spread-equivalent; the page recommends ~1.9 HFA.
"""
from __future__ import annotations
import re
import requests

from ..teams import resolve

URL = "https://sonnymoorepowerratings.com/nfl-foot.htm"

LINE = re.compile(
    r"^\s*\d{1,2}\s+([A-Za-z][A-Za-z0-9'&\. ]+?)\s+\d+\s+\d+\s+\d+\s+[\d.]+\s+([\d.]+)\s*$"
)


def fetch(timeout: int = 20) -> dict[str, float]:
    """Return {abbr: raw_PR}. Raises on network failure; returns {} on parse failure."""
    r = requests.get(URL, timeout=timeout,
                     headers={"User-Agent": "Mozilla/5.0 (walters-model)"})
    r.raise_for_status()
    return parse(r.text)


def parse(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw in text.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        abbr = resolve(m.group(1).strip())
        if abbr:
            out[abbr] = float(m.group(2))
    return out
