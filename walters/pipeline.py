"""End-to-end pipeline: data feeds -> game contexts -> Walters lines."""
from __future__ import annotations

from .teams import TEAMS
from .scoring import (GameContext, TeamGameState, score_game,
                      BOOK_FACTOR_SCALE, haversine_miles)
from .datasources import espn, weather as wx
from .teams import intl_venue_lookup


def blend_power(massey: dict[str, float] | None,
                sonny: dict[str, float] | None) -> dict[str, float]:
    """Center each source at league mean (=> spread-equivalent points, avg 0
    per the book) and average available sources per team."""
    sources = [s for s in (massey, sonny) if s]
    if not sources:
        raise ValueError("Need at least one ratings source (Massey or Sonny Moore)")
    centered = []
    for s in sources:
        mean = sum(s.values()) / len(s)
        centered.append({k: v - mean for k, v in s.items()})
    out = {}
    for abbr in TEAMS:
        vals = [c[abbr] for c in centered if abbr in c]
        if vals:
            out[abbr] = sum(vals) / len(vals)
    return out


def categorize(power: dict[str, float]) -> dict[str, str]:
    """Great = top 8, Below Average = bottom 8, else Average (mirrors the
    original sheet's rank buckets)."""
    ranked = sorted(power, key=power.get, reverse=True)
    cat = {}
    for i, abbr in enumerate(ranked):
        cat[abbr] = "Great" if i < 8 else ("Below Average" if i >= len(ranked) - 8 else "Average")
    return cat


def _team_state(abbr: str, week: int, history: dict[int, list[dict]],
                cats: dict[str, str], sb_winner: str | None,
                sb_loser: str | None) -> TeamGameState:
    st = TeamGameState(abbr=abbr, category=cats.get(abbr, "Average"))
    st.sb_winner = abbr == sb_winner
    st.sb_loser = abbr == sb_loser

    prev = history.get(week - 1, [])
    last = next((g for g in prev if abbr in (g["home"], g["away"])), None)
    if last is None and week > 1:
        st.off_bye = True
    elif last is not None:
        st.last_game_day = last["game_day"]
        st.last_game_venue = "H" if last["home"] == abbr else "A"
        if last["completed"]:
            margin = last["home_score"] - last["away_score"]
            st.last_margin = margin if last["home"] == abbr else -margin
            # ESPN marks OT in status detail; approximate via score parity not
            # possible — leave last_game_ot False unless enriched upstream.

    # 3rd away in 4 / consecutive 2+ TZ trips need weeks back to week-3
    away_count = 0
    for w in range(max(1, week - 3), week + 1):
        for g in history.get(w, []):
            if g["away"] == abbr:
                away_count += 1
    st.third_away_in_four = away_count >= 3
    return st


def run_week(season: int, week: int,
             massey: dict[str, float] | None,
             sonny: dict[str, float] | None,
             odds_lookup: dict | None = None,
             hfa: float = 1.9,
             factor_scale: float = BOOK_FACTOR_SCALE,
             sb_winner: str | None = None,
             sb_loser: str | None = None,
             fetch_weather: bool = True,
             injuries: dict | None = None) -> list[dict]:
    """Fetch this week + prior 3 weeks of schedule, build contexts, score."""
    power = blend_power(massey, sonny)
    cats = categorize(power)

    history = {}
    for w in range(max(1, week - 3), week + 1):
        history[w] = espn.fetch_week(season, w)

    results = []
    for g in history[week]:
        home_st = _team_state(g["home"], week, history, cats, sb_winner, sb_loser)
        away_st = _team_state(g["away"], week, history, cats, sb_winner, sb_loser)
        # away team's 2nd straight 2+ TZ trip
        ht, at = TEAMS[g["home"]], TEAMS[g["away"]]
        from .teams import TZ_OFFSET
        prev = history.get(week - 1, [])
        last_away = next((p for p in prev if p["away"] == g["away"]), None)
        if last_away:
            last_home_tz = TZ_OFFSET[TEAMS[last_away["home"]]["tz"]]
            away_tz = TZ_OFFSET[at["tz"]]
            cur_home_tz = TZ_OFFSET[ht["tz"]]
            away_st.second_straight_2tz = (
                abs(away_tz - last_home_tz) >= 2 and abs(away_tz - cur_home_tz) >= 2
            )

        ctx = GameContext(week=week, home=home_st, away=away_st,
                          kickoff_et_hour=g["kickoff_et_hour"],
                          neutral_site=g["neutral_site"])
        ctx.game_day = g["game_day"]
        venue_recognized = True
        if g["neutral_site"]:
            ctx.venue_latlon = intl_venue_lookup(g.get("venue", ""))
            venue_recognized = ctx.venue_latlon is not None

        if fetch_weather and not ht["dome"] and not g["neutral_site"]:
            w_ = wx.kickoff_weather(ht["lat"], ht["lon"], g["date_utc"])
            ctx.temp_f, ctx.rain = w_["temp_f"], w_["rain"]

        res = score_game(ctx, power[g["home"]], power[g["away"]],
                         hfa=hfa, factor_scale=factor_scale)

        market = g["market_home_spread"]
        if odds_lookup:
            o = odds_lookup.get((g["away"], g["home"]))
            if o and o.get("home_spread") is not None:
                market = o["home_spread"]

        edge = None
        bet_side = ""
        if market is not None:
            edge = round(market - res.walters_home_line, 2)
            # market more generous to home than our line -> take home, else away
            if edge >= 1:
                bet_side = g["home"]
            elif edge <= -1:
                bet_side = g["away"]

        inj_h = (injuries or {}).get(g["home"], {})
        inj_a = (injuries or {}).get(g["away"], {})
        results.append(dict(
            week=week, away=g["away"], home=g["home"],
            game_day=g["game_day"],
            neutral_site=g["neutral_site"],
            venue=g.get("venue", ""),
            venue_recognized=venue_recognized,
            completed_scores=bool(g["completed"]),
            home_score=g["home_score"], away_score=g["away_score"],
            qb_flag=bool(inj_h.get("qb_flag") or inj_a.get("qb_flag")),
            injury_count=int(inj_h.get("count", 0)) + int(inj_a.get("count", 0)),
            injuries_home=inj_h.get("players", []),
            injuries_away=inj_a.get("players", []),
            home_power=round(power[g["home"]], 2),
            away_power=round(power[g["away"]], 2),
            factor_pts_home=res.factor_points_home,
            walters_home_line=res.walters_home_line,
            market_home_spread=market,
            edge=edge, bet_side=bet_side,
            temp_f=ctx.temp_f,
            factors=[(h.name, h.units, h.side) for h in res.hits],
        ))
    return results
