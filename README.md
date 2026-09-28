# Van scraper

Weekly search for a second-hand **electric, high-roof (H2/H3), large van** to
convert and live in. Same shape as `job-board-scraper`: a stateless GitHub
Actions run writes `output/latest.json`; a weekly Cowork session diffs it
against seen listing IDs and reports what's new.

## Requirements encoded (edit `vanscraper/config.py`)

| Rule | Where |
|---|---|
| Electric only; diesel/petrol rejected | `classify.py` |
| Large platform. Tier 1 = Stellantis (Boxer/Ducato/Relay/Movano: widest, crosswise bed possible). Tier 2 = Transit/Sprinter/Master/eDeliver 9/Daily/Crafter | `classify.py` |
| Roof H2/H3 required; H1 rejected; unstated roof kept but flagged | `classify.py` |
| Budget incl. VAT: preferred ≤ £25k, ceiling £32k (private buyer pays the VAT on "+VAT" listings) | `config.py` |
| Battery < 80kWh flagged (≈100 real miles, charging stop needed on ~130-mile trips); ≥ 90kWh preferred | `config.py` |
| BYD on a watch list for its expected larger vans | `classify.py` |

## Sources and robots.txt

The scraper checks robots.txt before every request and never fetches a
disallowed URL. Findings so far:

- **AA Cars search** (`/used-cars/displaycars`): **disallowed**, not used.
- **AA Cars browse pages** (`/used-vans/<make>/<model>` etc.): allowed, but
  each shows only a sample -> **partial discovery**.
- **AA Cars listing pages**: allowed -> used for enrichment and starred vans.
- **Cazoo/Motors, Van Monster, others**: unknown until the probe runs (below).
- **AutoTrader**: expected disallowed; manual checks only.

## First-time setup

1. Create a GitHub repo `van-scraper`, push this folder.
2. Actions tab -> *Weekly van scrape* -> **Run workflow** with **probe = true**.
   The job summary lists which sources are allowed. Paste it to Claude to
   write the next adapter.
3. Run again with probe = false for a real scrape. Check `output/latest.json`.
4. If AA parsing misses fields, save one real page to `tests/fixtures/`
   (the current fixtures are reconstructed, not downloaded) and fix the parser.

`uv sync` creates `uv.lock` on first run; commit it.

## Starring a van

Add an entry to `starred.json` (listing_id, url, note). Starred vans are
re-checked every run whatever the filters say: live / sold / price change.

## Output

`output/latest.json`: `run_metadata` (per-source status: `ok`, `failed`,
`disallowed`, `robots_unreachable`), `starred[]`, and `vans[]` sorted by score.
**Read the `flags`, not the score.** The score only orders the list.

Status meanings, as in the job scraper: `failed`/`robots_unreachable` =
"couldn't check", never "no vans".

## Cowork handoff prompt

> Fetch `https://raw.githubusercontent.com/james-westwood/van-scraper/main/output/latest.json`.
> Check `run_started_utc` is < 9 days old. Diff `vans[].listing_id` against
> the seen-IDs list in my van watchlist doc; report new vans (title, price
> inc VAT, battery, roof, flags, link), grouped tier 1 then tier 2. Report
> any starred van that sold or changed price. List sources that weren't
> `ok`. Update the seen-IDs list.
