# Audit — Grain Marketing App research and plan

Audit date: November 10, 2026 (America/Chicago).  
Scope: the planning-stage repo at `/workspace/grain-marketing-app`. There is still no app code. This is a research-and-plan audit only.

Original elevator list kept as `research/grain_elevators.csv` (899 rows). A cleaned working copy is `research/grain_elevators_cleaned.csv` (875 rows). No data was invented. Coordinates were not guessed for Liberty Grain. Near-duplicate facilities that might be two plants sharing a town pin were flagged, not merged.

Live USDA PDFs were fetched from `https://www.ams.usda.gov/mnreports/ams_<ID>.pdf`. Bid-URL checks recorded HTTP status only, with a research User-Agent, and did not save bid content.

---

## Severity key

- **High** — would mislead a farmer or break a core feature if imported as-is.
- **Medium** — wrong counts, stale docs, or data that needs a human pass before it is used.
- **Low** — naming, rounding, or checklist drift.

---

## Top findings

### 1. High — Many “bid pages” are API endpoints, not pages a farmer can open

205 of 899 rows (kept in the cleaned file too) point `bid_url` at an API, not a public board:

| Host / pattern | Rows | Status on November 10, 2026 (sample) |
| --- | --- | --- |
| `api.bushelpowered.com/.../GetBidsList` | 70 | 404. Every one of these 70 rows shares the same URL. All 70 already have a company cash-bids website (mostly CHS `.../grain/cash-bids` pages; the CHS Holdrege website sample returned 200). |
| `api.dtn.com/markets/sites/.../cash-bids` | 50 | 403 (auth required). Websites are usually the co-op homepage, not a direct bid page. |
| Landus `www.landus.ag/api/cash-bids?location=` | 36 | 429 on this check (rate-limited API). |
| Gradable `/api/commodities/...` (POET, ADM) | 39 | API 200, but the matching Gradable *market* website also 200 and is the better link-out. |
| Grain Discovery `/api/public-sites/...` | 6 | 200 (still an API). |

If the app uses `bid_url` as “View bid,” those farmers will hit a 404, a login wall, or raw JSON. Prefer the website cash-bids page when one exists. Do not scrape or redisplay Bushel, DTN, or Barchart numbers.

Other link issues:

- `https://www.farmerscoopsociety.com/ajax/homepage/dtn-cash-bids` returned **404**. The co-op homepage returned 200.
- 12 bid URLs are bare homepages (for example Lake Norden, Hendricks, Canby, Revillo). Those sites returned 200, but they are not bid boards.
- Four Southeast Farmers rows use the non-standard host `sfc_cb-jsi.agricharts.com` (underscore in the hostname). A curl request returned 200; some browsers reject underscore hosts. The website field uses the same host.
- NEW Cooperative `https://www.newcoop.com/cash-bids` (54 rows) returned 403 to this checker (likely bot protection, not proof the page is down).
- Sample AgriCharts cash-grid pages (Central Farmers, Agtegra, Dakota Mill, Hoven Equity, NuGen, Valley Springs, West-Con, AgMark, CoMark) returned 200.

### 2. High — Exact duplicate locations, mostly AgMark listed twice

28 groups share the same operator, location name, state, and coordinates.

- **24 AgMark LLC. Kansas locations** appear twice, once on `agmarkllc.agricharts.com` and once on `agmarkresp.agricharts.com`, with identical coordinates. These were merged in the cleaned file. Both URLs were kept (`bid_url` plus `alternate_bid_url`). Kansas falls from 71 rows in the original to 47 in the cleaned file. AgMark Speed stays `enabled=False`.
- **Four other pairs were not merged**, because the source filenames look like two facilities that were pinned to the same town point: CHS Holdrege Holdrege (`holdregewest` vs `holdregeshuttle`), CHS High Plains Holyoke (`holyokeshuttle` vs `stateline`; a third Holyoke row sits about a mile away and was left as-is), Heartland Co-op Earlham (`earlham` vs `earlhamfeedmill`), and Frenchman Valley Chappell (`chappell` vs `northchappell`, and the crop tags already disagree — one lists milo, the other does not). Flag: `same_coords_different_source_files`.

