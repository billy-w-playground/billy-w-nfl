"""The Odds API — live NFL spreads/totals. Free tier: 500 req/mo.

Get a key at https://the-odds-api.com. Optional: if absent, the app uses
ESPN's embedded odds instead.
"""
from __future__ import annotations
import requests

from ..teams import resolve

BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"


def fetch(api_key: str, timeout: int = 20) -> dict[tuple[str, str], dict]:
    """Return {(away, home): {'home_spread': float, 'total': float}} using a
    consensus (median across books)."""
    r = requests.get(BASE, params=dict(
        apiKey=api_key, regions="us", markets="spreads,totals", oddsFormat="american",
    ), timeout=timeout)
    r.raise_for_status()
    out: dict[tuple[str, str], dict] = {}
    for game in r.json():
        home = resolve(game.get("home_team", ""))
        away = resolve(game.get("away_team", ""))
        if not home or not away:
            continue
        spreads, totals = [], []
        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] == "spreads":
                    for oc in market.get("outcomes", []):
                        if resolve(oc.get("name", "")) == home and oc.get("point") is not None:
                            spreads.append(float(oc["point"]))
                elif market["key"] == "totals":
                    for oc in market.get("outcomes", []):
                        if oc.get("name") == "Over" and oc.get("point") is not None:
                            totals.append(float(oc["point"]))
        def med(xs):
            if not xs:
                return None
            xs = sorted(xs)
            return xs[len(xs) // 2]
        out[(away, home)] = dict(home_spread=med(spreads), total=med(totals))
    return out
