"""Billy Walters game-factor scoring engine.

Implements the factor table from the book chapter verbatim. Every factor
awards raw units to either the home or away side of THIS game. Per the
book: "Each number in these factors is worth one-fifth of a point" —
raw units are converted to point-spread points via FACTOR_SCALE.

FACTOR_SCALE = 0.2  -> book specification (default)
FACTOR_SCALE = 1.0  -> the legacy spreadsheet's (buggy) raw weighting,
                       kept only for back-comparison.

Predicted home margin =
    (home_power - away_power) + HFA + FACTOR_SCALE * (home_units - away_units)

Walters home line = -predicted_home_margin (negative = home favored),
so it compares directly to a market home spread.
"""

from dataclasses import dataclass, field
from math import radians, sin, cos, asin, sqrt

from .teams import TEAMS, TZ_OFFSET

BOOK_FACTOR_SCALE = 0.2


@dataclass
class TeamGameState:
    """Per-team situational inputs for one game."""
    abbr: str
    category: str = "Average"          # "Great" / "Average" / "Below Average"
    last_game_day: str | None = None   # "Sun", "Mon", "Thu", ... None = bye/none
    last_game_venue: str | None = None  # "H" or "A"
    last_game_ot: bool = False
    last_margin: float | None = None   # signed margin of their previous game
    off_bye: bool = False
    third_away_in_four: bool = False   # away team only
    second_straight_2tz: bool = False  # away team only
    sb_winner: bool = False
    sb_loser: bool = False
    playoff_bye: bool = False


@dataclass
class GameContext:
    week: int
    home: TeamGameState
    away: TeamGameState
    kickoff_local_hour: float | None = None   # venue-local, 24h
    kickoff_et_hour: float | None = None      # Eastern, 24h
    neutral_site: bool = False                # international games etc.
    temp_f: float | None = None
    rain: bool = False
    travel_miles: float | None = None         # away team travel; computed if None
    notes: list = field(default_factory=list)


@dataclass
class FactorHit:
    name: str
    units: float
    side: str   # "home" or "away"


def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 3956 * 2 * asin(sqrt(a))


def _warm_to_cold_units(temp_f: float) -> float:
    if temp_f is None:
        return 0.0
    if 30 <= temp_f <= 35:
        return 0.25
    if 25 <= temp_f < 30:
        return 0.5
    if 20 <= temp_f < 25:
        return 0.75
    if 15 <= temp_f < 20:
        return 1.0
    if 10 <= temp_f < 15:
        return 1.25
    if temp_f < 10:
        return 1.75
    return 0.0


