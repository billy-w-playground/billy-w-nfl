"""Backtest / self-grading: how do Walters edges actually perform?

For any completed week, ESPN's scoreboard carries both the final score and
the market spread, so the app can re-run the model and grade every pick
against the number without storing anything.

METHODOLOGICAL WARNING (surfaced in the UI too): power ratings are fetched
CURRENT, not as-of that week. Sonny Moore's ratings for Week 6 already
reflect Weeks 1-5 results, so grading past weeks with today's ratings gives
the model information it would not have had — look-ahead bias that flatters
the record. Treat backtested numbers as a sanity check on the FACTOR logic,
not as proof of edge. An honest forward record needs a weekly snapshot of
the board, which the Walters tab's download button produces.
"""
from __future__ import annotations

from .pipeline import run_week


def grade_pick(bet_side: str, home: str, away: str, market_home_spread: float,
               home_score: int, away_score: int) -> str | None:
    """Return 'W' / 'L' / 'P' for the bet against the number."""
    if not bet_side or market_home_spread is None:
        return None
    margin = home_score - away_score
    if bet_side == home:
        result = margin + market_home_spread
    else:
        result = -margin - market_home_spread
    if abs(result) < 1e-9:
        return "P"
    return "W" if result > 0 else "L"


def grade_weeks(season: int, weeks: list[int], sonny: dict[str, float],
                hfa: float, factor_scale: float,
                sb_winner: str | None, sb_loser: str | None) -> list[dict]:
    """Re-run and grade every completed game in the given weeks."""
    graded: list[dict] = []
    for wk in weeks:
        try:
            results = run_week(season, wk, None, sonny, odds_lookup=None,
                               hfa=hfa, factor_scale=factor_scale,
                               sb_winner=sb_winner, sb_loser=sb_loser,
                               fetch_weather=False, injuries={})
        except Exception:
            continue
        for r in results:
            if not r.get("completed_scores"):
                continue
            hs, as_ = r["home_score"], r["away_score"]
            res = grade_pick(r["bet_side"], r["home"], r["away"],
                             r["market_home_spread"], hs, as_)
            if res is None:
                continue
            graded.append(dict(
                week=wk, away=r["away"], home=r["home"],
                bet=r["bet_side"], edge=r["edge"],
                walters=r["walters_home_line"],
                market=r["market_home_spread"],
                score=f"{as_}-{hs}", result=res,
            ))
    return graded


EDGE_BUCKETS = [(1, 2), (2, 3), (3, 5), (5, 8), (8, 99)]


def bucket_stats(graded: list[dict]) -> list[dict]:
    """Win% by absolute-edge bucket — the core question: bigger edge, better?"""
    rows = []
    for lo, hi in EDGE_BUCKETS:
        sel = [g for g in graded
               if g["edge"] is not None and lo <= abs(g["edge"]) < hi]
        w = sum(1 for g in sel if g["result"] == "W")
        l = sum(1 for g in sel if g["result"] == "L")
        p = sum(1 for g in sel if g["result"] == "P")
        decided = w + l
        label = f"{lo}-{hi} pts" if hi < 99 else f"{lo}+ pts"
        rows.append(dict(
            bucket=label, n=len(sel), W=w, L=l, P=p,
            win_pct=round(100 * w / decided, 1) if decided else None,
        ))
    return rows


def overall(graded: list[dict]) -> dict:
    w = sum(1 for g in graded if g["result"] == "W")
    l = sum(1 for g in graded if g["result"] == "L")
    p = sum(1 for g in graded if g["result"] == "P")
    decided = w + l
    # -110 juice: risk 1.1 to win 1.0
    units = round(w * 1.0 - l * 1.1, 2)
    return dict(W=w, L=l, P=p, n=len(graded),
                win_pct=round(100 * w / decided, 1) if decided else None,
                units=units,
                breakeven=52.4)


def grade_snapshots(season: int, saved: list[tuple[int, str]]) -> list[dict]:
    """Grade saved pre-kickoff boards against actual results. No look-ahead:
    the picks are exactly what the model produced at save time."""
    import csv as _csv
    import io as _io

    from .datasources import espn

    graded: list[dict] = []
    for wk, text in saved:
        try:
            games = {(g["away"], g["home"]): g
                     for g in espn.fetch_week(season, wk)}
        except Exception:
            continue
        for row in _csv.DictReader(_io.StringIO(text)):
            bet = (row.get("Bet") or "").strip()
            if not bet:
                continue
            away, home = row.get("Away"), row.get("Home")
            g = games.get((away, home))
            if not g or not g.get("completed"):
                continue
            # bet string is like "SEA -3.5" — side is the first token
            side = bet.split()[0]
            try:
                market = float(row.get("Market (Home)"))
                edge = float(row.get("Edge"))
            except (TypeError, ValueError):
                continue
            res = grade_pick(side, home, away, market,
                             g["home_score"], g["away_score"])
            if res is None:
                continue
            graded.append(dict(
                week=wk, away=away, home=home, bet=bet, edge=edge,
                walters=row.get("Walters (Home)"), market=market,
                score=f"{g['away_score']}-{g['home_score']}", result=res,
            ))
    return graded
