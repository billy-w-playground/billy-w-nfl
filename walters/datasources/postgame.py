"""Post-game data-quality flags: was this the team we actually modelled?

The point is NOT to excuse losses. A pick-six that flips a cover is football
and stays in the record. What justifies a flag is INPUT INVALIDATION — the
starting quarterback left early, so the team that played is not the team the
power ratings priced.

Detection is by usage, not by injury report: if a team's leading passer threw
only a small share of its attempts while another quarterback threw most of
them, the starter did not finish. That catches an exit on the first drive
without depending on anyone filing a report.

The flag is symmetric by construction — either team's starter exiting flags
the game — so it cannot quietly favour the bets you happened to win.

Endpoint: site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=ID
"""
from __future__ import annotations

import requests

SUMMARY = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
           "summary?event={eid}")
HEADERS = {
    # Keep this minimal. A parenthesised custom UA gets 403'd, and a full
    # browser CORS fingerprint (Origin/Sec-Fetch-*) gets 403'd too. A plain
    # standard User-Agent and nothing else is what passes.
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/152.0.0.0 Safari/537.36"),
}

MIN_TEAM_ATTEMPTS = 12      # ignore run-heavy blowouts / weather games
QB1_SHARE = 0.50            # depth-chart QB1 below this share = did not finish


def _attempts(stat: str) -> int:
    """'18/29' -> 29."""
    try:
        return int(str(stat).split("/")[1])
    except (IndexError, ValueError, AttributeError):
        return 0


def qb_usage(event_id: str, timeout: int = 20) -> dict:
    """{team_abbr: [(player, attempts), ...]} sorted by attempts desc."""
    r = requests.get(SUMMARY.format(eid=event_id), headers=HEADERS,
                     timeout=timeout)
    r.raise_for_status()
    data = r.json()
    out: dict[str, list[tuple[str, int]]] = {}
    for team_block in (data.get("boxscore") or {}).get("players", []):
        abbr = ((team_block.get("team") or {}).get("abbreviation") or "").upper()
        if not abbr:
            continue
        rows: list[tuple[str, int]] = []
        for statgroup in team_block.get("statistics", []):
            if str(statgroup.get("name", "")).lower() != "passing":
                continue
            keys = [str(k).upper() for k in (statgroup.get("keys") or [])]
            try:
                idx = keys.index("COMPLETIONS/PASSINGATTEMPTS")
            except ValueError:
                idx = 0     # ESPN's passing stats lead with C/ATT
            for ath in statgroup.get("athletes", []):
                name = (ath.get("athlete") or {}).get("displayName", "?")
                stats = ath.get("stats") or []
                att = _attempts(stats[idx]) if idx < len(stats) else 0
                if att:
                    rows.append((name, att))
        if rows:
            out[abbr] = sorted(rows, key=lambda x: -x[1])
    return out


def flag_game(event_id: str, depth_charts: dict | None = None,
              timeout: int = 20) -> dict:
    """Return {'clean': bool|None, 'reason': str, 'detail': str}.

    Method: find each team's depth-chart QB1 and measure his share of the
    team's pass attempts. A starter who leaves early has a tiny share even
    though a BACKUP may lead the game in attempts — which is why the
    depth chart is required rather than just picking the leading passer.

    A blowout where the starter finishes and a backup mops up is NOT
    flagged: QB1's share stays high. clean=None means undetermined (no
    stats yet, or QB1 could not be identified) — never treated as clean.
    """
    from .depth import norm_name

    try:
        usage = qb_usage(event_id, timeout)
    except Exception as e:
        msg = str(e)
        if "403" in msg:
            msg = "boxscore blocked (403)"
        elif "404" in msg:
            msg = "boxscore not published yet"
        return dict(clean=None, reason="unknown", detail=msg[:60])
    if not usage:
        return dict(clean=None, reason="unknown", detail="no passing stats")

    reasons, undetermined = [], []
    for abbr, rows in usage.items():
        total = sum(a for _, a in rows)
        if total < MIN_TEAM_ATTEMPTS:
            continue
        chart = (depth_charts or {}).get(abbr) or {}
        qb1 = next((nm for nm, (pos, rank) in chart.items()
                    if pos.upper() == "QB" and rank == 1), None)
        if not qb1:
            # fall back: two passers each with real volume is suspicious
            if len(rows) >= 2 and rows[1][1] >= 8:
                reasons.append(f"{abbr} two QBs used "
                               f"({rows[0][0]} {rows[0][1]}, "
                               f"{rows[1][0]} {rows[1][1]})")
            else:
                undetermined.append(abbr)
            continue
        qb1_att = next((a for nm, a in rows if norm_name(nm) == qb1), 0)
        if (qb1_att / total) < QB1_SHARE:
            starter_label = next((nm for nm, a in rows
                                  if norm_name(nm) == qb1), "QB1")
            reasons.append(f"{abbr} starter {starter_label} threw "
                           f"{qb1_att}/{total}")
    if reasons:
        return dict(clean=False, reason="QB did not finish",
                    detail="; ".join(reasons))
    if undetermined:
        return dict(clean=None, reason="unknown",
                    detail="QB1 not identified: " + ", ".join(undetermined))
    return dict(clean=True, reason="", detail="")
