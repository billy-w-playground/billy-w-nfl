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

3. Rerun. The Walters tab now shows *** Save board to repo**. Hit it each
   week before kickoff; boards land in `history/2026_wk01.csv`, and the
   History tab grades them automatically once games finish.

The first save for a week wins — the app warns instead of silently
overwriting, because a board re-saved after kickoff is no longer a prediction.
