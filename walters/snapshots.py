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


def save(repo: str, token: str, season: int, week: int, csv_text: str,
         overwrite: bool = False, timeout: int = 20) -> str:
    """Commit the week's board. Returns 'created' | 'updated' | 'exists'."""
    path = path_for(season, week)
    sha, _ = get_existing(repo, token, path, timeout)
    if sha and not overwrite:
        return "exists"
    payload = {
        "message": f"Board snapshot {season} week {week}",
        "content": base64.b64encode(csv_text.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(f"{API}/repos/{repo}/contents/{path}",
                     headers=_headers(token), json=payload, timeout=timeout)
    r.raise_for_status()
    return "updated" if sha else "created"


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
