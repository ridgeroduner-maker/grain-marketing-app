# Grain Bids — first working version (LOCAL ONLY)

Public-facing PWA showing **end-of-day** cash grain bids (corn, spring wheat, winter wheat, soybeans, sunflowers)
within **300 miles of Gann Valley, SD** (44.0, −98.9), from **USDA AMS Market News only**. No profit calculator.
Nothing here is deployed, published or scheduled; work lives on branch `build/v1` (not merged to main). Everything is free/open-source.

## Run it

```bash
cd /workspace/grain-app          # needs: python3 (stdlib only) + pdftotext (poppler-utils)
./run_ingest.sh                  # fetch today's AMS reports -> data/grain.db -> public/data/*.json   (no API key needed)
python3 -m ingest.make_sample    # optional: SYNTHETIC 45-day history -> public/data-sample/ (flagged SAMPLE in UI)
./serve.sh                       # http://127.0.0.1:8765   (add ?sample=1 for sample data; #history #best #alerts open a tab)
python3 -m unittest discover -s ingest/tests && node public/alerts-core.test.js   # tests (8 python + alerts)
```

## 1. USDA AMS data sources (researched 2026-10-27)

Daily cash bids by location are published as AMS "Point of Sale – Grain" reports, one per state/region:

| Slug | Report | Used |
|---|---|---|
| 3186 | South Dakota Daily Grain Bids | yes |
| 3878 | North Dakota Daily Grain Bids | yes |
| 3225 | Nebraska Daily Elevator Grain Bids | yes |
| 3049 | Southern Minnesota Daily Grain Bids | yes |
| 2850 | Iowa Daily Cash Grain Bids (incl. terminals, Council Bluffs) | yes |
| 2887 | National Daily Sunflower, Canola, Millet & Flaxseed Report (only report with sunflowers; **town-level**) | yes |
| 2771 / 3239 / 2912 / 3223 | Montana / Wyoming / Colorado / KC wheat | no — outside 300 mi (WY SE corner ≈330 mi). Add to `ingest/config.py` `REPORTS` if desired |

Two ways to read them:

