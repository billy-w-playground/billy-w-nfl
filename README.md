# Billy Walters NFL Model (Streamlit)

Rebuild of the Walters power-rating + game-factor model, per the book chapter.
Hit **Run model** and get Walters lines vs the market for every game that week.

## Data pipes
| Source | What | Key needed | Fragility |
|---|---|---|---|
| ESPN scoreboard (unofficial JSON) | Schedule, results, day/time, embedded lines | No | Low — stable for years, but unofficial |
| Open-Meteo | Kickoff temp/rain at stadium lat/lon | No | Low. Forecasts only ~16 days out |
| ESPN odds (same scoreboard call) | OPENING spread and total, alongside current — DraftKings | No | Low |
| scoresandodds.com | Public bets% and money% for spread and total (Action Network data) | No | Medium — server-rendered HTML scrape |
| Weekly ratings file | `ratings/<season>_wk<NN>.csv` committed to the repo — used for that week instead of Sonny Moore (no toggle — presence of the file is the choice) | No | None — it's your file |
| Sonny Moore | Power ratings (spread-equivalent) | No | Medium — HTML scrape of a hand-maintained page; may serve last season's final ratings until after Week 1 |
| The Odds API | Consensus market lines | Optional (free tier 500/mo) | Low |

## The model
1. **Power**: each ratings source centered at league mean (→ point-spread units,
   avg team = 0 per the book), then averaged across sources.
2. **Factors**: the book's full factor table (turf, division/conference,
   primetime, Monday-night hangover, OT hangover, byes by team quality,
   Super Bowl carryover, 3rd-away-in-4, consecutive 2+ TZ trips, travel 2000+,
   proximity, body-clock kickoff penalties, blowout bounce-back, warm-to-cold
   and dome-to-cold weather ramps).
3. **Scale**: factor units × **0.2** — the book's "each number is worth
   one-fifth of a point." The legacy spreadsheet applied units raw (5×
   overweight); that mode is available as a toggle for comparison only.
4. **Line**: home margin = ΔPower + HFA (default 1.9, Sonny Moore's number)
   + scaled factors. Walters home line = −margin. Edge = market − Walters.

## Tabs
- **Best Bets** — the homepage. Two independent screens with adjustable thresholds: Walters (edge ≥ N points vs the market) and Formula (a side holding under X% of the money while running a ≥ Y-point money-minus-bets differential), for both spreads and totals. Line movement from the true opener is shown per side, and an RLM ✓ marks movement toward that side. A final section lists sides both screens agree on.
- **Walters Board** — model lines vs market, edges ranked, Top Plays, explicit bet strings, QB-injury flag (🚑), international flag (🌍), high-confidence filter, per-game factor and injury detail, weekly CSV download.
- **Injuries**: flagged, never auto-valued (ESPN gives no depth chart); enter points per team in the sidebar.
- **Home field**: defaults to 1.0 — measured HFA has fallen well below the traditional 3.
- **Saving**: boards are merged into one file per week, one row per game, first snapshot per game wins — so each slate (Thu / Sun / Mon) can be saved before its own kickoff without a later rerun overwriting earlier picks.
- **History & Edge Analysis** — re-runs completed weeks, grades every pick against ESPN's closing number, and reports win% by edge bucket: does a bigger edge actually win more? Includes record, units at -110, and the 52.4% breakeven line.

## Removed: Formula / betting splits
OddsCrowd's bets/money splits come from api.rsblabs.com, which sits behind
Cloudflare and blocks datacenter IPs — it works from a browser but not from
Streamlit Cloud. The Formula method is done manually on the OddsCrowd site.

## Known gaps (deliberate)
- **Injuries**: reports are pulled and QB-flagged, but NOT valued in points — the model line ignores them. Use the 🚑 flag to skip games, per your workflow.
- **OT detection**: ESPN's summary feed doesn't flag OT in this endpoint; OT-hangover factors only fire if enriched manually.
- **Super Bowl winner/loser**: set manually in the sidebar each season.

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
Deploy free: push to GitHub → share.streamlit.io → point at `app.py`.

## Tests
```
python tests/test_scoring.py
```
