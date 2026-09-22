"""Closing lines for games that have already been played, from nflverse.

WHY: ESPN strips the odds block from the scoreboard once a game goes live,
so a board saved after kickoff records the model line but an EMPTY market.
nflverse's games file keeps the closing spread and total for every game,
finished or not, and lives on GitHub where the app can always reach it.

Convention (verified against pre-kickoff lines saved by this app, 4/4):
  nflverse spread_line is positive when the HOME team is favoured, so
      home_spread (our convention, negative = home favoured) = -spread_line
"""
from __future__ import annotations
import csv

import requests

URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
CODE_FIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "OAK": "LV",
            "SD": "LAC", "STL": "LAR"}


def _t(code: str) -> str:
    c = (code or "").upper()
    return CODE_FIX.get(c, c)


def closing_lines(season: int, timeout: int = 60
                  ) -> dict[tuple[int, str, str], dict]:
    """{(week, away, home): {home_spread, total, home_score, away_score}}"""
    r = requests.get(URL, timeout=timeout)
    r.raise_for_status()
    out = {}
    for row in csv.DictReader(r.text.splitlines()):
        if row.get("season") != str(season) or row.get("game_type", "REG") != "REG":
            continue
        try:
            wk = int(row["week"])
        except (KeyError, ValueError):
            continue
        def f(k):
            try:
                return float(row.get(k))
            except (TypeError, ValueError):
                return None
        sl = f("spread_line")
        out[(wk, _t(row["away_team"]), _t(row["home_team"]))] = dict(
            home_spread=(None if sl is None else -sl),
            total=f("total_line"),
            home_score=f("home_score"), away_score=f("away_score"))
    return out
