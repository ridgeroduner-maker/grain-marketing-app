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
| `MAP_TILES_URL` | `tiles/plains.pmtiles` | **The one map setting.** A `.pmtiles` path/URL = self-hosted vector tiles (default); a `https://…/{z}/{x}/{y}.png` URL = any raster provider (`{key}` is filled from `MAP_TILES_KEY`); empty = no tiles (plain map + notice). Only a relative path or an `https://` URL is accepted. See **Map**. |
| `MAP_TILES_KEY` | `''` | Only for a keyed raster provider. **Never committed**: from env/`.env`, appended to `dist/config.js` by `build_dist.sh` (or in memory by `serve.sh`). The default map needs no key. |
| `MAP_TILES_ATTRIBUTION`, `MAP_TILES_MAX_ZOOM`, `PMTILES_DATA_MAX_ZOOM` | OSM + Protomaps, `10`, `9` | Credit text (OpenStreetMap contributors is required), the map's max zoom, and the data zoom the extract was built to (`MAXZOOM` in `build_tiles.sh`). |
| `DEV_OSM_TILES_ON_LOCALHOST` | `true` | **Development only**: when `MAP_TILES_URL` is empty, OSM public tiles are drawn **only on localhost/127.0.0.1** ([OSM policy](https://operations.osmfoundation.org/policies/tiles/)); any other host gets the plain map. |
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

## Map (Job 6: free, no account, no key, no billing)
Ridge declined Google billing, so Google Maps is **removed** (code, config, CSP, README steps, tests). The map is now **self-hosted Protomaps vector tiles (OpenStreetMap data) drawn in Leaflet**, served as one static file from the same site.

**How it works.** `public/mapmode.js` reads the single setting `MAP_TILES_URL` and picks `pmtiles` (default), `xyz` (raster provider), `osm-dev` (localhost only, URL empty) or `blank`. For `pmtiles`, the page first reads the first 1 KB of the file with a `Range` request and checks for a `206` and the `PMTiles` magic bytes; then it loads the vendored `protomaps-leaflet` and adds the layer to the same Leaflet map that holds the pins, the 300-mile ring and the dashed "~" region pins. If the file is missing, the host ignores Range (answers 200), the script fails, or an XYZ provider fails 4 tiles in a row with none loaded, the page switches to the **plain map with a notice** that names the cause. Nothing is requested from any other company in the default setup.

**What Ridge must do (one time, free, no account):**
1. Get the `pmtiles` command-line tool (one file, BSD-3-Clause): <https://github.com/protomaps/go-pmtiles/releases>; put it on PATH.
2. Run `./build_tiles.sh`. It finds the newest daily Protomaps build and extracts a box of about 350 mi around Gann Valley (bbox `-106.04,38.96,-91.94,49.10`, zoom 0 to 9) into `public/tiles/plains.pmtiles` (**about 17 MB**, 4 to 8 s here). The file is git-ignored on purpose; rebuild it now and then (roads and towns change slowly) by running the script again.
3. `./serve.sh` to look at it locally, then `./build_dist.sh` (copies the file into `dist/tiles/`).
4. Host `dist/` on a static host that answers HTTP **Range** requests with **206**. See hosting below. **GitHub Pages is the safest free pick.** Nothing was deployed by this build.
Optional: `MAXZOOM=10 ./build_tiles.sh` (about 38 MB, sharper; set `PMTILES_DATA_MAX_ZOOM` and `MAP_TILES_MAX_ZOOM` in `config.js` to 10 and 11).

**Why this option (read 2026-10-27).**
* It needs **no account, key, card, quota or third party at runtime**; the file is yours, so there is no terms change, outage or rate limit to depend on, and nobody else learns where a farmer looked.
* [OpenFreeMap](https://openfreemap.org/) is the runner-up (also no account/key): its [home page](https://openfreemap.org/) says "Using our public instance is completely free: there are no limits on the number of map views or requests. There's no registration, no user database, no API keys, and no cookies. We aim to cover the running costs of our public instance through donations." But its [terms](https://openfreemap.org/tos/) say "THE SITE IS PROVIDED “AS-IS,” “AS AVAILABLE,” AND “WITH ALL FAULTS.” WE MAKE NO WARRANTIES REGARDING ACCURACY, AVAILABILITY…", "We aim to maintain the Site’s availability but may discontinue it at any time without notice", and "We may use Cloudflare as a CDN… By using the Site, you consent to Cloudflare’s processing of your requests." A public app would depend on a donation-funded service with no SLA, and its vector tiles need MapLibre GL (WebGL, a much bigger library than Leaflet's plugin). Not chosen; easy to add later as one more provider.

**Terms and licences relied on.**
* **Data**: the [Protomaps downloads page](https://docs.protomaps.com/basemaps/downloads) says the basemap is "derived from OpenStreetMap… distributed as an Open Database License Produced Work (OpenStreetMap attribution required)". Attribution shown: "© OpenStreetMap contributors · Protomaps basemap" on the map, under it and in the footer. The same page: "hotlinking to these downloads are discouraged. Instead, you should copy the tileset to your own Cloud Storage", which is why the app serves its own extract and the build script does one extract rather than linking to their file. The `extract` command is documented in the [pmtiles CLI docs](https://docs.protomaps.com/pmtiles/cli) ("Create a smaller archive from a larger archive… The source archive may be local or remote").
* **Libraries** (vendored, unmodified, licence texts in `public/vendor/`): protomaps-leaflet 5.1.0 BSD-3-Clause (bundles the PMTiles reader, also BSD-3-Clause); Leaflet 1.9.4 BSD-2-Clause. The protomaps-leaflet bundle works with Leaflet 1.9.x (it needs `L` as a global and extends `L.GridLayer`; verified here with 1.9.4). **Caveat**: the [Protomaps Leaflet docs](https://docs.protomaps.com/basemaps/leaflet) say "The `protomaps-leaflet` library… is in maintenance mode. You should only use it for legacy projects that depend heavily on Leaflet - otherwise use MapLibre GL JS." The vendored copy is pinned, so it will not change under you; the cost is that new features go to MapLibre.
* **Costs**: none. The hosts below are free tiers; I did not create or check any account.

**Hosting the 17 MB file (limits read 2026-10-27):**
| Host | File / site limit | Range requests | Verdict |
|---|---|---|---|
| GitHub Pages | "Published GitHub Pages sites may be no larger than 1 GB"; soft limit "100 GB per month" bandwidth ([limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)) | Serves `.pmtiles` with 206; Protomaps lists it as an easy host ([cloud storage](https://docs.protomaps.com/pmtiles/cloud-storage)). A 2025 Firefox problem was reported fixed in March 2026 ([issue 584](https://github.com/protomaps/PMTiles/issues/584)). | Recommended |
| Netlify | no hard per-file limit found; staff: "the recommended size for uploading to deploys is no more than 10MB" ([forum](https://answers.netlify.com/t/what-is-the-maximum-allowed-object-size/145182)); free plan has 300 credits, bandwidth 20 credits/GB ([pricing](https://netlify.com/pricing)) | A user reports PMTiles working on Netlify ([issue 584](https://github.com/protomaps/PMTiles/issues/584)) | Probably fine; 17 MB is above the 10 MB advice; watch the credit meter |
| Cloudflare Pages | "The maximum file size for a single Cloudflare Pages site asset is 25 MiB" ([limits](https://developers.cloudflare.com/pages/platform/limits/)) | "Pages currently returns `200` responses for HTTP range requests; however, the team is working on adding spec-compliant `206`" ([serving pages](https://developers.cloudflare.com/pages/configuration/serving-pages)) | **Do not use** for this file: the app detects the 200 and shows the plain map with a notice |
GitHub Pages terms for the account should be re-read before launch (free app, no payments, so I expect no issue; not checked here).

**Other providers considered (all need an account, so not chosen):**
* **MapTiler** [free plan](https://www.maptiler.com/cloud/pricing/): "Suitable for testing, PoC, prototyping, personal, or non-commercial use", "No credit card needed", "MapTiler logo on the map"; its comparison table puts "Commercial use" under the paid plans (I could not read the exact free-plan cell, so treat commercial use as not allowed). A key is required.
* **Stadia Maps** [pricing](https://stadiamaps.com/pricing/): Free "200,000 credits/month… No additional usage… Commercial use not allowed"; needs an account and a key or domain registration ([auth docs](https://docs.stadiamaps.com/authentication/)).
* **Thunderforest** [pricing](https://www.thunderforest.com/pricing/): "Hobby Project… 150,000 tile requests per month… Free"; account and key needed; the Hobby plan is for trying ideas.
* **OSM public tiles**: the [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) says "heavy or inappropriate use harms others’ ability to edit and view the map. We may block access, without notice… there is no SLA or guarantee." Used only on localhost in development (`DEV_OSM_TILES_ON_LOCALHOST`).
To use a raster provider anyway: set `MAP_TILES_URL` to its `https://…/{z}/{x}/{y}.png?key={key}` URL, put the key in `.env` as `MAP_TILES_KEY`, set `MAP_TILES_ATTRIBUTION` to the provider's required text plus "© OpenStreetMap contributors", and re-read its terms (the three above restrict or limit free use). Add its host to the CSP `img-src`.

**Recommended CSP when hosting** (tested here on the map page with the default setup: map tiles, pins and ring rendered and no console violations; a `<meta>` copy is not shipped in `index.html`, so add it as a response header or meta tag at your host): `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`. Other tabs (History charts, alerts) were not run under this CSP.

**Caching.** `sw.js` (v6) ignores cross-origin requests and `.pmtiles` requests (a cached 200 copy would break range reads) and does not precache the tile file, so the map needs the network; offline you get the plain map with the notice. Tests assert both rules.

**Privacy**: with the default setup the map makes no third-party requests. A raster provider or `osm-dev` would see visitors' IP addresses and map areas.

## Draft legal pages (Job 7) - **DRAFT, not legal advice, have a lawyer review**
`public/terms.html` and `public/privacy.html` are **drafts written for Ridge's review**, not legal advice and not final. Each file carries a red "DRAFT - not legal advice, have a lawyer review" banner at the top. They are plain static pages with the site's styling (no JavaScript, mobile-friendly), linked from the footer of `index.html` and to each other, copied into `dist/` by `build_dist.sh` (the build fails if either is missing). Everything still to be supplied is a yellow **`[[PLACEHOLDER]]`**: `[[OWNER LEGAL NAME]]`, `[[CONTACT EMAIL]]`, `[[EFFECTIVE DATE]]`, `[[GOVERNING STATE: likely South Dakota, Ridge to confirm]]`, `[[HOST: GitHub Pages is the intended host - TBD ...]]`, plus a few `[[LAWYER: ...]]` / `[[OWNER TO CONFIRM ...]]` notes. Nothing (name, email, date) was invented. **Remove the DRAFT banner only after review.**

**Service worker**: both pages are precached (`sw.js` SHELL, cache version bumped `grain-v5` to `grain-v6`) so the footer links work offline in an installed app; after that they are served network-first like other app files, so edits reach people. A test checks every precached file exists.

**What the Privacy Policy says, and where I checked it in the code** (tests in `ingest/tests/test_legal.py` keep this true):
* **No accounts / no server-side user data**: no sign-in or server code in `public/`; the only network calls are same-site (`data/*.json`, `sw.js` fetching `data/latest.json`, a Range probe of `tiles/plains.pmtiles`). None carries alerts, location or settings.
* **Alerts/settings**: `localStorage` keys `grain.alerts` and `grain.me` only, plus an IndexedDB copy (`grain-app` / `kv`) so the service worker can check alerts; Cache Storage holds the app shell and data files (never the `.pmtiles`). No `sessionStorage`.
* **Geolocation**: one `getCurrentPosition` call, inside `locate()`, reached only from the "Use my location" button; low accuracy, 15 s timeout, 10 min cached position allowed; the result goes to `localStorage` (`grain.me`, kept until the user clears site data) and is used in the browser for distances and the map dot, never sent anywhere. The browser asks permission; refusal falls back to Gann Valley. The page says so.
* **Notifications**: permission requested only from the "Enable notifications" button; alerts are evaluated on the device; the page registers Chrome Periodic Background Sync if available (browser-gated, experimental); no push server.
* **Cookies/analytics**: no `document.cookie`/cookieStore, no analytics, ads or beacons in the app or vendored libraries (scan of `dist/`).
* **External requests**: scan of the built `dist/` found no external scripts, styles, fonts, images or CDNs; the only absolute URLs are plain links (USDA, OpenStreetMap, Protomaps, ODbL, Leaflet, Chart.js) and the OSM dev tile URL in `mapmode.js`, used only on localhost with `MAP_TILES_URL` empty. Headless Chrome loaded the index, terms and privacy pages with every resource coming from the one local host and empty `document.cookie`.
* **Host**: GitHub Pages named as the intended host, marked TBD; the page says host logs are the host's.

**Open questions for Ridge**
1. Legal name of the owner (person or business) to put in `[[OWNER LEGAL NAME]]`?
2. A contact email for `[[CONTACT EMAIL]]` (a role address you are happy to publish)?
3. Effective date (the day you publish after review)?
4. Governing state (likely South Dakota) and any venue/dispute wording?
5. Is GitHub Pages really the host? Can you see any of its logs or statistics (the draft says only that the host keeps its own)? If you switch to a keyed or outside map provider, the privacy page must change first.
6. CME Group: you accepted the display risk; does the lawyer want a permission, a different credit line, or `FUTURES_DISPLAY=basis_only`?
7. Is the liability limit enforceable as written in your state, and do you want a dollar cap?
8. Do you want a "forget my location" button (today it is cleared only by clearing site data)?
9. Children's wording and any state-law notices (the draft claims no personal data is collected by the app itself).
10. Should the footer say "draft" until review, or should the links stay hidden until launch?

## Not done / still open
* Region→county definitions (USDA does not publish them, so region pins and the 300-mile edge stay approximate; a region whose approximate centre is just outside 300 mi may partly be inside).
* Real push alerts, a lawyer's review and sign-off of the DRAFT Terms of Use and Privacy Policy pages (see **Draft legal pages**), and USDA/CME written confirmation (CME risk accepted by Ridge per Decisions).

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
Static site (no backend): `index.html, app.js, style.css, manifest.webmanifest, sw.js, alerts-core.js, icons/, vendor/` (Leaflet 1.9.4, protomaps-leaflet 5.1.0, Chart.js 4.4.4 vendored) + `tiles/plains.pmtiles` (built by `build_tiles.sh`, git-ignored) + JSON in `data/` (`meta, latest, history, futures`).
* **Map**: Leaflet over self-hosted Protomaps tiles (OSM data; plain map with a notice if the tile file is missing or the host lacks Range support), 300-mi ring, per-commodity/product/delivery pins with bid labels, best bid highlighted, sortable table, EOD futures panel.
* **Best bid near me**: browser geolocation (stays on-device), per-commodity cards with radius filter + top 3 runners-up.
* **Alerts**: local rules (≥/≤ price, per location or any) in localStorage; browser notifications; checked on open and every 15 min while open; once per report day.
  **Limit:** without a server there is no true Web Push — a closed app cannot be woken. Experimental Periodic Background Sync (Chromium, installed PWA) is wired in `sw.js` but untested here and browser-throttled. Real push later = push service + small server (free tiers exist) or email/SMS digests.
* **History**: Chart.js high/low bid lines, compare two locations, range filter. Real history is **1 day** until the daily job accumulates (or MARS backfill); synthetic history is available only with `ALLOW_SAMPLE` true.
* Installable (manifest + service worker; Chrome fired `beforeinstallprompt` in headless test). Responsive 420 px → desktop. Offline: app shell cached, data network-first with cached fallback; map tiles are not cached.
* SAMPLE data is always flagged: yellow banner, “(SAMPLE)” in header/popups, `is_sample=1` rows in `data/sample.db`. The sample fallback and `?sample=1` are disabled unless `ALLOW_SAMPLE` is true in `public/config.js`.

## Verified here
Job 7 (2026-10-27): headless Chrome on `serve.py`: terms and privacy pages at 390 px and 1200 px wide, no horizontal overflow, DRAFT banner and highlighted placeholders visible, no console errors, only the local host contacted, `document.cookie` empty; the index footer links to both; the service worker installed cache `grain-v6` containing `/terms.html` and `/privacy.html` and no `.pmtiles`. Tests: 47 python (12 new in `test_legal.py`), `alerts-core.test.js`, `mapmode.test.js`. **Not verified**: legal accuracy (no lawyer), real host logging behaviour, other browsers/phones, screen-reader pass of the new pages.
Job 6 (2026-10-27): the extract was really built with `./build_tiles.sh` (free CLI, no account; 17 MB, `pmtiles verify` ok) and served by `serve.py` with Range support. Headless Chrome (CDP): (a) on `localhost` and (b) on a non-localhost host name, **real map tiles rendered** (16 tile canvases, roads/labels/states visible, 18 pins, ring, attribution "Leaflet | © OpenStreetMap contributors · Protomaps basemap", no console errors, no notice); (c) a host that ignores Range (python `http.server`) gave the plain map with the notice "the web host does not support HTTP Range requests (it answered 200, not 206)"; (d) file missing gave the notice "…is not on the server — build it with ./build_tiles.sh"; (e) an unreachable raster URL gave the plain map and notice after 4 failed tiles; (f) with a strict CSP meta (see Map) the map rendered with no violations. WebGL is not needed. **Not verified**: any real static host (GitHub Pages/Netlify/Cloudflare) because nothing was deployed (host behaviour comes from the docs/issue linked above); raster providers (no accounts); OSM dev tiles on localhost in this job; Firefox/Safari; phones; the service worker + map offline path in a browser. Tests: 35 python, `alerts-core.test.js`, `mapmode.test.js`.
Job 5 (2026-10-27, superseded map parts): the Google Maps adapter described there was removed in Job 6; the stale-report, outside-radius and a11y checks still apply.
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
6. Map provider: now self-hosted Protomaps PMTiles in Leaflet (see **Map**). Where will it be hosted? GitHub Pages is the safest free choice for the 17 MB file; Cloudflare Pages will not work for it. OSM public tiles are localhost-dev only.
7. Data/terms: AMS data is public; add AMS attribution/disclaimer review before launch.
