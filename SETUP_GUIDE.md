# Fresh Deploy: formula-nfl (Mac, no experience assumed)

## 1. Create the repo
github.com -> "+" -> New repository -> name: **formula-nfl** -> Public ->
**Add README: OFF** -> Create repository.

## 2. Prepare the files
Unzip walters_app.zip. In Finder, open the walters_app folder and press
**Cmd+Shift+Period** to reveal the hidden .streamlit folder.

## 3. Upload
On the empty repo page click "uploading an existing file". Drag these SIX
items as WHOLE icons (do not open them, do not Cmd+A inside them):
app.py, requirements.txt, README.md, SETUP_GUIDE.md, and the folders
**walters** and **tests**. Before committing, confirm the file list shows
paths WITH slashes (walters/scoring.py, walters/datasources/espn.py). If
everything is bare filenames, the drag flattened — remove and re-drag the
folders. Commit.

## 4. The hidden theme folder
macOS won't drag hidden folders into a browser. Instead: Add file ->
Create new file -> type the name **.streamlit/config.toml** (the slash
creates the folder) -> paste:

    [theme]
    base = "dark"
    backgroundColor = "#000000"
    secondaryBackgroundColor = "#0d0d0d"
    textColor = "#00e63c"
    primaryColor = "#ffbf00"

Commit.

## 5. Deploy
share.streamlit.io -> Create app -> repo: <your-username>/formula-nfl ->
branch main -> main file path **app.py** -> Deploy. Two minutes later you
have a URL that works on your phone. Every GitHub edit auto-redeploys;
if the app ever looks stale after an edit: Manage app -> Reboot.

## 6. Weekly run
Set Season + Week -> Run model. Sonny Moore is the ratings source
(auto-fetched). SEA/NE Super Bowl carryover is pre-set for 2026 — change
the dropdowns next season. Optional: The Odds API key for sharper market
lines. Formula tabs light up automatically once OddsCrowd's API starts
sending bets/money splits.

## 7. Auto-saving weekly boards (one-time setup)

Backtests re-run the model with CURRENT ratings, which flatters the record.
Boards saved before kickoff don't. To let the app save them into your repo:

1. **Make a token**: github.com -> Settings -> Developer settings ->
   Personal access tokens -> **Fine-grained tokens** -> Generate new token.
   Repository access: only `formula-nfl`. Permissions: Repository
   permissions -> **Contents: Read and write**. Generate, copy the token.
2. **Add it to the app**: share.streamlit.io -> your app -> Settings ->
   **Secrets**, paste these two lines and save:

       github_token = "github_pat_...your token..."
       github_repo  = "billy-w-playground/formula-nfl"

3. Rerun. The Walters tab now shows a slate picker and a **Save to repo**
   button. Boards land in `history/2026_wk01.csv` and the History tab grades
   them automatically once games finish.

**Saving across a week.** A week's games kick off on different days, so save
each slate before it plays: Tuesday save the Thursday game, Sunday morning
save the Sunday slate, Sunday night save the Monday game. The slate picker
defaults to whatever is still unsaved, saved games show a ✓ on the board, and
a checkbox hides them. Merging is per game and the FIRST snapshot always
wins — a rerun after results are known can never overwrite a real
prediction.

## 8. Using a different power rating for a given week

Sonny Moore is automatic, but he may still be serving last season's numbers
early on. To use your own ratings for a specific week:

1. Get the file. Massey: masseyratings.com/nfl/ratings -> **More -> Export**.
   Or build a two-column CSV yourself:

       Team,Rating
       Seattle Seahawks,6.05
       New England Patriots,1.35

2. In the repo: **Add file -> Create new file**, name it exactly
   `ratings/2026_wk01.csv` (typing the slash creates the folder), paste the
   file contents, Commit. Use `_wk02`, `_wk03`, ... for later weeks.
3. Rerun. The app confirms "Ratings: ratings/2026_wk01.csv (32 teams)".

There is no toggle: a week with a committed file uses that file, every other
week uses Sonny Moore automatically. The file is read from the repo checkout,
so no secrets or tokens are involved.

Ratings must be point-spread-equivalent — a 3-point gap means a 3-point
spread. Absolute scale doesn't matter; the app re-centres every source on the
league mean, so only the gaps between teams count.

**Why the repo and not an upload:** the History tab re-runs past weeks. A
committed file means that week is always re-graded with the ratings the model
actually had, so weeks with a file carry no look-ahead bias.

## 9. What happens automatically, and what doesn't

**Automatic every run:** schedule, scores and market lines (ESPN), kickoff
weather (Open-Meteo), injury reports (ESPN), power ratings (Sonny Moore, or
that week's committed file), all factor scoring, edge ranking, and the
grading of past weeks.

**Your four clicks a week:** open the app, hit Run, pick the slate, hit Save
— before each slate kicks off (Thu, Sun, Mon). The week number auto-detects
from the schedule, so you rarely touch it.

**Ratings archiving.** The first save of a week also writes
`ratings/<season>_wk<NN>.csv` with the ratings that week was priced on, and
never overwrites it. Consequences worth knowing:
  * Every slate you save that week prices off the same numbers.
  * The History tab re-grades that week with the ratings the model actually
    had — no look-ahead bias.
  * Week 1 already has your Massey file, so nothing is archived over it;
    Week 1 keeps grading with Massey and Week 2 onward with archived Sonny
    Moore.
  * It needs the GitHub token from §7. Without it, no board saves and no
    ratings archive.

**Injuries are not automated, on purpose.** ESPN's feed gives position and
status but not depth-chart rank, so a third-string QB listed Out would
wrongly cost a team 7 points, and "Questionable" players usually play. The
board flags QB injuries; you enter the points in the sidebar
("SEA:-7, NE:-2.5"), which adjusts those teams' power ratings for that run.
Walters' own guide: a QB is worth about a touchdown, top non-QBs 2.5-3,
about 60% of players roughly zero.

**Not automated at all:** the app only runs when you open it. Fully hands-off
weekly runs would need a scheduled job (GitHub Actions) that runs the model
and commits the board on a timer — a separate build if you ever want it.

## 10. Best Bets thresholds

Three sliders, none of them proven:

* **Min Walters edge** — how far the model must sit from the market. Default
  3.0 is a guess. The History tab's edge buckets exist to replace it with a
  number that has evidence behind it.
* **Max money %** — the qualifying side must hold LESS than this share of the
  handle, i.e. still be the unpopular side.
* **Min money − bets differential** — but it must hold more money than
  tickets by this margin, i.e. fewer and larger bets.

Line movement comes from ESPN's own opening line, so reverse line movement
is reported (RLM ✓) without depending on the splits scrape. If scoresandodds
breaks, the Formula screens empty out and the Walters screen is unaffected.
