"""Per-week power-rating files committed to the repo.

Sonny Moore is the automatic source, but early in the season his page still
serves last season's final numbers, and some weeks you may simply trust a
different rating. Drop a CSV at:

    ratings/<season>_wk<NN>.csv        e.g. ratings/2026_wk01.csv

and the app uses it for that week instead of (or blended with) Sonny Moore.

Because the file is keyed to the week, the History tab re-runs that week with
the SAME ratings the live board used — so any week with a committed file is
graded without look-ahead bias.

Accepted formats:
  * Massey's own Export file (header row containing 'Pwr'; the power VALUE is
    the column right after the 'Pwr' rank column)
  * a plain Team,Rating CSV

Ratings must be point-spread-equivalent (a 3-point gap = a 3-point spread).
The pipeline re-centres every source on the league mean, so absolute scale
doesn't matter — only the gaps between teams.
"""
from __future__ import annotations
import csv
import io

import requests

from .teams import resolve

DIR = "ratings"


def path_for(season: int, week: int) -> str:
    return f"{DIR}/{season}_wk{int(week):02d}.csv"


def parse_csv(text: str) -> dict[str, float]:
    """Parse a Massey export or a simple Team,Rating CSV -> {abbr: rating}."""
    text = text.lstrip("\ufeff").strip()
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {}
    val_idx = None
    header = [c.strip().lower() for c in rows[0]]
    if "pwr" in header:
        val_idx = header.index("pwr") + 1
        rows = rows[1:]
    elif "team" in header:
        rows = rows[1:]
    out: dict[str, float] = {}
    for row in rows:
        if len(row) < 2:
            continue
        abbr = resolve(row[0])
        if not abbr:
            continue
        try:
            rating = float(row[val_idx] if val_idx is not None else row[-1])
        except (ValueError, IndexError):
            continue
        out[abbr] = rating
    return out


def load_from_repo(repo: str, season: int, week: int, branch: str = "main",
                   timeout: int = 15) -> dict[str, float] | None:
    """Fetch ratings/<season>_wk<NN>.csv from the public repo, or None."""
    if not repo:
        return None
    url = (f"https://raw.githubusercontent.com/{repo}/{branch}/"
           f"{path_for(season, week)}")
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        parsed = parse_csv(r.text)
        return parsed or None
    except Exception:
        return None
