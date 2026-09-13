"""Billy Walters NFL model — Streamlit app.

Tabs: Walters Board | History & Edge Analysis
Run:  streamlit run app.py
"""
import datetime as dt

import pandas as pd
import streamlit as st

from walters.pipeline import run_week
from walters.scoring import BOOK_FACTOR_SCALE
from walters.datasources import splits as splits_api
from walters.datasources import (sonnymoore, odds as odds_api,
                                 injuries as inj_api, depth as depth_api)
from walters import history as hist
from walters import snapshots as snap
from walters import ratings as ratings_files

st.set_page_config(page_title="Walters NFL Model", page_icon="🏈", layout="wide")

BOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&family=IBM+Plex+Mono:wght@500;700&display=swap');
html, body, [data-testid="stAppViewContainer"] { background: #000 !important; }
h1 { font-family: 'VT323', monospace !important; color: #ffbf00 !important;
     letter-spacing: 2px; font-size: 3rem !important; }
[data-testid="stMetricValue"] { font-family: 'VT323', monospace;
     color: #00e63c; font-size: 2.6rem; }
[data-testid="stMetricLabel"] { color: #7a7a7a; }
button[data-baseweb="tab"] { font-family: 'VT323', monospace;
     font-size: 1.3rem; color: #00e63c; }
button[data-baseweb="tab"][aria-selected="true"] { color: #ffbf00; }
.board { width: 100%; border-collapse: collapse;
     font-family: 'IBM Plex Mono', monospace; font-size: 0.86rem;
     background: #000; }
.board th { color: #7a7a7a; text-align: left; font-weight: 500;
     border-bottom: 1px solid #262626; padding: 4px 10px;
     font-size: 0.72rem; }
.board td { padding: 5px 10px; border-bottom: 1px solid #141414;
     color: #ffbf00; font-weight: 700; white-space: nowrap; }
.board td.team { color: #00e63c; }
.board td.neg { color: #ff3b30; }
.board td.sig { color: #00e63c; }
.board td.dim { color: #555; font-weight: 500; }
.board tr:hover td { background: #0d0d0d; }
</style>
"""
st.markdown(BOARD_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)
def load_splits(season: int, week: int) -> dict:
    """Public bets%/money% from scoresandodds (server-rendered HTML)."""
    try:
        return splits_api.fetch(season, week)
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def load_qb_data(season: int) -> dict:
    """nflverse QB attempts + depth-chart QB1s, for post-game flagging."""
    from walters.datasources import postgame
    try:
        return postgame.load(season)
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def load_depth_charts() -> dict:
    """All 32 depth charts, cached — 33 requests, so not every rerun."""
    try:
        return depth_api.fetch_all()
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def default_week(season: int) -> int:
    """Current NFL week from ESPN, so saves land under the right number."""
    try:
        import requests as _rq
        r = _rq.get(
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
            timeout=10)
        r.raise_for_status()
        wk = int(r.json().get("week", {}).get("number", 1))
        return min(max(wk, 1), 18)
    except Exception:
        return 1


def parse_adjustments(text: str) -> dict:
    """'SEA:-7, NE:-2.5' -> {'SEA': -7.0, 'NE': -2.5}"""
    out = {}
    for chunk in (text or "").replace(";", ",").split(","):
        if ":" not in chunk:
            continue
        team, _, val = chunk.partition(":")
        from walters.teams import resolve as _res
        abbr = _res(team.strip())
        try:
            out[abbr] = float(val)
        except (TypeError, ValueError):
            continue
    return {k: v for k, v in out.items() if k}


def board_table(df, team_cols=(), signal_cols=(), dim_cols=()):
    """Render a dataframe as a Vegas-board HTML table."""
    import html as _html
    head = "".join(f"<th>{_html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            v = row[c]
            txt = "" if v is None or (isinstance(v, float) and pd.isna(v)) else v
            if isinstance(txt, float):
                txt = f"{txt:+.1f}" if c not in ("Injuries",) else f"{txt:.0f}"
            txt = _html.escape(str(txt))
            cls = ""
            if c in team_cols:
                cls = "team"
            elif c in signal_cols and str(v).strip():
                cls = "sig"
            elif c in dim_cols:
                cls = "dim"
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0:
                cls = "neg"
            cells.append(f'<td class="{cls}">{txt}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(f'<table class="board"><thead><tr>{head}</tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table>',
                unsafe_allow_html=True)


st.title("🏈 BILLY WALTERS NFL BOARD")

with st.sidebar:
    st.header("Run settings")
    today = dt.date.today()
    default_season = today.year if today.month >= 8 else today.year - 1
    season = st.number_input("Season", 2020, 2035, default_season)
    week = st.number_input("Week", 1, 18, default_week(int(season)),
                           help="Auto-detected from the schedule; override "
                                "if you want a different week.")
    hfa = st.slider(
        "Home field advantage (pts)", 0.0, 4.0, 1.0, 0.1,
        help="Commonly assumed to be 3. Measured 1974-2022 it is nearer 2.5, "
             "and in the four seasons before Walters' book it was under 1 "
             "point. Default 1.0 reflects the recent trend.")
    # Book spec only: the chapter is explicit that each factor unit is worth
    # one-fifth of a point. The old raw weighting was a spreadsheet bug.
    factor_scale = BOOK_FACTOR_SCALE

    st.divider()
    st.header("Injury adjustments")
    inj_text = st.text_input(
        "Points off, by team", "",
        placeholder="SEA:-7, NE:-2.5",
        help="Applied to that team's power rating. Walters' guide: a QB is "
             "worth about a touchdown (the best more), top non-QBs 2.5-3, "
             "and ~60% of players roughly zero. Not automated: ESPN's feed "
             "doesn't say who is a starter, and Questionable players usually "
             "play — so this stays your judgement call.")

    st.divider()
    st.header("Super Bowl carryover")
    from walters.teams import TEAMS as _T
    _opts = ["(none)"] + sorted(_T)
    sb_winner = st.selectbox("Last SB winner", _opts, index=_opts.index("SEA"))
    sb_loser = st.selectbox("Last SB loser", _opts, index=_opts.index("NE"))
    sb_winner = "" if sb_winner == "(none)" else sb_winner
    sb_loser = "" if sb_loser == "(none)" else sb_loser

    st.divider()
    st.header("Data sources")
    st.caption("Ratings: a committed `ratings/<season>_wk<NN>.csv` is used "
               "for that week; every other week uses Sonny Moore "
               "automatically.")

    use_weather = st.checkbox("Fetch weather (Open-Meteo)", True)
    use_injuries = st.checkbox("Fetch injury reports (ESPN)", True)

    odds_key = st.text_input("The Odds API key (optional)", type="password")


run = st.button("▶ Run model", type="primary", use_container_width=True)

# Streamlit reruns this whole script on ANY widget interaction (a checkbox,
# deleting a chip from a multiselect). Results therefore live in
# st.session_state so the board survives those reruns instead of vanishing
# and forcing another fetch.
if run:
    st.session_state.pop("run_data", None)

if not run and "run_data" not in st.session_state:
    st.info("Set the week and hit **Run model**. No keys needed for the "
            "defaults; The Odds API key improves market lines.")
    st.stop()

if not run:
    _d = st.session_state["run_data"]
    results = _d["results"]
    sonny_r = _d["sonny_r"]
    ratings_used = _d.get("ratings_used")
    had_file = _d.get("had_file", False)
    season, week = _d["season"], _d["week"]
    hfa, factor_scale = _d["hfa"], _d["factor_scale"]
    sb_winner, sb_loser = _d["sb_winner"], _d["sb_loser"]
    st.caption(f"Showing saved run: {season} week {week}. "
               "Hit **Run model** to refresh.")
else:
    prog = st.progress(0, "Power ratings…")
    warnings = []

    gh_repo_cfg = st.secrets.get("github_repo", "")
    # A committed ratings file wins for that week; otherwise Sonny Moore.
    # No toggle — the file's presence IS the choice. Read straight from the
    # repo checkout, so no secrets are involved.
    file_r = ratings_files.load_from_repo(gh_repo_cfg, int(season), int(week))

    sonny_r = None
    if file_r:
        st.success(f"Ratings: {ratings_files.path_for(int(season), int(week))} "
                   f"({len(file_r)} teams).")
    else:
        try:
            sonny_r = sonnymoore.fetch()
        except Exception as e:
            warnings.append(f"Sonny Moore fetch failed: {e}")

    prog.progress(20, "Odds…")

    odds_lookup = None
    if odds_key.strip():
        try:
            odds_lookup = odds_api.fetch(odds_key.strip())
        except Exception as e:
            warnings.append(f"Odds API failed: {e} — using ESPN lines.")
    prog.progress(35, "Injuries…")

    injuries = {}
    if use_injuries:
        injuries = inj_api.fetch()
        if not injuries:
            warnings.append("Injury fetch returned nothing — reports unavailable.")
    prog.progress(60, "Schedule, weather, scoring…")

    # Archive the UNADJUSTED ratings: injury points are a per-run overlay,
    # not part of a team's rating. Baking them in would double-count the
    # moment the week is re-run or re-graded.
    raw_ratings = dict(file_r or sonny_r or {})

    adjustments = parse_adjustments(inj_text)
    if adjustments:
        for _src in (file_r, sonny_r):
            if _src:
                for _abbr, _delta in adjustments.items():
                    if _abbr in _src:
                        _src[_abbr] = _src[_abbr] + _delta
        st.info("Injury adjustments applied: " +
                ", ".join(f"{k} {v:+g}" for k, v in adjustments.items()))

    if not sonny_r and not file_r:
        for w in warnings:
            st.warning(w)
        st.error(
            "No ratings available: Sonny Moore's fetch failed and there is no "
            "`" + ratings_files.path_for(int(season), int(week)) + "` in the "
            "repo. Commit that file (exact path, lowercase, zero-padded week) "
            "and rerun.")
        st.stop()

    try:
        results = run_week(int(season), int(week), file_r, sonny_r,
                           odds_lookup=odds_lookup, hfa=hfa,
                           factor_scale=factor_scale,
                           sb_winner=sb_winner.strip().upper() or None,
                           sb_loser=sb_loser.strip().upper() or None,
                           fetch_weather=use_weather, injuries=injuries)
    except Exception as e:
        st.error(f"Pipeline failed: {e}")
        st.stop()
    prog.progress(100, "Done")

    for w in warnings:
        st.warning(w)
    unknown_venues = [r["venue"] for r in results
                      if r["neutral_site"] and not r.get("venue_recognized", True)]
    if unknown_venues:
        st.warning("Unrecognized international venue(s) — travel factors "
                   "skipped: " + ", ".join(sorted(set(unknown_venues))) +
                   ". Add coordinates to INTL_VENUES in walters/teams.py.")
    if not results:
        st.info("No games found for that season/week.")
        st.stop()

    ratings_used = raw_ratings
    had_file = bool(file_r)
    st.session_state["run_data"] = dict(
        results=results, sonny_r=sonny_r,
        ratings_used=(file_r or sonny_r), had_file=bool(file_r),
        season=int(season), week=int(week),
        hfa=hfa, factor_scale=factor_scale,
        sb_winner=sb_winner, sb_loser=sb_loser)

def bet_str(r):
    """'SEA -3.0' — the actual ticket, not a model number."""
    m = r["market_home_spread"]
    if not r["bet_side"] or m is None:
        return ""
    line = m if r["bet_side"] == r["home"] else -m
    return f"{r['bet_side']} {line:+.1f}"


# The full board is built once, above the tabs, because both the Best Bets
# tab (for saving) and the Walters tab (for display) need it.
_rows = []
for _r in results:
    _flags = []
    if _r["qb_flag"]:
        _flags.append("🚑 QB")
    if _r["neutral_site"]:
        _flags.append("🌍 INTL")
        if not _r.get("venue_recognized", True):
            _flags.append("⚠️ VENUE?")
    _rows.append({
        "Away": _r["away"], "Home": _r["home"], "Day": _r["game_day"],
        "Walters (Home)": _r["walters_home_line"],
        "Market (Home)": _r["market_home_spread"],
        "Edge": (abs(_r["edge"]) if _r["edge"] is not None else None),
        "Bet": bet_str(_r),
        "Flags": " ".join(_flags),
        "Injuries": _r["injury_count"],
    })
df = pd.DataFrame(_rows)
GH_TOKEN = st.secrets.get("github_token", "")
GH_REPO = st.secrets.get("github_repo", "")
SAVE_PW = st.secrets.get("save_password", "")
already = set()
saved_f = set()
if GH_TOKEN and GH_REPO:
    try:
        already = snap.saved_games(GH_REPO, GH_TOKEN, int(season), int(week))
        saved_f = snap.saved_formula(GH_REPO, GH_TOKEN, int(season), int(week))
    except Exception:
        pass
df["Saved"] = ["✓" if (a, h) in already else ""
               for a, h in zip(df["Away"], df["Home"])]
df = df.sort_values("Edge", ascending=False, na_position="last")

tab_best, tab_w, tab_hist = st.tabs(
    ["⭐ Best Bets", "🏈 Walters Board", "📊 History & Edge Analysis"])

# --- Tab 0: Best Bets --------------------------------------------------------
with tab_best:
    st.caption("Two independent screens. Walters compares the model to the "
               "market; Formula reads the public bets/money split and line "
               "movement. They share no inputs — agreement on a side is the "
               "strongest read, not a requirement. Open and Now are both "
               "ESPN/DraftKings numbers, so Move is real movement at one "
               "book. A side whose line moved against it is excluded.")
    f1, f2, f3, f4 = st.columns(4)
    min_edge = f1.slider("Min Walters edge (pts)", 0.0, 12.0, 3.0, 0.5,
                         key="bb_min_edge",
                         help="Thresholds are unproven. The History tab's "
                              "edge buckets are how you find the real one.")
    max_bets = f2.slider("Max bets % on the side", 5.0, 100.0, 30.0, 1.0,
                         key="bb_max_bets",
                         help="Ticket minority — the public is elsewhere.")
    max_money = f3.slider("Max money % on the side", 20.0, 100.0, 40.0, 1.0,
                          key="bb_max_money")
    min_diff = f4.slider("Min money − bets differential", 0.0, 30.0, 5.0, 0.5,
                         key="bb_min_diff")

    # A game that has kicked off is not a bet any more. This is separate
    # from "already saved" — it drops finished games even if never recorded.
    live = [r for r in results if not r.get("completed_scores")]
    dropped = len(results) - len(live)

    saved_w = already

    hide_recorded = st.checkbox("Hide picks already saved", value=True,
                                key="bb_hide_saved")
    if dropped:
        st.caption(f"{dropped} game(s) already kicked off and are excluded.")

    splits = load_splits(int(season), int(week))
    if not splits:
        st.warning("Splits unavailable — Formula screens are empty this run. "
                   "Walters picks below are unaffected.")

    # ---- Walters screen
    w_rows = []
    for r in live:
        if r["edge"] is None or abs(r["edge"]) < min_edge or not r["bet_side"]:
            continue
        is_saved = (r["away"], r["home"]) in saved_w
        if is_saved and hide_recorded:
            continue
        w_rows.append({
            "Saved": "✓" if is_saved else "",
            "Away": r["away"], "Home": r["home"], "Day": r["game_day"],
            "Bet": bet_str(r), "Edge": round(abs(r["edge"]), 1),
            "Walters": r["walters_home_line"], "Market": r["market_home_spread"],
            "Flags": ("🚑" if r["qb_flag"] else ""),
        })
    st.subheader(f"🏈 Walters — edge ≥ {min_edge:g}")
    if w_rows:
        board_table(pd.DataFrame(sorted(w_rows, key=lambda x: -x["Edge"])),
                    team_cols=("Away", "Home", "Bet"), signal_cols=("Bet",),
                    dim_cols=("Saved", "Day", "Flags"))
    else:
        st.info("No games clear that edge.")

    # ---- Formula screens (spreads and totals)
    def _move(cur, opn):
        return None if (cur is None or opn is None) else round(cur - opn, 1)

    sp_rows, ou_rows = [], []
    for r in live:
        s = splits.get((r["away"], r["home"]))
        if not s:
            continue
        # spread: movement toward a side = opener minus current, per side
        mv_home = _move(r.get("open_home_spread"), r.get("market_home_spread"))
        oh, ch = r.get("open_home_spread"), r.get("market_home_spread")
        for side, bets, money, mv, opn, now in (
            (r["away"], s.get("away_bets_pct"), s.get("away_money_pct"),
             None if mv_home is None else -mv_home,
             None if oh is None else -oh, None if ch is None else -ch),
            (r["home"], s.get("home_bets_pct"), s.get("home_money_pct"),
             mv_home, oh, ch),
        ):
            sig = splits_api.formula_signal(bets, money, max_money, min_diff,
                                            max_bets, mv)
            # Reject a line that moved AGAINST the side. Flat (0.0) passes.
            # Both numbers are ESPN/DraftKings, so the comparison is
            # same-book; mixing in a consensus "now" made phantom moves.
            if sig and (mv is None or mv >= 0):
                is_saved = (r["away"], r["home"], "spread", side) in saved_f
                if is_saved and hide_recorded:
                    continue
                sp_rows.append({
                    "Saved": "✓" if is_saved else "",
                    "Away": r["away"], "Home": r["home"],
                    "Market": "spread", "Side": side,
                    "HomeSpread": ch, "Open": opn, "Now": now,
                    "Bets%": sig["bets_pct"], "Money%": sig["money_pct"],
                    "Diff": sig["differential"],
                    "Move": sig["line_move"] if sig["line_move"] is not None else "",
                })
        # totals
        mv_over = _move(r.get("market_total"), r.get("open_total"))
        # ESPN (DraftKings) for BOTH, so Open->Now is a real move rather
        # than the gap between two books' numbers.
        now_total = r.get("market_total")
        open_total = r.get("open_total")
        for side, bets, money, mv in (
            ("Over", s.get("over_bets_pct"), s.get("over_money_pct"), mv_over),
            ("Under", s.get("under_bets_pct"), s.get("under_money_pct"),
             None if mv_over is None else -mv_over),
        ):
            sig = splits_api.formula_signal(bets, money, max_money, min_diff,
                                            max_bets, mv)
            if sig and (mv is None or mv >= 0):
                is_saved = (r["away"], r["home"], "total", side) in saved_f
                if is_saved and hide_recorded:
                    continue
                ou_rows.append({
                    "Saved": "✓" if is_saved else "",
                    "Away": r["away"], "Home": r["home"],
                    "Market": "total", "Side": side,
                    "Total": now_total, "Open": open_total, "Now": now_total,
                    "Bets%": sig["bets_pct"], "Money%": sig["money_pct"],
                    "Diff": sig["differential"],
                    "Move": sig["line_move"] if sig["line_move"] is not None else "",
                })

    st.subheader(f"📈 Formula — spreads (bets < {max_bets:g}%, "
                 f"money < {max_money:g}%, diff ≥ {min_diff:g}, "
                 "line not moving against the side)")
    if sp_rows:
        _sp = pd.DataFrame(sorted(sp_rows, key=lambda x: -x["Diff"]))
        board_table(_sp.drop(columns=["Market", "HomeSpread"]),
                    team_cols=("Away", "Home", "Side"), signal_cols=("Side",),
                    dim_cols=("Saved", "Open", "Now"))
    else:
        st.info("No spread sides clear those thresholds.")

    st.subheader(f"⬆️⬇️ Formula — totals (bets < {max_bets:g}%, "
                 f"money < {max_money:g}%, diff ≥ {min_diff:g}, "
                 "line not moving against the side)")
    if ou_rows:
        _ou = pd.DataFrame(sorted(ou_rows, key=lambda x: -x["Diff"]))
        board_table(_ou.drop(columns=["Market", "Total"]),
                    team_cols=("Away", "Home", "Side"), signal_cols=("Side",),
                    dim_cols=("Saved", "Open", "Now"))
    else:
        st.info("No totals sides clear those thresholds.")

    # ---- overlap
    w_sides = {(x["Away"], x["Home"], x["Bet"].split()[0]) for x in w_rows}  # noqa
    both = [x for x in sp_rows
            if (x["Away"], x["Home"], x["Side"]) in w_sides]
    if both:
        st.subheader("🎯 Both screens agree")
        board_table(pd.DataFrame(both).drop(columns=["Market", "HomeSpread"]),
                    team_cols=("Away", "Home", "Side"), signal_cols=("Side",),
                    dim_cols=("Saved", "Open", "Now"))


    # ---- one save per slate: board + Formula picks together
    st.divider()
    st.markdown("##### Save a slate")
    st.caption("One button per slate. Saves the full Walters board for those "
               "games AND any qualifying Formula picks, with the numbers as "
               "they stand now. First save of anything wins, so a later run "
               "can never rewrite a pre-kickoff record.")

    if not (GH_TOKEN and GH_REPO):
        st.info("Add `github_token` and `github_repo` in the app's Streamlit "
                "**Secrets** to enable saving (steps in "
                "`walters/snapshots.py`).")
    elif SAVE_PW and not st.session_state.get("save_unlocked"):
        entered = st.text_input("Password to save", type="password",
                                key="save_pw_input",
                                help="Set as save_password in Secrets. "
                                     "Viewing and running stay open; only "
                                     "writing to the repo is gated.")
        if entered:
            if entered == SAVE_PW:
                st.session_state["save_unlocked"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
    else:
        # only games not yet saved AND not yet kicked off
        live_keys = {(r["away"], r["home"]) for r in live}
        # df is sorted by Edge, so its index is shuffled — the mask must be a
        # Series carrying that same index. A bare list is rejected outright by
        # current pandas rather than silently misaligning.
        is_live = pd.Series(
            [(a_, h_) in live_keys
             for a_, h_ in zip(df["Away"], df["Home"])], index=df.index)
        board_unsaved = df[(df["Saved"] == "") & is_live]
        day_of = {(r["away"], r["home"]): r["game_day"] for r in live}
        f_pending = [x for x in (sp_rows + ou_rows) if not x["Saved"]]
        days = list(dict.fromkeys(board_unsaved["Day"].tolist()))
        if not days:
            st.success("Every game still to come is already saved.")
        else:
            counts = {}
            for d in days:
                g = int((board_unsaved["Day"] == d).sum())
                f = sum(1 for x in f_pending
                        if day_of.get((x["Away"], x["Home"])) == d)
                counts[d] = (g, f)
            picks = st.multiselect(
                "Which slate(s)?", options=days, default=days,
                key="save_slates",
                format_func=lambda d: (f"{d} — {counts[d][0]} game"
                                       f"{'s' if counts[d][0] != 1 else ''}"
                                       + (f" + {counts[d][1]} Formula"
                                          if counts[d][1] else "")),
                help="Save each slate before its kickoff.")
            sel_board = board_unsaved[board_unsaved["Day"].isin(picks)]
            sel_formula = [x for x in f_pending
                           if day_of.get((x["Away"], x["Home"])) in picks]
            label = (f"💾 Save {len(sel_board)} game(s)"
                     + (f" + {len(sel_formula)} Formula pick(s)"
                        if sel_formula else ""))
            if st.button(label, type="primary", use_container_width=True,
                         disabled=sel_board.empty and not sel_formula,
                         key="save_slate_btn"):
                msgs, errs = [], []
                try:
                    cols = [c for c in df.columns if not c.startswith("_")]
                    added, _ = snap.save_incremental(
                        GH_REPO, GH_TOKEN, int(season), int(week),
                        sel_board[cols].to_dict("records"), cols)
                    if added:
                        msgs.append(f"{added} game(s) → "
                                    f"{snap.path_for(int(season), int(week))}")
                        if not had_file and ratings_used:
                            try:
                                if snap.save_ratings(GH_REPO, GH_TOKEN,
                                                     int(season), int(week),
                                                     ratings_used) == "created":
                                    msgs.append(
                                        "ratings archived → "
                                        f"ratings/{int(season)}_"
                                        f"wk{int(week):02d}.csv")
                            except Exception as e:
                                errs.append(f"ratings archive: {e}")
                except Exception as e:
                    errs.append(f"board: {e}")
                if sel_formula:
                    try:
                        fcols = ["Away", "Home", "Market", "Side",
                                 "HomeSpread", "Total", "Open", "Now",
                                 "Bets%", "Money%", "Diff", "Move"]
                        fadd, _ = snap.save_formula(
                            GH_REPO, GH_TOKEN, int(season), int(week),
                            sel_formula, fcols)
                        if fadd:
                            msgs.append(
                                f"{fadd} Formula pick(s) → "
                                f"{snap.formula_path(int(season), int(week))}")
                    except Exception as e:
                        errs.append(f"formula: {e}")
                for e in errs:
                    st.error(f"Save failed — {e}")
                if msgs:
                    st.success("Saved: " + "; ".join(msgs) + ".")
                elif not errs:
                    st.info("Nothing new to save.")

# --- Tab 1: Walters ----------------------------------------------------------
with tab_w:
    fc1, fc2 = st.columns(2)
    hide_qb = fc1.checkbox("High-confidence only (hide QB-injury games)",
                           value=False, key="hide_qb_games")
    hide_saved = fc2.checkbox("Hide games already saved", value=False,
                              key="hide_saved_games", disabled=not already)
    view = df
    if hide_qb:
        view = view[~view["Flags"].str.contains("QB")]
    if hide_saved:
        view = view[view["Saved"] == ""]
    top = df[df["Bet"] != ""].head(3)
    if len(top):
        st.markdown("#### 🔥 TOP PLAYS")
        tcols = st.columns(len(top))
        for tc, (_, tr) in zip(tcols, top.iterrows()):
            tc.metric(f"{tr['Away']} @ {tr['Home']}", tr["Bet"],
                      f"edge {tr['Edge']:.1f}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Games", len(df))
    c2.metric("Edges ≥ 1 pt", int((df["Bet"] != "").sum()))
    c3.metric("QB-flagged", int(df["Flags"].str.contains("QB").sum()))
    board_table(view, team_cols=("Away", "Home", "Bet"),
                signal_cols=("Bet",), dim_cols=("Day", "Flags"))

    st.subheader("Game detail")
    for r in sorted(results, key=lambda x: -(abs(x["edge"]) if x["edge"] is not None else -1)):
        label = f"{r['away']} @ {r['home']} — Walters {r['walters_home_line']:+.1f}"
        if r["bet_side"]:
            label += f" → BET {r['bet_side']} ({r['edge']:+.1f})"
        if r["qb_flag"]:
            label += "  🚑"
        with st.expander(label):
            if r["factors"]:
                st.table(pd.DataFrame(r["factors"],
                                      columns=["Factor", "Units", "Credits"]))
            for side, plist in (("Home", r["injuries_home"]),
                                ("Away", r["injuries_away"])):
                if plist:
                    st.caption(f"{side} injuries: " + "; ".join(
                        f"{p['name']} ({p['position']}, {p['status']})"
                        for p in plist))

    st.divider()
    with st.expander("🚑 Injury suggestions (depth-chart aware)"):
        st.caption("Only starters score. Suggested values follow Walters' "
                   "guide — QB about a touchdown, top non-QBs 2-3, everyone "
                   "else zero. Review, then paste into the sidebar box.")
        charts = load_depth_charts()
        if not charts:
            st.info("Depth charts unavailable this run.")
        else:
            teams_playing = sorted({r["home"] for r in results} |
                                   {r["away"] for r in results})
            parts, rows = [], []
            for tm in teams_playing:
                inj_list = []
                for r in results:
                    if r["home"] == tm:
                        inj_list = r["injuries_home"]
                    elif r["away"] == tm:
                        inj_list = r["injuries_away"]
                    if inj_list:
                        break
                if not inj_list:
                    continue
                pts, detail = depth_api.suggest(inj_list, charts.get(tm, {}))
                for d in detail:
                    if d["points"] or d["depth"] == "starter":
                        rows.append(dict(Team=tm, Player=d["name"],
                                         Pos=d["pos"], Depth=d["depth"],
                                         Status=d["status"], Pts=-d["points"]))
                if pts:
                    parts.append(f"{tm}:-{pts:g}")
            if rows:
                board_table(pd.DataFrame(rows), team_cols=("Team",),
                            dim_cols=("Depth", "Status"))
            else:
                st.write("No starters listed on either injury report.")
            if parts:
                st.markdown("**Copy into the sidebar box:**")
                st.code(", ".join(parts), language=None)
                st.caption("Adjust or delete before applying — the app can't "
                           "know a backup is unusually good, and Questionable "
                           "players usually play.")

    st.divider()
    st.download_button("⬇ Download this board (CSV)",
                       df.to_csv(index=False).encode(),
                       file_name=f"walters_{season}_wk{week}.csv",
                       mime="text/csv")
    st.caption("Saving to the repo lives on the **Best Bets** tab — one "
               "button per slate, covering both the board and Formula picks.")

# --- Tab 2: History & Edge Analysis -----------------------------------------
with tab_hist:
    gh_token, gh_repo = GH_TOKEN, GH_REPO
    saved = snap.list_saved_local(int(season))
    if not saved and gh_token and gh_repo:
        try:
            saved = snap.list_saved(gh_repo, gh_token, int(season))
        except Exception as e:
            st.warning(f"Could not read saved boards: {e}")

    if saved:
        graded_s = hist.grade_snapshots(int(season), saved,
                                        load_qb_data(int(season)))
        st.success(f"Grading {len(saved)} saved board(s) — no look-ahead bias.")
        if graded_s:
            o = hist.overall(graded_s)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Record (all games)",
                      f"{o['W']}-{o['L']}" + (f"-{o['P']}" if o['P'] else ""))
            c2.metric("Win %", f"{o['win_pct']}%" if o['win_pct'] is not None else "—")
            c3.metric("Units (-110)", f"{o['units']:+.2f}")
            c4.metric("Breakeven", f"{o['breakeven']}%")

            flagged = [g for g in graded_s if g.get("clean") == "⚠"]
            if flagged:
                clean_only = [g for g in graded_s if g.get("clean") != "⚠"]
                oc = hist.overall(clean_only)
                st.caption(
                    f"{len(flagged)} game(s) flagged for a starting QB not "
                    "finishing — the modelled team isn't the team that "
                    "played. Clean-only record shown alongside; the all-games "
                    "number above stays the headline.")
                d1, d2, d3 = st.columns(3)
                d1.metric("Record (clean only)",
                          f"{oc['W']}-{oc['L']}" + (f"-{oc['P']}" if oc['P'] else ""))
                d2.metric("Win % (clean)",
                          f"{oc['win_pct']}%" if oc['win_pct'] is not None else "—")
                d3.metric("Units (clean)", f"{oc['units']:+.2f}")

            # Stable key + a constant element tree: st.tabs remounts (and
            # snaps back to tab 1) when the widget tree changes shape, which
            # is why an unkeyed toggle bounced you out on its first click.
            use_clean = st.checkbox("Edge buckets: clean games only",
                                    value=False, key="edge_clean_only",
                                    disabled=not flagged)
            basis = [g for g in graded_s if g.get("clean") != "⚠"] if use_clean \
                else graded_s
            st.subheader("Win % by edge size"
                         + (" (clean games)" if use_clean else ""))
            bs = pd.DataFrame(hist.bucket_stats(basis))
            board_table(bs, dim_cols=("bucket",))
            ch = bs.dropna(subset=["win_pct"]).set_index("bucket")
            # Always render the chart element, even with nothing in it, so the
            # element count never changes between toggle states.
            st.bar_chart(ch["win_pct"] if len(ch)
                         else pd.Series(dtype="float64", name="win_pct"))
            st.subheader("Graded picks")
            board_table(pd.DataFrame(graded_s),
                        team_cols=("away", "home", "bet"),
                        signal_cols=("result",),
                        dim_cols=("week", "score", "clean", "note"))
        else:
            st.info("Saved boards found, but none of those games have "
                    "finished yet.")
        st.divider()
        st.markdown("##### Backtest (current ratings — look-ahead bias)")

    st.caption("Re-runs the model for completed weeks and grades every pick "
               "against the closing number from ESPN.")
    if week <= 1:
        st.info("No completed weeks yet this season. Come back after Week 1 "
                "and this fills in automatically.")
    else:
        weeks = list(range(1, int(week)))
        with st.spinner(f"Grading weeks 1–{weeks[-1]}…"):
            graded = hist.grade_weeks(int(season), weeks, sonny_r, hfa,
                                      factor_scale,
                                      sb_winner.strip().upper() or None,
                                      sb_loser.strip().upper() or None,
                                      repo=st.secrets.get("github_repo", ""))
        if not graded:
            st.info("No graded games yet.")
        else:
            o = hist.overall(graded)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Record", f"{o['W']}-{o['L']}" + (f"-{o['P']}" if o['P'] else ""))
            c2.metric("Win %", f"{o['win_pct']}%" if o['win_pct'] is not None else "—")
            c3.metric("Units (-110)", f"{o['units']:+.2f}")
            c4.metric("Breakeven", f"{o['breakeven']}%")

            st.subheader("Does a bigger edge mean a better record?")
            bstats = pd.DataFrame(hist.bucket_stats(graded))
            board_table(bstats, dim_cols=("bucket",))
            chartable = bstats.dropna(subset=["win_pct"]).set_index("bucket")
            if len(chartable):
                st.bar_chart(chartable["win_pct"])
                st.caption("Breakeven at -110 juice is 52.4%. A rising line "
                           "left-to-right is the result you want; a flat or "
                           "falling one means edge size is not predictive.")

            st.subheader("Every graded pick")
            board_table(pd.DataFrame(graded), team_cols=("away", "home", "bet"),
                        signal_cols=("result",), dim_cols=("week", "score"))

            st.warning(
                "**Look-ahead bias:** ratings are fetched current, not as-of "
                "each week, so Sonny Moore's numbers already reflect results "
                "the model is being graded on. These figures flatter the "
                "record — use the weekly CSV snapshots for an honest forward "
                "test.")

    # ---- Formula record
    st.divider()
    st.subheader("📈 Formula record")
    saved_f_hist = snap.list_saved_formula_local(int(season))
    if not saved_f_hist and gh_token and gh_repo:
        try:
            import base64 as _b64
            saved_f_hist = []
            for wk in range(1, 19):
                _, txt = snap.get_existing(gh_repo, gh_token,
                                           snap.formula_path(int(season), wk))
                if txt:
                    saved_f_hist.append((wk, txt))
        except Exception:
            saved_f_hist = []
    if not saved_f_hist:
        st.info("No saved Formula picks yet. Save them from the Best Bets tab "
                "before kickoff and they'll be graded here.")
    else:
        gf = hist.grade_formula(int(season), saved_f_hist)
        if not gf:
            st.info("Formula picks saved, but none of those games are final.")
        else:
            of = hist.overall(gf)
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Record", f"{of['W']}-{of['L']}"
                      + (f"-{of['P']}" if of['P'] else ""))
            g2.metric("Win %", f"{of['win_pct']}%" if of['win_pct'] is not None else "—")
            g3.metric("Units (-110)", f"{of['units']:+.2f}")
            g4.metric("Breakeven", f"{of['breakeven']}%")
            st.markdown("**Win % by money − bets differential**")
            board_table(pd.DataFrame(hist.diff_buckets(gf)),
                        dim_cols=("bucket",))
            st.markdown("**Graded Formula picks**")
            board_table(pd.DataFrame(gf),
                        team_cols=("away", "home", "side"),
                        signal_cols=("result",),
                        dim_cols=("week", "market", "score"))
