"""Per-week power ratings committed to the repo.

Streamlit Cloud clones the repo onto the server, so any file committed at
  ratings/massey_<season>_wk<NN>.csv        e.g. ratings/massey_2026_wk01.csv
is readable by the app at run time. Drop a Massey export in that folder and
the app uses it for that week — useful early season when Sonny Moore is
still serving last season's final ratings.

Bonus: a file committed BEFORE a week is played is an as-of-that-week
rating snapshot, so the History tab can backtest that week without the
look-ahead bias that current ratings introduce.

Accepted formats:
  * Massey's own Export CSV (header row containing 'Pwr'; the power VALUE
    sits in the column immediately after the 'Pwr' rank column)
  * a simple two-column Team,Rating CSV
"""
from __future__ import annotations
import csv
import io
import os

from .teams import resolve

DIR = "ratings"


def path_for(season: int, week: int) -> str:
    return os.path.join(DIR, f"massey_{season}_wk{int(week):02d}.csv")


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


def load(season: int, week: int) -> dict[str, float] | None:
    """Return ratings for this week if a file is committed, else None."""
    p = path_for(season, week)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8-sig") as fh:
            r = parse_csv(fh.read())
        return r or None
    except Exception:
        return None


def available(season: int) -> list[int]:
    """Weeks that have a committed ratings file."""
    if not os.path.isdir(DIR):
        return []
    out = []
    for name in os.listdir(DIR):
        if name.startswith(f"massey_{season}_wk") and name.endswith(".csv"):
            try:
                out.append(int(name.split("_wk")[1][:-4]))
            except ValueError:
                continue
    return sorted(out)
