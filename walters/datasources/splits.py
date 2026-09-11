"""Public betting splits from scoresandodds.com (Action Network data).

WHY THIS SOURCE: the consensus page is SERVER-RENDERED — the bets%/money%
numbers are in the HTML, not filled in by JavaScript. That's what made
OddsCrowd and Action's own endpoints painful. Openers are NOT taken from
here; they come from ESPN's odds payload, so if this scrape breaks you lose
splits only and keep line movement.

Page layout, per game, three blocks (moneyline, spread, total). After tags
are stripped each block reads:

    SF (+3.5)  % of Bets  LA (-3.5)   41% 59%   66% 34%   % of Money

so the first team token is the AWAY side, the second is HOME, the first
percentage pair is tickets and the second is money. Totals blocks use
"Over (o48.5)" / "Under (u48.5)"; moneyline blocks carry no line.

Historical weeks are addressable with ?week=<season>-reg-<n>.
"""
from __future__ import annotations
import re

import requests

from ..teams import resolve

URL = "https://www.scoresandodds.com/nfl/consensus-picks"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/152.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml",
}

# scoresandodds uses a few non-standard abbreviations
ABBR_FIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "OAK": "LV", "SD": "LAC"}

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# TEAM or TEAM (+3.5) / Over (o48.5)
_SIDE = re.compile(r"\b([A-Z]{2,3}|Over|Under)\b\s*(?:\(([^)]+)\))?")
_PCT = re.compile(r"(\d{1,3})%")


def _strip(html: str) -> str:
    txt = _TAG.sub(" ", html)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&#039;", "'").replace("&quot;", '"'))
    return _WS.sub(" ", txt)


def fetch_raw(week_slug: str | None = None, timeout: int = 25) -> str:
    params = {"week": week_slug} if week_slug else None
    r = requests.get(URL, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def week_slug(season: int, week: int) -> str:
    return f"{season}-reg-{int(week)}"


def _norm(tok: str) -> str | None:
    tok = tok.strip().upper()
    tok = ABBR_FIX.get(tok, tok)
    return resolve(tok)


def parse(html: str) -> dict[tuple[str, str], dict]:
    """{(away, home): {spread/total bets% and money% ...}}"""
    txt = _strip(html)
    out: dict[tuple[str, str], dict] = {}
    # each block runs from a '% of Bets' label to the following '% of Money'
    for m in re.finditer(r"([^%]{0,120}?)% of Bets(.{0,220}?)% of Money",
                         txt, re.S):
        head, body = m.group(1), m.group(2)
        sides = _SIDE.findall(head + " " + body)
        pcts = [int(p) for p in _PCT.findall(body)]
        if len(sides) < 2 or len(pcts) < 4:
            continue
        (a_tok, a_line), (h_tok, h_line) = sides[0], sides[1]
        a_bets, h_bets, a_money, h_money = pcts[0], pcts[1], pcts[2], pcts[3]

        if a_tok in ("Over", "Under") or h_tok in ("Over", "Under"):
            # totals block: attach to the most recent game seen
            if not out:
                continue
            key = list(out)[-1]
            try:
                total = float(str(a_line or h_line).lstrip("ou"))
            except (TypeError, ValueError):
                total = None
            out[key].update(over_bets_pct=a_bets, over_money_pct=h_bets and a_money,
                            total_line=total)
            out[key]["over_bets_pct"] = a_bets
            out[key]["under_bets_pct"] = h_bets
            out[key]["over_money_pct"] = a_money
            out[key]["under_money_pct"] = h_money
            continue

        away, home = _norm(a_tok), _norm(h_tok)
        if not away or not home:
            continue
        key = (away, home)
        rec = out.setdefault(key, dict(away=away, home=home))
        if a_line and re.search(r"[+-]", str(a_line)):
            # spread block
            try:
                rec["home_spread"] = float(str(h_line).replace("+", ""))
            except (TypeError, ValueError):
                pass
            rec.update(away_bets_pct=a_bets, home_bets_pct=h_bets,
                       away_money_pct=a_money, home_money_pct=h_money)
        else:
            # moneyline block — keep it, it also anchors the game order
            rec.update(ml_away_bets_pct=a_bets, ml_home_bets_pct=h_bets,
                       ml_away_money_pct=a_money, ml_home_money_pct=h_money)
    return out


def fetch(season: int | None = None, week: int | None = None,
          timeout: int = 25) -> dict[tuple[str, str], dict]:
    slug = week_slug(season, week) if (season and week) else None
    return parse(fetch_raw(slug, timeout))


# --- the Formula ------------------------------------------------------------
def formula_signal(bets_pct: float | None, money_pct: float | None,
                   max_money: float = 40.0, min_diff: float = 5.0,
                   line_move: float | None = None) -> dict | None:
    """A side qualifies when money% is BELOW max_money and money% minus
    bets% is at least min_diff — a small share of the handle, but a bigger
    share than its ticket count, i.e. fewer and larger bets.

    line_move (points moved toward this side, from ESPN's opener) is
    reported when available but does not gate the signal.
    """
    if bets_pct is None or money_pct is None:
        return None
    diff = money_pct - bets_pct
    if money_pct < max_money and diff >= min_diff:
        return dict(bets_pct=bets_pct, money_pct=money_pct,
                    differential=round(diff, 1), line_move=line_move,
                    rlm=bool(line_move is not None and line_move > 0))
    return None
