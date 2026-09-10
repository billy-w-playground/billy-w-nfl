"""ESPN depth charts — who actually starts.

The injury feed says a player is Out; it does not say whether he is the
starter or third string. This module supplies the missing rank so a backup
QB's absence stops looking like a starter's.

Endpoint (verified against a live response, Sep 2026):
  site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{id}/depthcharts
    -> depthchart[]            formation groups ("Base 3-4 D", offense, ...)
         .positions{slot}      slot key, e.g. "qb", "lde"
            .position          {abbreviation, parent:{abbreviation}}
            .athletes[]        ORDERED: index 0 is the starter

Team ids are read from the teams endpoint rather than hardcoded, so a
franchise move or id change doesn't silently break the mapping.
"""
from __future__ import annotations
import re

import requests

from ..teams import resolve

TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
DEPTH_URL = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
             "teams/{id}/depthcharts")
HEADERS = {"User-Agent": "Mozilla/5.0 (walters-model)"}


def norm_name(name: str) -> str:
    """'A.J. Brown' / 'AJ Brown' / 'A J Brown' -> 'ajbrown'."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


def team_ids(timeout: int = 20) -> dict[str, str]:
    """{abbr: espn_team_id}."""
    r = requests.get(TEAMS_URL, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    out: dict[str, str] = {}
    for grp in r.json().get("sports", [{}])[0].get("leagues", [{}])[0] \
            .get("teams", []):
        t = grp.get("team", {})
        abbr = resolve(t.get("abbreviation") or t.get("displayName", ""))
        if abbr and t.get("id"):
            out[abbr] = str(t["id"])
    return out


def fetch_team(espn_id: str, timeout: int = 20) -> dict[str, tuple[str, int]]:
    """{normalized_name: (position_abbr, depth_rank)} — rank 1 = starter.

    A player can appear in several formation groups; the BEST (lowest) rank
    wins, so a starter listed deep in a nickel package still reads as QB1.
    """
    r = requests.get(DEPTH_URL.format(id=espn_id), headers=HEADERS,
                     timeout=timeout)
    r.raise_for_status()
    out: dict[str, tuple[str, int]] = {}
    for group in r.json().get("depthchart", []):
        for slot in (group.get("positions") or {}).values():
            pos = (slot.get("position") or {})
            abbr = (pos.get("abbreviation")
                    or (pos.get("parent") or {}).get("abbreviation") or "?")
            for rank, ath in enumerate(slot.get("athletes") or [], start=1):
                key = norm_name(ath.get("displayName", ""))
                if not key:
                    continue
                prev = out.get(key)
                if prev is None or rank < prev[1]:
                    out[key] = (abbr.upper(), rank)
    return out


def fetch_all(timeout: int = 20) -> dict[str, dict[str, tuple[str, int]]]:
    """{team_abbr: {normalized_name: (pos, rank)}}. Missing teams are skipped."""
    ids = team_ids(timeout)
    out: dict[str, dict[str, tuple[str, int]]] = {}
    for abbr, tid in ids.items():
        try:
            out[abbr] = fetch_team(tid, timeout)
        except Exception:
            continue
    return out


# --- suggested point values (Walters' guide, applied conservatively) -------
OUT_STATUSES = {"out", "doubtful", "injured reserve", "ir",
                "physically unable to perform", "pup", "suspension"}
SOFT_STATUSES = {"questionable"}

# position group -> (points if starter OUT, points if starter QUESTIONABLE)
VALUES = {
    "QB": (7.0, 3.0),
    "WR": (2.0, 0.75), "TE": (1.5, 0.5), "RB": (1.0, 0.25),
    "LT": (2.0, 0.75), "OT": (2.0, 0.75), "OL": (1.5, 0.5),
    "C": (1.5, 0.5), "G": (1.0, 0.25),
    "DE": (2.0, 0.75), "DT": (1.5, 0.5), "EDGE": (2.0, 0.75),
    "CB": (1.5, 0.5), "S": (1.0, 0.25), "LB": (1.0, 0.25),
}


def suggest(team_injuries: list[dict],
            team_depth: dict[str, tuple[str, int]]) -> tuple[float, list[dict]]:
    """Return (total_points_off, per-player detail) for one team.

    Only STARTERS (depth rank 1) score. Everyone else is treated as zero,
    consistent with Walters' point that ~60% of players are worth nothing to
    a spread — and with the finding that Vegas prices barely 45 players a
    season above zero.
    """
    total = 0.0
    detail = []
    for p in team_injuries:
        status = (p.get("status") or "").lower()
        if status not in OUT_STATUSES | SOFT_STATUSES:
            continue
        key = norm_name(p.get("name", ""))
        pos, rank = team_depth.get(key, (p.get("position", "?"), None))
        pts = 0.0
        if rank == 1:
            base = VALUES.get(pos.upper())
            if base is None:
                base = VALUES.get((p.get("position") or "").upper(), (0.0, 0.0))
            pts = base[0] if status in OUT_STATUSES else base[1]
        detail.append(dict(name=p.get("name"), pos=pos,
                           depth=("starter" if rank == 1
                                  else (f"#{rank}" if rank else "not listed")),
                           status=p.get("status"), points=pts))
        total += pts
    total = round(total * 2) / 2   # nearest half point
    return total, detail