* **MARS API** — `https://marsapi.ams.usda.gov/services/v1.2/reports/{slug}/Report Detail?q=report_date=MM/DD/YYYY`.
  **Requires a free API key** (unauthenticated calls are refused: 401 in my test, 403 in Data Scout's). HTTP Basic auth, key as
  username, empty password. Gives full history (needed for backfill/charts). Rows have `trade_loc`, `commodity`, `grade`,
  `protein`, `price Min/Max`, `basis Min/Max`, `basis Min Futures Month`, `avg_price`, `report_date`…
* **Public report PDFs, no key** — `https://www.ams.usda.gov/mnreports/ams_{slug}.pdf` (today's report only, no history).
  Same data, and it also carries USDA's **end-of-day futures settlements** table (CBOT/KCBT/MGE) which the app uses for the futures
  panel. This is what the ingest uses by default and it is **verified working** against live 2026-10-26 reports.

**Key finding:** AMS reports bids by *trade region* ("North Central", "Southeast"…) for SD/ND/NE/IA/MN, **not by individual
elevator**. Only the sunflower/canola report lists towns. So "map of bid locations" = region pins placed at an
**approximate centroid** (labelled "~" / "Region bid" in the UI). Towns are geocoded from the free US Census Gazetteer.

### What Ridge must do to get the (free) API key — only needed for history backfill / MARS path
1. Go to <https://mymarketnews.ams.usda.gov> and register (free; sign-in goes through USDA eAuthentication/Login.gov-style account).
2. Log in → **My Profile** → “Show API key” (per AMS docs; I could not load that page from the box to confirm exact wording).
3. `cp .env.example .env` and put `USDA_AMS_API_KEY=<key>` in it (or `export USDA_AMS_API_KEY=...`). Never commit it.
4. `python3 -m ingest.ingest --source mars --backfill-days 90 --export`

> The MARS code path is written from AMS docs + a published sample row and unit-tested on that row, but **has not hit the live API**
> (no key was available). Expect to adjust field handling on first real run (e.g. the backfill date-range syntax `q=report_begin_date=a:b`).

### Posted-at times, credit and the confirm note (build/v1)
* Every bid shows **when USDA posted its report** (America/Chicago): ingest reads `publishedDate` from the keyless public MARS metadata endpoint
  (`/services/v3.1/public/listPublishedReport/<id>?format=json`, metadata only — no prices) and stores it as `bids.posted_at` / `futures.posted_at`;
  if unavailable the UI says "posted time n/a". Matches Data Scout's observed times (e.g. SD 2:28 pm CT).
* A persistent “Call your elevator to confirm” banner, the same note on every best-bid card and map popup, and a footer crediting
  **USDA AMS Livestock, Poultry & Grain Market News** (report IDs listed). The futures panel names the USDA report it was printed in.
* Radius center is Gann Valley **44.0335 N, 98.9884 W** (Data Scout S51), haversine 300 mi.
* Open licensing risk (spec §6.8): futures numbers originate with CME/MIAX; shown only as printed in USDA reports with attribution. Ask USDA/CME before a public launch.

## 2. Ingest job (`ingest/`)
* `python3 -m ingest.ingest [--source auto|pdf|mars] [--date YYYY-MM-DD] [--backfill-days N] [--export]` — `auto` = MARS if `USDA_AMS_API_KEY` set else PDF.
* SQLite `data/grain.db`: `locations(state,name,section,lat,lon,geo_method,distance_mi)`, `bids(commodity, location_id, grade, protein, bid_low/high/avg, unit, basis_low/high, basis_futures_month, delivery, report_date, source_report, …)`, `futures`, `unlocated`, `ingest_runs`; view `bids_flat` = commodity, location, lat/lon, bid, basis, report date, source report.
  “Bid” used for ranking = **high end** of AMS's reported range (low/avg also stored). Sunflowers are $/cwt, others $/bu (stored in `unit`).
* Haversine filter to 300 mi from Gann Valley in `ingest.upsert` (`ingest/geo.py`); rows outside the radius or with no coordinates are dropped/recorded in `unlocated`.
* Idempotent (unique key per date/report/commodity/grade/protein/location/delivery). First real run: 66 bid rows + 41 futures settlements for 2026-10-26.
* Schedule **examples only (not installed)**: `deploy/grain-ingest.{service,timer}` (systemd), `deploy/crontab.example` — weekday 4:30 PM CT. They only run the local ingest; nothing publishes.

## 3. PWA (`public/`)
Static site (no backend): `index.html, app.js, style.css, manifest.webmanifest, sw.js, alerts-core.js, icons/, vendor/` (Leaflet 1.9.4, Chart.js 4.4.4 vendored for offline) + JSON in `data/` (`meta, latest, history, futures`).
* **Map**: Leaflet + OpenStreetMap tiles, 300-mi ring, per-commodity/product/delivery pins with bid labels, best bid highlighted, sortable table, EOD futures panel.
* **Best bid near me**: browser geolocation (stays on-device), per-commodity cards with radius filter + top 3 runners-up.
* **Alerts**: local rules (≥/≤ price, per location or any) in localStorage; browser notifications; checked on open and every 15 min while open; once per report day.
  **Limit:** without a server there is no true Web Push — a closed app cannot be woken. Experimental Periodic Background Sync (Chromium, installed PWA) is wired in `sw.js` but untested here and browser-throttled. Real push later = push service + small server (free tiers exist) or email/SMS digests.
* **History**: Chart.js high/low bid lines, compare two locations, range filter. Real history is **1 day** until the daily job accumulates (or MARS backfill); `?sample=1` shows synthetic history.
* Installable (manifest + service worker; Chrome fired `beforeinstallprompt` in headless test). Responsive 420 px → desktop. Offline: app shell cached, data network-first with cached fallback; map tiles are not cached.
* SAMPLE data is always flagged: yellow banner, “(SAMPLE)” in header/popups, `is_sample=1` rows in `data/sample.db`. If real data is missing the UI falls back to sample with a notice.

## Verified here
`curl` of `/`, manifest, sw.js, app.js, data JSON, icons → 200. Headless Chrome loaded real + sample modes without JS errors, rendered map/table/best-bid/history (screenshots checked). Unit tests: parser on real PDFs (SD, sunflower), haversine, geocoding, MARS row normalizer, alert logic.

## What's done / blocked / open questions
**Blocked on Ridge:** nothing for daily data (keyless PDF path works). API key needed only for history backfill and as a more robust feed than PDF parsing.
**Risks:**
* PDF parsing is layout-based; AMS format changes would break it (tests on saved fixtures will catch it; MARS API is the durable fix).
* Region pin positions are my approximations (fractions of state bounding boxes in `ingest/config.py`, plus `data/location_overrides.json`). Whether a region is inside 300 mi is therefore approximate. Need AMS's county definitions of each trade region ("Trade Regions / Misc Info" link in each report) for proper centroids.
* No elevator-level (named location) bids exist in these reports for SD/ND/NE/IA/MN — if Ridge expected individual elevators, that data would have to come from elsewhere (not AMS).
**Open questions for Ridge:**
1. Is region-level (not elevator-level) OK for “bids by location”?
2. Include Montana/Wyoming/Colorado/Kansas wheat reports if in range / adding Minneapolis & KC terminal reports?
3. Futures: using USDA's published settlements (free, same reports). OK, or a different EOD futures source (e.g. Stooq/Yahoo — licensing unclear)?
4. Sunflower products: NuSun vs high-oleic (only high-oleic had in-range bids today); confection/black-oil not covered.
5. Deployment target later (free static hosting works — app is fully static) and push-notification approach.
6. OSM public tile servers are fine for dev/light use; a public launch should respect their tile usage policy or use a free tile provider with an account/key.
7. Data/terms: AMS data is public; add AMS attribution/disclaimer review before launch.