Separately, 100 cleaned rows share coordinates with a *differently named* row (town-level pins). Examples near Kimball: Agtegra “Redfield Energy,” “Redfield Elevator,” and several AGP/Aberdeen labels all sit on the same point. These were flagged (`shared_coords_different_name`) and not merged.

### 3. High — Minnesota mapping and freight terms will skew net-price ranking if ignored

- **AMS_3049 is “Southern Minnesota Daily Grain Bids,”** with a single “South” country-elevator region, corn and soy only. The CSV has 135 Minnesota buyers. 33 of them sit at latitude 45° or farther north (Fisher, Beltrami, Halstad, Mahnomen, Ada, Fergus Falls, Barnesville, and others), and 64 sit at 44.5° or farther north. Applying the Southern Minnesota range to those locations would be wrong. Minnesota has no statewide country-elevator report.
- **AMS_3046 (Minneapolis Daily Grain Report)** exists and was fetched (200, report date November 9, 2026). It is *terminal* bids, not country elevators, so it does not fill the northern Minnesota gap. **AMS_3045** is a MIAX Futures Exchange floor summary, not a cash country-elevator report, and should not be used in this app.
- **North Dakota AMS_3878 quotes FOB-T.** The other eight planned reports quote **DLVD-T**. A flat midpoint comparison will mix delivered and FOB prices. The plan does not mention this.
- Even inside a covered state, not every region has every crop. On the October 26, 2026 South Dakota report, white oats were listed only in Northeast and East Central, and hard-red spring wheat was missing from Southeast.

### 4. Medium — Document contradictions and stale status

- `README.md` “Decisions so far” still says “KS and CO map to the nearest state report.” The later plan update, and the build-plan Page, correctly say KS and CO use their own reports (AMS_2886 and AMS_2912). That README line is stale.
- South Dakota is counted two ways: **116** total in the CSV (and the plan Page), vs **115** in `research/grain_elevators_summary.md` and in `research/canvas.tsx` metrics. The 115 figure is the 116 SD rows minus Liberty Grain (no bid page).
- “Within 150 miles: 156” uses *listed, rounded* miles, including Liberty Grain (no coordinates) and three locations listed as 150 whose computed distance is 150.09–150.55 miles (Maurice IA, Brunsville IA, Revillo SD). Computed haversine ≤ 150 miles: 152 rows with coordinates.
- The plan Page laptop checklist still says Git needs go-ahead. Git for Windows was already installed on Graden’s laptop. Free Supabase, Expo, and OpenRouteService accounts were not created. The repo still has no GitHub or Origin remote; this audit commits locally only.
- `canvas.tsx` is a 150-mile snapshot (156 hardcoded rows) under a title that says 300 miles. The crop filter value `"wheat"` matches spring wheat, winter wheat, and “hrw wheat” because it uses `includes`. The state filter omits KS and CO, which is harmless for this 150-mile slice (none are that close) but incomplete if the table is ever expanded.

### 5. Medium — List quality: missing pin, stale names, unverified source

