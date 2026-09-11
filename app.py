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

    splits = load_splits(int(season), int(week))
    if not splits:
        st.warning("Splits unavailable — Formula screens are empty this run. "
                   "Walters picks below are unaffected.")

    # ---- Walters screen
    w_rows = []
    for r in results:
        if r["edge"] is None or abs(r["edge"]) < min_edge or not r["bet_side"]:
            continue
        w_rows.append({
            "Away": r["away"], "Home": r["home"], "Day": r["game_day"],
            "Bet": bet_str(r), "Edge": round(abs(r["edge"]), 1),
            "Walters": r["walters_home_line"], "Market": r["market_home_spread"],
            "Flags": ("🚑" if r["qb_flag"] else ""),
        })
    st.subheader(f"🏈 Walters — edge ≥ {min_edge:g}")
    if w_rows:
        board_table(pd.DataFrame(sorted(w_rows, key=lambda x: -x["Edge"])),
                    team_cols=("Away", "Home", "Bet"), signal_cols=("Bet",),
                    dim_cols=("Day", "Flags"))
    else:
        st.info("No games clear that edge.")

    # ---- Formula screens (spreads and totals)
    def _move(cur, opn):
        return None if (cur is None or opn is None) else round(cur - opn, 1)

    sp_rows, ou_rows = [], []
    for r in results:
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
                sp_rows.append({
                    "Away": r["away"], "Home": r["home"], "Side": side,
                    "Open": opn, "Now": now,
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
                ou_rows.append({
                    "Away": r["away"], "Home": r["home"], "Side": side,
                    "Open": open_total, "Now": now_total,
                    "Bets%": sig["bets_pct"], "Money%": sig["money_pct"],
                    "Diff": sig["differential"],
                    "Move": sig["line_move"] if sig["line_move"] is not None else "",
                })

    st.subheader(f"📈 Formula — spreads (bets < {max_bets:g}%, "
                 f"money < {max_money:g}%, diff ≥ {min_diff:g}, "
                 "line not moving against the side)")
    if sp_rows:
        board_table(pd.DataFrame(sorted(sp_rows, key=lambda x: -x["Diff"])),
                    team_cols=("Away", "Home", "Side"), signal_cols=("Side",),
                    dim_cols=("Open", "Now"))
    else:
        st.info("No spread sides clear those thresholds.")

    st.subheader(f"⬆️⬇️ Formula — totals (bets < {max_bets:g}%, "
                 f"money < {max_money:g}%, diff ≥ {min_diff:g}, "
                 "line not moving against the side)")
    if ou_rows:
        board_table(pd.DataFrame(sorted(ou_rows, key=lambda x: -x["Diff"])),
                    team_cols=("Away", "Home", "Side"), signal_cols=("Side",),
                    dim_cols=("Open", "Now"))
    else:
        st.info("No totals sides clear those thresholds.")

    # ---- overlap
    w_sides = {(x["Away"], x["Home"], x["Bet"].split()[0]) for x in w_rows}
    both = [x for x in sp_rows
            if (x["Away"], x["Home"], x["Side"]) in w_sides]
    if both:
        st.subheader("🎯 Both screens agree")
        board_table(pd.DataFrame(both), team_cols=("Away", "Home", "Side"),
                    signal_cols=("Side",), dim_cols=("Open", "Now"))


# --- Tab 1: Walters ----------------------------------------------------------
with tab_w:
    rows = []
    for r in results:
        flags = []
        if r["qb_flag"]:
            flags.append("🚑 QB")
        if r["neutral_site"]:
            flags.append("🌍 INTL")
            if not r.get("venue_recognized", True):
                flags.append("⚠️ VENUE?")
        rows.append({
            "Away": r["away"], "Home": r["home"], "Day": r["game_day"],
            "Walters (Home)": r["walters_home_line"],
            "Market (Home)": r["market_home_spread"],
            "Edge": (abs(r["edge"]) if r["edge"] is not None else None),
            "Bet": bet_str(r),
            "Flags": " ".join(flags),
            "Injuries": r["injury_count"],
        })
    df = pd.DataFrame(rows)
    _tok = st.secrets.get("github_token", "")
    _repo = st.secrets.get("github_repo", "")
    already = set()
    if _tok and _repo:
        try:
            already = snap.saved_games(_repo, _tok, int(season), int(week))
        except Exception:
            already = set()
    df["Saved"] = ["✓" if (a, h) in already else ""
                   for a, h in zip(df["Away"], df["Home"])]
    df = df.sort_values("Edge", ascending=False, na_position="last")
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
    st.markdown("##### Save this week's board")
    st.caption("A board saved before kickoff is the only bias-free record of "
               "what the model predicted.")
    gh_token = st.secrets.get("github_token", "")
    gh_repo = st.secrets.get("github_repo", "")
    sc1, sc2 = st.columns([2, 1])
    with sc2:
        st.download_button("⬇ Download CSV", df.to_csv(index=False).encode(),
                           file_name=f"walters_{season}_wk{week}.csv",
                           mime="text/csv", use_container_width=True)
    save_pw = st.secrets.get("save_password", "")
    if save_pw and not st.session_state.get("save_unlocked"):
        with sc1:
            entered = st.text_input("Password to save", type="password",
                                    key="save_pw_input",
                                    help="Set in the app's Streamlit Secrets "
                                         "as save_password. Viewing and "
                                         "running stay open to everyone; only "
                                         "writing to the repo is gated.")
            if entered:
                if entered == save_pw:
                    st.session_state["save_unlocked"] = True
                    st.rerun()
                else:
                    st.error("Wrong password.")
        gh_token = ""   # keeps the save UI hidden until unlocked

    with sc1:
        if gh_token and gh_repo:
            unsaved = df[df["Saved"] == ""]
            days = list(dict.fromkeys(unsaved["Day"].tolist()))
            if not days:
                st.success("Every game this week is already saved.")
            else:
                day_counts = {d: int((unsaved["Day"] == d).sum()) for d in days}
                picks = st.multiselect(
                    "Which slate(s) to save now?",
                    options=days, default=days,
                    format_func=lambda d: f"{d} ({day_counts[d]} game"
                                          f"{'s' if day_counts[d] != 1 else ''})",
                    help="Save each slate before its kickoff. Games already "
                         "saved are never overwritten.")
                sel = unsaved[unsaved["Day"].isin(picks)]
                if st.button(f"💾 Save {len(sel)} game(s) to repo",
                             type="primary", use_container_width=True,
                             disabled=sel.empty):
                    try:
                        cols = [c for c in df.columns if not c.startswith("_")]
                        added, skipped = snap.save_incremental(
                            gh_repo, gh_token, int(season), int(week),
                            sel[cols].to_dict("records"), cols)
                        msg = (f"Saved {added} game(s) to "
                               f"{snap.path_for(int(season), int(week))}.")
                        if added and not had_file and ratings_used:
                            try:
                                st_r = snap.save_ratings(
                                    gh_repo, gh_token, int(season),
                                    int(week), ratings_used)
                                if st_r == "created":
                                    msg += (" Ratings archived to "
                                            f"ratings/{int(season)}_"
                                            f"wk{int(week):02d}.csv.")
                            except Exception as e:
                                st.warning(f"Board saved, but ratings archive "
                                           f"failed: {e}")
                        if added:
                            st.success(msg)
                        else:
                            st.info("Nothing new to save.")
                    except Exception as e:
                        st.error(f"Save failed: {e}")
        else:
            st.info("Add `github_token` and `github_repo` in the app's "
                    "Streamlit **Secrets** to enable one-click saving "
                    "(setup steps are in walters/snapshots.py).")

# --- Tab 2: History & Edge Analysis -----------------------------------------
with tab_hist:
    gh_token = st.secrets.get("github_token", "")
    gh_repo = st.secrets.get("github_repo", "")
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
