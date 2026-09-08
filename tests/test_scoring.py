"""Validate the scoring engine on the DAL @ DET Week 14 Thursday-night game
from the original spreadsheet, plus rule unit checks."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from walters.scoring import GameContext, TeamGameState, score_game, compute_factors

def make_dal_det():
    home = TeamGameState("DET", category="Average", last_game_day="Thu", last_game_venue="H")
    away = TeamGameState("DAL", category="Average", last_game_day="Thu", last_game_venue="A")
    g = GameContext(week=14, home=home, away=away,
                    kickoff_et_hour=20.25, temp_f=18.34)  # Ford Field: dome, temp ignored
    g.game_day = "Thu"
    return g

def test_dal_det_factors():
    g = make_dal_det()
    hits = compute_factors(g)
    names = {h.name: (h.units, h.side) for h in hits}
    # Both turf teams -> same turf +1 away
    assert names.get("Same turf") == (1, "away"), names
    # Thursday night home +2
    assert names.get("Home team Thursday night") == (2, "home"), names
    # Night game penalizes CT away team (DAL) +3 home
    assert names.get("Night game penalizes CT away team") == (3, "home"), names
    # DET is ET home team at night -> +6 away
    assert names.get("Night game penalizes ET home team") == (6, "away"), names
    # Ford Field is a dome: no warm-to-cold despite 18F outside
    assert "Warm away team into cold" not in names, names

def test_book_scale():
    g = make_dal_det()
    res = score_game(g, home_power=2.18, away_power=0.0, hfa=1.9, factor_scale=0.2)
    # home units 5, away units 7 -> net -2 units -> -0.4 pts
    assert res.home_units == 5 and res.away_units == 7, (res.home_units, res.away_units)
    assert abs(res.factor_points_home - (-0.4)) < 1e-9
    assert abs(res.predicted_home_margin - (2.18 + 1.9 - 0.4)) < 1e-6
    assert abs(res.walters_home_line - (-3.68)) < 1e-6

def test_legacy_scale_diverges():
    g = make_dal_det()
    book = score_game(g, 2.18, 0.0, factor_scale=0.2)
    legacy = score_game(g, 2.18, 0.0, factor_scale=1.0)
    assert abs(legacy.factor_points_home) == 5 * abs(book.factor_points_home)

def test_bye_table():
    home = TeamGameState("GB", category="Great", off_bye=True)
    away = TeamGameState("CHI", category="Below Average", off_bye=True)
    g = GameContext(week=6, home=home, away=away, kickoff_et_hour=13.0)
    g.game_day = "Sun"
    hits = {h.name: (h.units, h.side) for h in compute_factors(g)}
    assert hits["Great team off bye (home)"] == (7, "home")
    assert hits["Below Average team off bye (away)"] == (5, "away")

def test_monday_hangover():
    away = TeamGameState("MIN", last_game_day="Mon", last_game_venue="A")
    home = TeamGameState("CHI")
    g = GameContext(week=5, home=home, away=away, kickoff_et_hour=13.0)
    g.game_day = "Sun"
    hits = {h.name: (h.units, h.side) for h in compute_factors(g)}
    assert hits["Away team off Monday night (was away)"] == (8, "home")

def test_blowout_bounce():
    home = TeamGameState("NYJ", last_margin=-31)
    away = TeamGameState("MIA", last_margin=-20)
    g = GameContext(week=3, home=home, away=away, kickoff_et_hour=13.0)
    g.game_day = "Sun"
    hits = {h.name for h in compute_factors(g)}
    assert "NYJ lost previous by 29+" in hits
    assert "MIA lost previous by 19+" in hits

def test_warm_to_cold():
    home = TeamGameState("GB")
    away = TeamGameState("MIA")   # warm team
    g = GameContext(week=15, home=home, away=away, kickoff_et_hour=13.0, temp_f=17)
    g.game_day = "Sun"
    hits = {h.name: (h.units, h.side) for h in compute_factors(g)}
    assert hits["Warm away team into cold"] == (1.0, "home")




def test_intl_symmetric_travel():
    from walters.scoring import GameContext, TeamGameState, compute_factors
    g = GameContext(week=4, home=TeamGameState("MIN"), away=TeamGameState("PIT"),
                    kickoff_et_hour=9.5, neutral_site=True)
    g.game_day = "Sun"
    g.venue_latlon = (53.3607, -6.251)  # Croke Park, Dublin
    hits = {h.name: h.side for h in compute_factors(g)}
    assert "Away travel 2000+ mi (neutral site)" in hits
    assert "Home travel 2000+ mi (neutral site)" in hits  # nets to zero
    assert not any("Night game" in n or "Thursday" in n for n in hits)

def test_grade_pick():
    from walters.history import grade_pick
    assert grade_pick('SEA', 'SEA', 'NE', -3.5, 27, 23) == 'W'
    assert grade_pick('SEA', 'SEA', 'NE', -3.5, 26, 23) == 'L'
    assert grade_pick('NE', 'SEA', 'NE', -3.5, 26, 23) == 'W'
    assert grade_pick('SEA', 'SEA', 'NE', -3.0, 26, 23) == 'P'
    assert grade_pick('', 'SEA', 'NE', -3.0, 26, 23) is None


def test_bucket_and_units():
    from walters.history import bucket_stats, overall
    g = [dict(edge=1.5, result='W'), dict(edge=6.0, result='W'),
         dict(edge=6.0, result='L'), dict(edge=9, result='W')]
    b = {r['bucket']: r for r in bucket_stats(g)}
    assert b['1-2 pts']['n'] == 1 and b['5-8 pts']['win_pct'] == 50.0
    o = overall(g)
    assert o['W'] == 3 and o['L'] == 1 and abs(o['units'] - 1.9) < 1e-9


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"PASS {f.__name__}")
    print(f"\n{len(fns)} tests passed.")
