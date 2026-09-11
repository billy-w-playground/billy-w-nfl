"""Post-game data-quality flags, sourced from nflverse (GitHub releases).

WHY NOT ESPN: the scoreboard route works from Streamlit Cloud but the
boxscore/summary routes return 403 there (they answer fine from a browser),
so QB usage can't be read from ESPN in deployment. nflverse publishes the
same numbers as CSVs on GitHub releases, which the app can always reach.

WHAT IS FLAGGED: input invalidation, not bad luck. If a team's depth-chart
QB1 threw a small share of that team's attempts, he did not finish, so the
team that played is not the team the power ratings priced. A pick-six that
flips a cover is football and stays in the record.

The flag is symmetric: either team's starter exiting flags the game, so it
cannot quietly favour the bets that happened to win.

Sources:
  stats_player_week_<season>.csv  — per player per week: team, position,
                                    attempts (tiny file, ~30KB early season)
  depth_charts_<season>.csv       — timestamped depth charts; streamed and
                                    filtered to QB1 rows (48MB on the wire,
                                    ~2s, so cache it)
"""
from __future__ import annotations
import csv
import re

import requests

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
STATS_URL = BASE + "/stats_player/stats_player_week_{season}.csv"
DEPTH_URL = BASE + "/depth_charts/depth_charts_{season}.csv"

# nflverse team codes differ from ours for a few franchises. Without this
# the lookup silently misses and those teams read "no passing stats" forever.
CODE_FIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "OAK": "LV",
            "SD": "LAC", "STL": "LAR"}

MIN_TEAM_ATTEMPTS = 12   # ignore run-heavy / weather games
QB1_SHARE = 0.50         # QB1 below this share of team attempts = did not finish


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def norm_team(code: str) -> str:
    c = (code or "").upper()
    return CODE_FIX.get(c, c)


def fetch_qb_attempts(season: int, timeout: int = 60
                      ) -> dict[tuple[int, str], list[tuple[str, int]]]:
    """{(week, team): [(player, attempts), ...]} sorted by attempts desc."""
    r = requests.get(STATS_URL.format(season=season), timeout=timeout)
    r.raise_for_status()
    out: dict[tuple[int, str], list[tuple[str, int]]] = {}
    for row in csv.DictReader(r.text.splitlines()):
        try:
            att = int(float(row.get("attempts") or 0))
        except ValueError:
            att = 0
        if att <= 0:
            continue
        try:
            wk = int(row["week"])
        except (KeyError, ValueError):
            continue
        key = (wk, norm_team(row.get("team")))
        out.setdefault(key, []).append(
            (row.get("player_display_name") or row.get("player_name") or "?", att))
    for k in out:
        out[k].sort(key=lambda x: -x[1])
    return out


def fetch_qb1(season: int, timeout: int = 120) -> dict[str, str]:
    """{team: QB1 name} from the most recent depth-chart snapshot.

    Streamed so the 48MB file is never held in memory. LIMITATION: this is
    the latest snapshot, so a mid-season change of starter is applied to
    every week. Fine for current-week flagging; a stricter version would
    pick the snapshot preceding each game.
    """
    out: dict[str, tuple[str, str]] = {}
    with requests.get(DEPTH_URL.format(season=season), stream=True,
                      timeout=timeout) as r:
        r.raise_for_status()
        lines = (ln.decode("utf-8", "replace") for ln in r.iter_lines() if ln)
        for row in csv.DictReader(lines):
            if row.get("pos_abb") != "QB" or row.get("pos_rank") != "1":
                continue
            team = norm_team(row.get("team"))
            dt = row.get("dt") or ""
            if team and (team not in out or dt > out[team][1]):
                out[team] = (row.get("player_name") or "", dt)
    return {t: nm for t, (nm, _) in out.items()}


def load(season: int) -> dict:
    """Everything needed to flag a season's games. Cache this."""
    return dict(attempts=fetch_qb_attempts(season), qb1=fetch_qb1(season))


def flag_game(season: int, week: int, away: str, home: str,
              data: dict | None) -> dict:
    """Return {'clean': True|False|None, 'reason': str, 'detail': str}.

    clean=None means undetermined (stats not published yet, QB1 unknown) and
    is never treated as clean.
    """
    if not data:
        return dict(clean=None, reason="unknown", detail="no nflverse data")
    attempts, qb1s = data.get("attempts") or {}, data.get("qb1") or {}
    reasons, undetermined = [], []
    for team in (away, home):
        rows = attempts.get((int(week), norm_team(team)))
        if not rows:
            undetermined.append(f"{team}: no passing stats yet "
                                "(nflverse publishes within ~a day)")
            continue
        total = sum(a for _, a in rows)
        if total < MIN_TEAM_ATTEMPTS:
            continue
        starter = qb1s.get(norm_team(team))
        if not starter:
            undetermined.append(f"{team}: QB1 unknown")
            continue
        key = norm_name(starter)
        att = next((a for nm, a in rows if norm_name(nm) == key), 0)
        if (att / total) < QB1_SHARE:
            reasons.append(f"{team} starter {starter} threw {att}/{total}")
    if reasons:
        return dict(clean=False, reason="QB did not finish",
                    detail="; ".join(reasons))
    if undetermined:
        return dict(clean=None, reason="unknown", detail="; ".join(undetermined))
    return dict(clean=True, reason="", detail="")