- **Liberty Grain LLC, Kimball (listed 6 miles east),** is the only row with no latitude or longitude, a blank `enabled` flag (set to `False` in the cleaned file), and `bid_url` of `unknown (none found)`. It is the closest buyer in the list and still unverified. Coordinates were not invented.
- **VERBIO North America LLC, Nevada, IA** is listed at 300 miles; haversine from 43.75, −98.96 is **300.15** miles. Flag only. Road miles will likely be longer, so the M3 routing batch may drop it.
- **18 rows** use deprecated-looking operator names still marked `enabled=True`: `zWest-Con` (5), `zFarmers Cooperative Elevator Co.OLD` (11), `zFinley Farmers Grain & Elevator` (2).
- **28 rows** use the widget title `Cash Bid JSI Site - Ag State` as the operator name (should be reviewed against the real Ag State name).
- One likely typo: Frontier Cooperative **Tecumsech**, NE (probably Tecumseh). Not renamed.
- Crop tags that need a human pass: `wht`; `hard red` / `red winter` alongside winter or spring wheat; Liberty Grain “soybeans (2012 report); current unknown.” Tags are inconsistent (`soybean` vs `soybeans`, `wheat` as a generic catch-all on 768 rows). Sunflowers appear on only five boards, all Dakota Mill & Grain in South Dakota. Oats appear on 16 boards (14 SD, 1 MN, 1 NE).
- The list comes from the unverified public repo [dnilgis/bids](https://github.com/dnilgis/bids) (no LICENSE). Treat it as a research index only.
- Location precision: 573 town, 273 street, 3 county, 49 blank, 1 “news report.” That matches the plan’s “50 blank or other” if the news-report row is included. Town-level pins are why so many different names share coordinates.

No rows had invalid or swapped coordinates. Listed integer miles match haversine from 43.75, −98.96 within 1 mile, except the three 150-mile rounding cases and Liberty Grain (no pin). State counts in the *original* file match the plan: IA 276, NE 244, MN 135, SD 116, KS 71, ND 49, CO 8.

---

## USDA report IDs

All nine planned public PDFs returned HTTP 200 on November 10, 2026, with a “Final” report dated **November 9, 2026**. Local copies in `research/usda_reports/` are the earlier **October 26, 2026** finals. Titles, areas, and cash crops match the plan:

| ID | Title (verified) | Cash crops on the report (not the futures table) | Notes |
| --- | --- | --- | --- |
| AMS_3186 | South Dakota Daily Grain Bids | Corn, soybeans, HRS (14.0%), HRW (ordinary), white oats | Oats only in some SD regions. |
| AMS_3878 | North Dakota Daily Grain Bids | Corn, soybeans (#2, not #1), HRS milling 14.0% | **FOB-T.** No HRW, no oats. |
| AMS_3225 | Nebraska Daily Elevator Grain Bids | Corn, sorghum, soybeans, HRW | 7 corn regions, as planned. Not every crop in every region. |
| AMS_2850 | Iowa Daily Cash Grain Bids | Corn, soybeans | 6 country-elevator regions plus Southwest terminals. |
| AMS_3049 | Southern Minnesota Daily Grain Bids | Corn, soybeans | Single “South” region only. |
| AMS_3043 | Iowa–Southern Minnesota Barge Terminal Grain Bids | Corn, soybeans | River terminals, not country elevators. |
| AMS_2886 | Kansas Daily Grain Bids | Corn, sorghum, soybeans, HRW, hard white wheat | Hard white confirmed. |
| AMS_2912 | Colorado Daily Grain Bids | Corn, sorghum, soybeans, HRW | Points sunflower/millet to AMS_2887. |
| AMS_2887 | National Daily Sunflower, Canola, Millet, and Flaxseed Report | NuSun and high-oleic sunflower, plus canola, millet, flax, in **$/cwt**, by town | Towns on the Oct 26 copy included Akron, CO; Jamestown, KS; Enderlin, ND; West Fargo, ND. These must be matched to elevators, not applied as a state range. |

`https://www.ams.usda.gov/mnreports/ams_3226.pdf` returns **404**. That is expected: MyMarketNews notes that on August 3, 2020, AMS_3226 was folded into AMS_2850. The plan’s “includes AMS_3226” wording is historically right; do not fetch 3226 as a separate PDF.

Every one of these PDFs also prints **CBOT / KCBT / MGE futures settlements**. The app must parse only the cash bid tables. Redisplaying those settlements would be exchange data, which the plan already says v1 will not show.

Sunflower gap in the elevator list: ADM Enderlin is in the CSV as `enabled=False` and tagged canola only, even though AMS_2887 also quotes sunflowers at Enderlin and West Fargo. West Fargo / Cargill crush bids are not in the list as sunflower plants.

---

## Trucking math (Iowa State A3-10, 2026)

Source checked November 10, 2026: [2026 Iowa Farm Custom Rate Survey (A3-10)](https://www.extension.iastate.edu/agdm/crops/pdf/a3-10.pdf) (HTTP 200; FM 1698, revised March 2026).

Under “Hauling grain … to market, truck”:

| One-way trip | Average, $/bu | Median | Range (trimmed) | Responses |
| --- | --- | --- | --- | --- |
| 5 miles | 0.135 | 0.120 | 0.060–0.500 | 96 |
| 25 miles | 0.200 | 0.200 | 0.090–0.350 | 97 |
| 100 miles | **0.405** | 0.400 | 0.180–0.650 | 46 |

The plan’s arithmetic is correct: `0.405 $/bu ÷ 100 miles × 1,000 bu = $4.05 per loaded mile`, or `$0.00405 per bushel per mile`.

Caveats, which the plan already flags in part:

- **1,000 bu per load is still not in A3-10.** It is an assumption. Soybeans and wheat loads are typically fewer bushels than corn at the same weight limit.
- A flat per-mile default **undercharges short hauls**. Implied cost from the same survey: about $0.027/bu/mi at 5 miles and $0.008/bu/mi at 25 miles, versus $0.00405 at 100 miles. The plan’s cross-checks mention this; the default still uses the 100-mile figure.
- These are Iowa custom rates, not a South Dakota farm-truck survey.
- Net price is USDA midpoint minus this estimate, not an elevator’s bid.

---

## `canvas.tsx` issues

- Metrics: “115 in South Dakota” and “156 within 150 mi” have the counting quirks above.
- Title says 300 miles; the table is the 150-mile subset only (156 rows), which matches the section caption but not the page title.
- Crop filter `"wheat"` is too broad; `"soybean"` happens to match `soybeans` too.
- Hardcoded snapshot will drift as the CSV is cleaned; it is a research Page export, not app code.
- Several bid links in that snapshot are the same API endpoints called out above.

No syntax issues were found in the file (it is a single Canvas module with a large inline array).

---

## Risks (licensing, free tiers)

- **dnilgis/bids has no LICENSE.** Use as an index, then verify against each elevator’s own page (already the plan).
- **Barchart / DTN / Bushel terms** still forbid scraping or redistributing bids. Link out only.
- **USDA cash tables are public**, but the same PDFs contain futures settlements. Skip that block in both adapters.
- **Supabase free-tier pause** after about a week of inactivity remains a real off-season risk. Whether the weekday cron counts as activity was not re-verified in this audit.
- **OpenRouteService** is one-time batch only; use the current HeiGIT host, as the plan says.
- **Apple Developer Program ($99/year)** is still waiting on Graden’s later approval; Expo Go is enough through M7.

---

## Fixes made in this commit

In `research/grain_elevators_cleaned.csv` only (original CSV unchanged):

- Merged 24 exact AgMark dual-widget duplicates (899 → 875 rows). Alternate URL, website, and source are preserved.
- Added `computed_miles_from_kimball` (haversine, statute miles, WGS-84 mean radius 3958.7613) from Kimball origin **43.75, −98.96** — the same origin the listed integer miles used.
- Added `audit_flags` and original line numbers.
- Set Liberty Grain `enabled` from blank to `False` and flagged `enabled_blank_set_to_false`.
- Flagged missing coordinates, the 300.15-mile VERBIO row, rounded 150-mile boundary rows, API and homepage bid URLs, the underscore hostname, deprecated `z…` / `.OLD` operator names, the “Cash Bid JSI Site” labels, the Tecumsech typo, odd crop tags, blank precision, and same-coordinate collisions.

Docs:

- Added this file and `ENHANCEMENTS.md`.
- Updated `README.md` to link both, to correct the KS/CO mapping contradiction, and to point at the cleaned CSV.

Not changed: `research/canvas.tsx` (research snapshot), plan Page (lives outside the repo), live USDA files (local copies kept as the October 26, 2026 snapshot).

---

## Still open

- Confirm Liberty Grain’s coordinates, crops, and whether it still buys grain (needs a local check or a call; approval required before any call).
- Human-verify the 4 same-pin facility pairs, the 18 `z` / `.OLD` operators, “Cash Bid JSI Site - Ag State,” and town-level shared pins, closest first.
- Replace API `bid_url` values with farmer-facing pages where a website already has one. Do not invent URLs that are not already in the data.
- Map each elevator to the correct USDA region; do not assign AMS_3049 to northern Minnesota; handle ND FOB vs DLVD elsewhere.
- Match AMS_2887 towns to elevators; decide what to show when there is no town match (including Dakota Mill locations that list sunflowers on their boards but may not appear in the USDA town table).
- Road-route from Kimball and drop locations beyond 300 *road* miles (M3). Straight-line 300 is only a first cut.
- GitHub / Origin backup of this repo still has not been pushed (no remote). That needs Graden’s GitHub sign-in.
- Free Supabase, Expo, and OpenRouteService accounts are still outstanding, and need Graden’s sign-up (passwords stay in his password manager).
