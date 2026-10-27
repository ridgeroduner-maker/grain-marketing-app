# Grain Bids — first working version (LOCAL ONLY)

Public-facing PWA showing USDA's regional cash grain bids (posted about 2 to 4 pm Central each business day) (corn, spring wheat, winter wheat, soybeans, sunflowers)
within **300 miles of Gann Valley, SD** (44.0, −98.9), from **USDA AMS Market News only**. No profit calculator.
Nothing here is deployed, published or scheduled; work lives on branch `build/v1` (not merged to main). Everything is free/open-source.

## Run it

```bash
cd /workspace/grain-app          # needs: python3 (stdlib only) + pdftotext (poppler-utils)
./run_ingest.sh                  # fetch today's AMS reports -> data/grain.db -> public/data/*.json   (no API key needed)
python3 -m ingest.make_sample    # optional: SYNTHETIC 45-day history -> public/data-sample/ (git-ignored; only usable if ALLOW_SAMPLE is true in public/config.js)
./serve.sh                       # http://127.0.0.1:8765   (#history #best #alerts open a tab; ?sample=1 only works if ALLOW_SAMPLE is true)
python3 -m unittest discover -s ingest/tests && node public/alerts-core.test.js   # tests (32 python + 2 node scripts below)
node public/mapmode.test.js      # map-mode/config/service-worker guard tests
```

## Decisions
(Restored from the project notes that were first committed in `0d65bd9`; the build README replaced them.)
- Public app, free tools only. Crops: corn, spring wheat, winter wheat, soybeans, sunflowers, within 300 miles of Gann Valley, SD.
- Features: map, best bid near me, price alerts, history charts. **No profit calculator.**
- Prices: USDA AMS Market News regional data only at launch. No contact or permission requests to elevators. Sunflowers: thin coverage is OK.
- Futures: settlements as printed in the USDA reports only. No paid CME data at launch.
- **Oct 27, 2026: futures prices are shown with USDA AMS credit, and Ridge accepted the CME display risk flagged by Reviewer. Ridge directly confirmed this decision (per BOBBY).**
  Implemented as a switch: `FUTURES_DISPLAY` in `public/config.js` = `full` (default) or `basis_only` (hides futures dollar settlements everywhere, including an empty `futures.json`, and shows basis only). Tested in `ingest/tests/test_export.py`.
- Nothing is published, sent, or paid for without Ridge typing APPROVE.

