"""Persist weekly boards to the GitHub repo (the app's own storage).

Streamlit Cloud's filesystem is ephemeral — anything written there is lost
on reboot or redeploy — so saved boards go into the repo itself via the
GitHub Contents API. A snapshot written BEFORE kickoff is the only
bias-free record of what the model actually predicted.

Setup (one time):
  1. github.com -> Settings -> Developer settings -> Personal access tokens
     -> Fine-grained tokens -> Generate new token
       - Repository access: only your formula-nfl repo
       - Permissions: Repository permissions -> Contents -> Read and write
  2. share.streamlit.io -> your app -> Settings -> Secrets, paste:
       github_token = "github_pat_..."
       github_repo  = "billy-w-playground/formula-nfl"
  3. Save. The app picks it up on the next run.
"""
from __future__ import annotations
import base64
from pathlib import Path

import requests

API = "https://api.github.com"
DIR = "history"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def path_for(season: int, week: int) -> str:
    return f"{DIR}/{season}_wk{int(week):02d}.csv"


def get_existing(repo: str, token: str, path: str, timeout: int = 20):
    """Return (sha, decoded_text) if the file exists, else (None, None)."""
    r = requests.get(f"{API}/repos/{repo}/contents/{path}",
                     headers=_headers(token), timeout=timeout)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    j = r.json()
    text = base64.b64decode(j.get("content", "")).decode("utf-8", "replace")
    return j.get("sha"), text


def saved_games(repo: str, token: str, season: int, week: int,
                timeout: int = 20) -> set[tuple[str, str]]:
    """(away, home) pairs already recorded for this week."""
    import csv as _csv
    import io as _io
    _, text = get_existing(repo, token, path_for(season, week), timeout)
    if not text:
        return set()
    return {(r.get("Away", ""), r.get("Home", ""))
            for r in _csv.DictReader(_io.StringIO(text))}


def save_incremental(repo: str, token: str, season: int, week: int,
                     rows: list[dict], fieldnames: list[str],
                     timeout: int = 20) -> tuple[int, int]:
    """Merge rows into the week's file, keeping the FIRST snapshot of each
    game. Returns (added, skipped_already_saved).

    Slates are saved separately across the week (Thu, then Sun, then Mon),
    so a game recorded before kickoff is never replaced by a rerun after
    the result is known."""
    import csv as _csv
    import io as _io

    path = path_for(season, week)
    sha, text = get_existing(repo, token, path, timeout)
    existing: list[dict] = []
    if text:
        existing = list(_csv.DictReader(_io.StringIO(text)))
    have = {(r.get("Away", ""), r.get("Home", "")) for r in existing}

    added = 0
    for row in rows:
        key = (str(row.get("Away", "")), str(row.get("Home", "")))
        if key in have:
            continue
        existing.append({k: row.get(k, "") for k in fieldnames})
        have.add(key)
        added += 1
    skipped = len(rows) - added
    if added == 0:
        return 0, skipped

    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    w.writerows(existing)

    payload = {
        "message": f"Board snapshot {season} wk{week}: +{added} game(s)",
        "content": base64.b64encode(buf.getvalue().encode()).decode(),
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(f"{API}/repos/{repo}/contents/{path}",
                     headers=_headers(token), json=payload, timeout=timeout)
    r.raise_for_status()
    return added, skipped


def list_saved_local(season: int | None = None) -> list[tuple[int, str]]:
    """Saved boards already committed to the repo are on local disk."""
    d = Path(__file__).resolve().parent.parent / DIR
    out = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.csv")):
        try:
            seas, wk = p.stem.split("_wk")
            seas, wk = int(seas), int(wk)
        except ValueError:
            continue
        if season is not None and seas != season:
            continue
        out.append((wk, p.read_text(encoding="utf-8-sig")))
    return sorted(out)


def list_saved(repo: str, token: str, season: int | None = None,
               timeout: int = 20) -> list[tuple[int, str]]:
    """Return [(week, csv_text)] for every saved snapshot, oldest first."""
    r = requests.get(f"{API}/repos/{repo}/contents/{DIR}",
                     headers=_headers(token), timeout=timeout)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    out = []
    for item in r.json():
        name = item.get("name", "")
        if not name.endswith(".csv"):
            continue
        try:
            seas, wk = name[:-4].split("_wk")
            seas, wk = int(seas), int(wk)
        except ValueError:
            continue
        if season is not None and seas != season:
            continue
        d = requests.get(item["download_url"], timeout=timeout)
        d.raise_for_status()
        out.append((wk, d.text))
    return sorted(out)


def save_ratings(repo: str, token: str, season: int, week: int,
                 ratings: dict[str, float], timeout: int = 20) -> str:
    """Archive the ratings a week was priced with, as ratings/<s>_wk<NN>.csv.

    Written on the FIRST board save of the week and never overwritten, so
    every slate that week prices off the same numbers and the History tab
    re-grades the week with the ratings the model actually had — no
    look-ahead. Returns 'created' | 'exists' | 'skipped'.
    """
    from .teams import TEAMS
    if not ratings:
        return "skipped"
    path = f"ratings/{season}_wk{int(week):02d}.csv"
    sha, _ = get_existing(repo, token, path, timeout)
    if sha:
        return "exists"
    lines = ["Team,Rating"]
    for abbr, val in sorted(ratings.items(), key=lambda kv: -kv[1]):
        name = TEAMS.get(abbr, {}).get("full_name", abbr)
        lines.append(f"{name},{round(float(val), 4)}")
    payload = {
        "message": f"Ratings snapshot {season} wk{week}",
        "content": base64.b64encode(("\n".join(lines) + "\n").encode()).decode(),
    }
    r = requests.put(f"{API}/repos/{repo}/contents/{path}",
                     headers=_headers(token), json=payload, timeout=timeout)
    r.raise_for_status()
    return "created"