def compute_factors(g: GameContext) -> list[FactorHit]:
    """Return every factor that fires for this game, in raw book units."""
    hits: list[FactorHit] = []
    H, A = TEAMS[g.home.abbr], TEAMS[g.away.abbr]

    def hit(name, units, side):
        if units:
            hits.append(FactorHit(name, units, side))

    # --- Turf / division / conference -------------------------------------
    if H["turf"] == A["turf"]:
        hit("Same turf", 1, "away")
    else:
        hit("Opposite turf", 1, "home")
    same_div = H["conference"] == A["conference"] and H["division"] == A["division"]
    if same_div:
        hit("Same division", 1, "away")
    if H["conference"] != A["conference"]:
        hit("Different conferences", 1, "home")

    # --- Primetime (skip on neutral sites: no true home crowd) ------------
    et = g.kickoff_et_hour
    if not g.neutral_site and et is not None:
        # Day-of-week comes from the schedule feed via context notes; the
        # caller passes game_day on the context when known.
        day = getattr(g, "game_day", None)
        if day == "Thu" and et >= 18:
            hit("Home team Thursday night", 2, "home")
        if day == "Sun" and et >= 20:
            hit("Home team Sunday night", 4, "home")
        if day == "Mon" and et >= 18:
            hit("Home team Monday night", 2, "home")

    # --- Coming off Monday night ------------------------------------------
    # Book: home off MNF then away next = +4 away (their opponent)... the
    # table is written from the perspective of the CURRENT game's sides:
    #   Home team coming off Monday night and home = 0
    #   Home team coming off Monday night and away = +4 away  (n/a here:
    #       if they're home this week this row can't fire for this game)
    #   Away team coming off Monday night and home = +6 home
    #   Away team coming off Monday night and away = +8 home
    if g.away.last_game_day == "Mon":
        if g.away.last_game_venue == "H":
            hit("Away team off Monday night (was home)", 6, "home")
        elif g.away.last_game_venue == "A":
            hit("Away team off Monday night (was away)", 8, "home")

    # --- Overtime hangover -------------------------------------------------
    if g.home.last_game_ot:
        units = 4 if g.home.last_game_venue == "H" else 2
        hit("Home team off OT game", units, "away")
    if g.away.last_game_ot:
        units = 4 if g.away.last_game_venue == "H" else 2
        hit("Away team off OT game", units, "home")

    # --- Byes ---------------------------------------------------------------
    def bye_units(cat: str, is_away: bool) -> float:
        table = {
            ("Below Average", False): 8, ("Below Average", True): 5,
            ("Average", False): 5, ("Average", True): 6,
            ("Great", False): 7, ("Great", True): 8,
        }
        return table.get((cat, is_away), 5)

    if g.home.off_bye:
        hit(f"{g.home.category} team off bye (home)", bye_units(g.home.category, False), "home")
    if g.away.off_bye:
        hit(f"{g.away.category} team off bye (away)", bye_units(g.away.category, True), "away")
    if g.home.playoff_bye:
        hit("Bye in playoffs", 1, "home")

    # --- Super Bowl carryover ----------------------------------------------
    for side_name, st in (("home", g.home), ("away", g.away)):
        opp = "away" if side_name == "home" else "home"
        if st.sb_winner:
            if g.week == 1:
                hit(f"SB winner first game ({st.abbr})", 4, side_name)
            elif g.week <= 4:
                hit(f"SB winner weeks 2-4 ({st.abbr})", 2, side_name)
        if st.sb_loser:
            if g.week == 1:
                hit(f"SB loser first game ({st.abbr})", 4, opp)
            elif g.week <= 4:
                hit(f"SB loser weeks 2-4 ({st.abbr})", 2, opp)

    # --- Schedule fatigue ---------------------------------------------------
    if g.away.third_away_in_four:
        hit("Away team's 3rd away game in 4", 2, "home")
    if g.away.second_straight_2tz:
        hit("2nd straight game 2+ time zones away", 2, "home")

    # --- Travel -------------------------------------------------------------
    # Book rule: away travel 2000+ miles = +1 home. At neutral/international
    # sites we apply it symmetrically: each team traveling 2000+ miles to the
    # actual venue credits its OPPONENT 1 unit (so London usually nets zero
    # unless one side is materially closer or stayed abroad).
    if g.neutral_site:
        venue = getattr(g, "venue_latlon", None)
        if venue:
            vh = haversine_miles(H["lat"], H["lon"], venue[0], venue[1])
            va = haversine_miles(A["lat"], A["lon"], venue[0], venue[1])
            g.travel_miles = va
            if va > 2000:
                hit("Away travel 2000+ mi (neutral site)", 1, "home")
            if vh > 2000:
                hit("Home travel 2000+ mi (neutral site)", 1, "away")
    else:
        miles = g.travel_miles
        if miles is None:
            miles = haversine_miles(A["lat"], A["lon"], H["lat"], H["lon"])
            g.travel_miles = miles
        if miles > 2000:
            hit("Away travel 2000+ miles", 1, "home")

    # --- Proximity (an away-team advantage when visiting near-home turf) ---
    prox_units = {"FL": 1, "TX": 1, "SE": 1, "LA": 2, "LV_LA": 1,
                  "IND_CIN": 1, "NE": 1, "NYG_NYJ": 2, "BAL_WAS": 2, "CHI_GB": 1}
    for tag, u in prox_units.items():
        if tag in A["proximity"] and tag in H["proximity"] and g.home.abbr != g.away.abbr:
            hit(f"Proximity {tag}", u, "away")

    # --- Body clock ---------------------------------------------------------
    if not g.neutral_site and et is not None:
        away_tz, home_tz = A["tz"], H["tz"]
        if abs(et - 13) < 0.5:  # 1pm ET kickoffs
            if away_tz == "PT":
                hit("1pm ET kickoff penalizes West away team", 2, "home")
            elif away_tz == "MT":
                hit("1pm ET kickoff penalizes Mountain away team", 1, "home")
            if home_tz == "PT":
                hit("1pm ET kickoff penalizes West home team", 2, "away")
            elif home_tz == "MT":
                hit("1pm ET kickoff penalizes Mountain home team", 1, "away")
        if et >= 18:  # night games penalize eastern/central body clocks
            night_units = {"ET": 6, "CT": 3, "MT": 1}
            if away_tz in night_units:
                hit(f"Night game penalizes {away_tz} away team", night_units[away_tz], "home")
            if home_tz in night_units:
                hit(f"Night game penalizes {home_tz} home team", night_units[home_tz], "away")

    # --- Blowout bounce-back -----------------------------------------------
    for side_name, st in (("home", g.home), ("away", g.away)):
        if st.last_margin is not None and st.last_margin <= -29:
            hit(f"{st.abbr} lost previous by 29+", 4, side_name)
        elif st.last_margin is not None and st.last_margin <= -19:
            hit(f"{st.abbr} lost previous by 19+", 2, side_name)

    # --- Weather ------------------------------------------------------------
    outdoor_cold_venue = (not H["dome"]) and (not g.neutral_site)
    if outdoor_cold_venue and g.temp_f is not None:
        if A["climate"] == "Warm":
            u = _warm_to_cold_units(g.temp_f)
            hit("Warm away team into cold", u, "home")
        if A["dome"] and A["climate"] == "Cold":
            if 20 <= g.temp_f <= 30:
                hit("Cold dome away team outdoors 20-30F", 0.25, "home")
            elif 10 <= g.temp_f < 20:
                hit("Cold dome away team outdoors 10-20F", 0.5, "home")
            elif 5 <= g.temp_f < 10:
                hit("Cold dome away team outdoors 5-10F", 0.25, "away")
            if g.rain:
                hit("Cold dome away team in rain", 0.75, "away")

    return hits


@dataclass
class WaltersResult:
    home_units: float
    away_units: float
    factor_points_home: float   # net factor points credited to home margin
    predicted_home_margin: float
    walters_home_line: float
    hits: list[FactorHit]


def score_game(g: GameContext, home_power: float, away_power: float,
               hfa: float = 1.9,
               factor_scale: float = BOOK_FACTOR_SCALE) -> WaltersResult:
    hits = compute_factors(g)
    hu = sum(h.units for h in hits if h.side == "home")
    au = sum(h.units for h in hits if h.side == "away")
    factor_pts = factor_scale * (hu - au)
    hfa_used = 0.0 if g.neutral_site else hfa
    margin = (home_power - away_power) + hfa_used + factor_pts
    return WaltersResult(
        home_units=hu, away_units=au,
        factor_points_home=round(factor_pts, 2),
        predicted_home_margin=round(margin, 2),
        walters_home_line=round(-margin, 2),
        hits=hits,
    )
