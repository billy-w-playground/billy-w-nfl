"""ESPN unofficial scoreboard API: schedule, results, day/time, and odds.

Endpoint (undocumented but stable for years):
  https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
  ?dates=YYYY&seasontype=2&week=N        (seasontype 2 = regular season)
"""
from __future__ import annotations
import datetime as dt
import requests

from ..teams import resolve

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


def fetch_week(season: int, week: int, seasontype: int = 2, timeout: int = 20) -> list[dict]:
    """Return normalized game dicts for one week.

    Each dict: week, home, away, date_utc (ISO), game_day (Thu/Sun/...),
    kickoff_et_hour, neutral_site, completed, home_score, away_score,
    market_home_spread (None if no odds), over_under.
    """
    params = {"dates": season, "seasontype": seasontype, "week": week}
    r = requests.get(BASE, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    games = []
    for ev in data.get("events", []):
        comp = ev["competitions"][0]
        comps = comp["competitors"]
        home = next(c for c in comps if c["homeAway"] == "home")
        away = next(c for c in comps if c["homeAway"] == "away")
        h = resolve(home["team"].get("abbreviation") or home["team"]["displayName"])
        a = resolve(away["team"].get("abbreviation") or away["team"]["displayName"])
        if not h or not a:
            continue

        date_utc = dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo
        et = date_utc.astimezone(ZoneInfo("America/New_York"))

        odds = None
        ou = None
        for o in comp.get("odds", []):
            # spread is quoted for the favorite; homeTeamOdds tells side
            spread = o.get("spread")
            ou = o.get("overUnder", ou)
            if spread is not None:
                fav_home = o.get("homeTeamOdds", {}).get("favorite", None)
                if fav_home is True:
                    odds = -abs(spread)
                elif fav_home is False:
                    odds = abs(spread)
                else:
                    odds = spread  # ESPN spread is usually already home-relative
                break

        status = comp.get("status", {}).get("type", {})
        venue_name = (comp.get("venue", {}) or {}).get("fullName", "")
        games.append(dict(
            event_id=str(ev.get("id", "")),
            week=week,
            home=h, away=a,
            date_utc=date_utc.isoformat(),
            game_day=et.strftime("%a")[:3],
            kickoff_et_hour=et.hour + et.minute / 60,
            neutral_site=bool(comp.get("neutralSite", False)),
            venue=venue_name,
            completed=bool(status.get("completed", False)),
            home_score=int(home.get("score") or 0),
            away_score=int(away.get("score") or 0),
            market_home_spread=odds,
            over_under=ou,
        ))
    return games


def fetch_weeks(season: int, through_week: int) -> dict[int, list[dict]]:
    """Fetch weeks 1..through_week (used to derive last-game context)."""
    return {w: fetch_week(season, w) for w in range(1, through_week + 1)}
