"""NFL injury reports via ESPN.

Primary: the aggregate injuries endpoint used by ESPN's injuries page.
Fallback: per-team site API. Both are unofficial; on any failure this
returns {} and the app shows 'injury data unavailable' rather than dying.

Output: {abbr: {"players": [{"name","position","status"}],
                "count": int, "qb_flag": bool}}
qb_flag = any QB with status Out / Doubtful / Injured Reserve / PUP.
"""
from __future__ import annotations
import requests

from ..teams import TEAMS, resolve

AGG_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
TEAM_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{abbr}"

BAD_STATUSES = {"out", "doubtful", "injured reserve", "ir",
                "physically unable to perform", "pup", "suspension"}
SOFT_STATUSES = {"questionable"}


def _classify(players: list[dict]) -> dict:
    qb_flag = any(
        p["position"].upper() == "QB"
        and p["status"].lower() in BAD_STATUSES | SOFT_STATUSES
        for p in players
    )
    return {"players": players, "count": len(players), "qb_flag": qb_flag}


def fetch(timeout: int = 20) -> dict[str, dict]:
    try:
        r = requests.get(AGG_URL, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0 (walters-model)"})
        r.raise_for_status()
        data = r.json()
        out: dict[str, dict] = {}
        for team_blob in data.get("injuries", []):
            abbr = resolve(team_blob.get("displayName", "")
                           or team_blob.get("team", {}).get("displayName", ""))
            if not abbr:
                continue
            players = []
            for inj in team_blob.get("injuries", []):
                ath = inj.get("athlete", {})
                players.append(dict(
                    name=ath.get("displayName", "?"),
                    position=(ath.get("position", {}) or {}).get(
                        "abbreviation", "?"),
                    status=inj.get("status", "?"),
                ))
            out[abbr] = _classify(players)
        if out:
            return out
    except Exception:
        pass

    # Fallback: per-team (slower, 32 calls)
    out = {}
    for abbr in TEAMS:
        try:
            r = requests.get(TEAM_URL.format(abbr=abbr.lower()),
                             params={"enable": "injuries"}, timeout=timeout)
            r.raise_for_status()
            team = r.json().get("team", {})
            players = []
            for inj in team.get("injuries", []) or []:
                ath = inj.get("athlete", {})
                players.append(dict(
                    name=ath.get("displayName", "?"),
                    position=(ath.get("position", {}) or {}).get(
                        "abbreviation", "?"),
                    status=inj.get("status", "?"),
                ))
            out[abbr] = _classify(players)
        except Exception:
            continue
    return out