## Settings (`public/config.js`, one place)
| Setting | Default | Meaning |
|---|---|---|
| `FUTURES_DISPLAY` | `full` | `full` or `basis_only` (see Decisions). Also read by the export (`ingest/config.py: futures_display()`); env `GRAIN_FUTURES_DISPLAY` overrides for one run. |
| `GOOGLE_MAPS_API_KEY` | `''` (empty) | Google Maps JavaScript API browser key. **Never committed**: injected from env/`.env` by `build_dist.sh` (appended to `dist/config.js`) or `serve.sh` (appended in memory). Empty = plain no-tile map + "Map tiles not configured" notice. See **Map (Google Maps)** below. |
| `DEV_OSM_TILES_ON_LOCALHOST` / `TILE_URL` / `TILE_ATTRIBUTION` / `TILE_MAX_ZOOM` | `true` / OSM | **Development only**: with no Google key, OSM public tiles are drawn **only on localhost/127.0.0.1** ([OSM policy](https://operations.osmfoundation.org/policies/tiles/)); any other host gets the plain map. |
| `ALLOW_SAMPLE` | `false` | Synthetic demo data (`?sample=1` and the no-real-data fallback). Must stay `false` in a public build; when false the app never loads or falls back to sample data. Also don't deploy `public/data-sample/` (git-ignored; regenerate with `make_sample`). |

## Data freshness and failure behaviour (Reviewer round 1)
* Staleness is measured against **today (Central)**, not the newest date in the data: every row has `age_days`; the page shows a status banner with the newest report date, **Final vs Preliminary**, the **last successful ingest time**, and a red warning when the newest report is 2+ business days old. Rows 2+ business days old also get a "Nd old" tag; alerts ignore them.
* Rows from a region/report line that is **missing from that report's newest edition are not exported** (history keeps them), and rows older than 7 days (`STALE_EXPIRE_DAYS`) are expired. Both are listed in `meta.dropped_rows`.
* If **any** report fails to fetch/parse (or an in-scope report parses to zero bids) the ingest run is recorded `ok=0`, exits non-zero, and **does not export**; `public/data/` keeps the last good copy and the banner shows its age.
* Service worker caches **only 200 same-origin responses** (never 404/500 pages); app files and data are network-first; a saved copy served offline is flagged so the page says "offline — data generated N days ago".
* The Iowa "Mills and Processors" soybean row has **no region text in USDA's PDF**, so it can't be placed. It is now stored (`skipped_rows`), logged by the ingest, exported in `meta.skipped_rows` and listed under the table ("cannot be placed on the map"), not dropped silently.

## Best bid, labels and approximation
* Product choices are `grade · (protein) · freight`: **grades never merge** (ND soybeans US #2 FOB-T vs US #1 DLVD-T elsewhere stay separate; ND "Milling HRS" vs "HRS" separate) and delivered vs FOB are separate. Each bid shows its USDA **range**; ranking uses the top of the range (labelled as the app's reading); distance is shown on every ranked line and always labelled **straight-line miles**; sort by highest bid or closest.
* Region bids (everything except sunflowers) are drawn at an **approximate centre this app chose**: dashed pins with "~", legend, "approximate" popups, and a note that the 300-mile cutoff is approximate for them. Only sunflower processors are called town-level (`precision: town`).
* Basis is labelled with its exchange and month (e.g. "-90 to -80¢ vs CBOT Dec futures"): CBOT corn/soybeans, MGE spring wheat, KCBT winter wheat — Data Scout's inference, arithmetic-checked by Reviewer; labelled as the app's reading in the footer.
* Wording: "posted about 2 to 4 pm Central", a USDA voluntary-reporting disclaimer (paraphrased, with a pointer to USDA's wording), and a footer list of what the app itself calculates (high-of-range, ranking, distances, pin positions, cents-to-dollar conversion, exchange named on basis, change since previous report).
* Leaflet (BSD-2-Clause, used only for the no-tile/dev fallback map) and Chart.js (MIT) license texts are in `public/vendor/` and linked from the footer.

## Re-review fixes (Job 5)
* **Per-report staleness**: the banner names every single report that is 2+ business days old even when others are current (e.g. only `ND (3878)`). **Best bid near me** only ranks rows from a report at most 1 business day old; older rows are listed in a "Not ranked" note on the card and keep their "Nd old" tag in the table. Alerts skip rows older than 2 business days.
* **Alerts in the background**: `sw.js` and the page share `GrainAlerts.freshRows(rows, 2)` (`alerts-core.js`), so the service-worker check obeys the same 2-business-day rule the UI states (`node public/alerts-core.test.js`).
* **"Just outside your radius"**: bids whose located centre is beyond 300 mi but within `MARGIN_MILES` (350, `ingest/config.py`) are exported to `public/data/outside.json` (table `outside_bids`) and listed under the bid table, never pinned or ranked, with distance, `~` for regions, freight and posted time.
* **Unplaced Iowa soybean row**: derived from `meta.skipped_rows` (never hard-coded); a Best-bid card shows a warning when an unplaced bid of the same crop/grade/freight is higher than the best placed bid.
* **Row-count guard**: the export refuses to run (ingest run recorded `ok=0`, non-zero exit, `public/data/` untouched) when the new row count is under `MIN_ROW_RATIO` (0.7) of the last good `latest.json`. Intentional drop: `python3 -m ingest.ingest --export --accept-row-drop`.
* **Times**: all exported timestamps carry a Central offset (`meta.time_zone = America/Chicago`); the banner shows e.g. `Tue, Oct 27, 1:41 PM CT`.
* **Manifest wording** now says "posted about 2 to 4 pm Central"; the wording test scans `manifest.webmanifest`.
* **a11y**: labelled alert-form fields, full tab/tabpanel ARIA with arrow-key navigation, keyboard-focusable table rows (Enter/Space show the pin).
* **`public/data-sample/` never ships**: it is git-ignored and untracked (a test asserts both), the service worker never precaches it, and `./build_dist.sh` builds `dist/` from `public/` then deletes `dist/data-sample` and fails if any path containing `data-sample` remains (tested). `deploy/` holds only local ingest cron/systemd examples (no web deploy files). `serve.sh` serves `public/` for local development only and is not a deploy tool. **Deploy only `dist/`, never `public/`.**

## Map (Google Maps)
**How it works.** `public/mapmode.js` picks one engine per page: `google` (key set) = Google **Maps JavaScript API**, loaded from `maps.googleapis.com` with `loading=async`; `osm-dev` (no key, localhost, dev flag) = Leaflet + OSM tiles; `blank` (anything else) = Leaflet with **no tiles** (pins + 300-mile ring on a plain background) and a "Map tiles not configured" notice. A placeholder or malformed key (e.g. `YOUR_...`) counts as no key. If Google fails (script blocked/offline, or `gm_authFailure` for a bad/restricted key) the page falls back to the plain map with a notice. Pins are small HTML overlays (`OverlayView`, no Map ID needed), the ring is a `google.maps.Circle`, popups are `InfoWindow`s, region pins keep the dashed "~" style. Google's logo/copyright stay untouched, and a credit line with the Google Maps/Earth Additional Terms and Privacy Policy links sits under the map. **Leaflet is never loaded alongside Google tiles**: Google's terms forbid using Google core services with or near a non-Google map, and Google documents Leaflet only for its own 2D Tiles API, not for use in this way, so the JavaScript API was chosen (see caveats).

**What Ridge must do** (nothing here was done by the build; no account, billing, key or spend exists yet):
1. Create (or pick) a Google Cloud project at console.cloud.google.com.
2. Enable **billing** on it (Maps Platform requires a billing account even inside the free monthly usage).
3. Enable the **Maps JavaScript API** only (APIs & Services > Library).
4. Create an **API key** (APIs & Services > Credentials) and restrict it: *Application restriction* = **Websites (HTTP referrers)** with your site URL(s) (e.g. `https://yourdomain.example/*`; add `http://localhost:8765/*` only for local testing, then remove it); *API restriction* = **Maps JavaScript API** only. The key is visible in the page source by design; the restrictions are the protection.
5. Set **quotas** (APIs & Services > Maps JavaScript API > Quotas): a daily cap on map loads. **A budget alert only emails you, it does not stop spending; the quota cap does.** Also create a **budget + alert** in Billing > Budgets & alerts.
6. Put the key in `.env` (copy `.env.example`, line `GOOGLE_MAPS_API_KEY=...`; `.env` is git-ignored) **or** export it in the shell, then `./serve.sh` (local test) or `./build_dist.sh` (builds `dist/`, appends the key to `dist/config.js` only). Do not paste the key into `public/config.js` or commit it.
7. Add public **Terms of Use** and **Privacy Policy** pages before launch (Google's terms require them, with flow-down terms and a link to Google's; the app does not have them yet).

**Recommended CSP when hosting** (UNTESTED with a live key; verify in the browser console before enforcing): `default-src 'self'; script-src 'self' https://maps.googleapis.com https://maps.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https://maps.gstatic.com https://maps.googleapis.com https://*.ggpht.com https://*.googleusercontent.com; font-src https://fonts.gstatic.com; connect-src 'self' https://maps.googleapis.com; frame-src 'none'` (Google lists its own CSP guidance in the Maps JavaScript API docs). No `<meta>` CSP ships in `index.html`, because it could not be validated without a live key.

**Caching.** `sw.js` returns before handling any cross-origin request (`url.origin !== location.origin`), so Google scripts/tiles are never cached by the app; a test asserts this line. Do not add Google URLs to the shell cache.

**Cost and terms caveats** (read 2026-10-27; re-check before launch, prices change):
* **Cost**: the JavaScript API bills as "Dynamic Maps", one load per map initialisation. The pricing page (updated 2026-10-23) lists **10,000 free loads per month, then $7.00 per 1,000 up to 100,000** (lower tiers after that). A new Google Cloud account may have a $300 trial credit. [pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [billing overview](https://developers.google.com/maps/billing-and-pricing/billing-overview). **This conflicts with the "free tools only" decision**: it is free only under the monthly allowance, and it requires a billing account. Decide that explicitly. The plain no-tile map is the free fallback.
* **Unrestricted-key abuse** is billed to the key owner: restrict the key (step 4) and cap quota (step 5). [API security best practices](https://developers.google.com/maps/api-security-best-practices).
* **Terms** ([Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms), [JS API policies](https://developers.google.com/maps/documentation/javascript/policies)): no caching/storing/scraping of Google content beyond what the terms allow; do not obscure or alter Google's logo/attribution; do not use Google core services with or near a non-Google map (so no Leaflet or OSM layer beside it); required public terms/privacy pages; get end-user consent before using location with Google services (this app reads geolocation only for its own distance calculation and sends it nowhere; the pins are the app's own overlay, not Google data).
* **Leaflet + Google tiles**: not used. Google's [Map Tiles API 2D tiles policy](https://developers.google.com/maps/documentation/tile/policies) permits display of tiles obtained with session tokens in a viewer, but that API has its own billing/session rules, and I could not extract its price from the pricing page, so no number is given for it.
* Google's Maps terms also restrict listing/directory-style uses; this app is not one, but re-read them before launch.

## Not done / still open
* Region→county definitions (USDA does not publish them, so region pins and the 300-mile edge stay approximate; a region whose approximate centre is just outside 300 mi may partly be inside).
* Real push alerts, the app's own Terms of Use and Privacy Policy pages (required before a public launch when using Google Maps, see below), and USDA/CME written confirmation (CME risk accepted by Ridge per Decisions).

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
  Same data, and it also carries USDA's **futures closing-settlements** table (CBOT/KCBT/MGE) which the app uses for the futures
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
* **Map**: Google Maps JavaScript API when a key is configured (otherwise a plain Leaflet map with no tiles), 300-mi ring, per-commodity/product/delivery pins with bid labels, best bid highlighted, sortable table, EOD futures panel.
* **Best bid near me**: browser geolocation (stays on-device), per-commodity cards with radius filter + top 3 runners-up.
* **Alerts**: local rules (≥/≤ price, per location or any) in localStorage; browser notifications; checked on open and every 15 min while open; once per report day.
  **Limit:** without a server there is no true Web Push — a closed app cannot be woken. Experimental Periodic Background Sync (Chromium, installed PWA) is wired in `sw.js` but untested here and browser-throttled. Real push later = push service + small server (free tiers exist) or email/SMS digests.
* **History**: Chart.js high/low bid lines, compare two locations, range filter. Real history is **1 day** until the daily job accumulates (or MARS backfill); synthetic history is available only with `ALLOW_SAMPLE` true.
* Installable (manifest + service worker; Chrome fired `beforeinstallprompt` in headless test). Responsive 420 px → desktop. Offline: app shell cached, data network-first with cached fallback; map tiles are not cached.
* SAMPLE data is always flagged: yellow banner, “(SAMPLE)” in header/popups, `is_sample=1` rows in `data/sample.db`. The sample fallback and `?sample=1` are disabled unless `ALLOW_SAMPLE` is true in `public/config.js`.

## Verified here
Job 5 (2026-10-27): headless Chrome (CDP) with no key on a non-localhost host showed the plain map, pins, ring and the "Map tiles not configured" notice with no console errors; on localhost the OSM dev map; with a fake key Google answered `InvalidKeyMapError` and the page fell back to the plain map with the notice (the **success path with a valid key is not verified**, no key exists); a copy of the data with only ND aged showed the per-report banner line, the "Not ranked" note on the Best-bid card and the "just outside your radius" list (ND Northeast 304 mi, ND North Central 307 mi). Tests: 32 python, `alerts-core.test.js`, `mapmode.test.js`.
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
6. Map provider: now Google Maps (see **Map (Google Maps)**). OSM tiles are localhost-dev only.
7. Data/terms: AMS data is public; add AMS attribution/disclaimer review before launch.
