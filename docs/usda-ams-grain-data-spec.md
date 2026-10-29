# USDA AMS Market News – Data Spec for Ridge's Public Grain Marketing App

*Draft, research only. Prepared 2026-10-27 (America/Chicago). Nothing was sent, signed up for, or contacted. Scope: corn, spring wheat (HRS), winter wheat (HRW), soybeans, sunflowers within ~300 miles of Gann Valley, SD.*

**How to read the evidence tags:** every claim cites a URL in the Source List (S1…). *"Observed 2026-10-27"* = I fetched it myself that day with plain GET/curl. *"Search snippet only"* = I could not open the page myself (the `mymarketnews.ams.usda.gov` host timed out / returned HTTP 500 / HTTP/2 stream errors from my box and from the fetch tool), so the claim rests on a search-engine excerpt of that page. *"Could not be found"* = stated explicitly.

---

## 0. Executive summary

1. **The five reports Bobby named are real, current, and published every business day** as final PDFs: SD **3186**, ND **3878**, NE **3225**, southern MN **3049**, Iowa **2850** (Iowa's ID: "Iowa Daily Cash Grain Bids", slug `AMS_2850`), sunflowers **2887** ("National Daily Sunflower, Canola, Millet, and Flaxseed Report"). All six were fetched 2026-10-27 from `https://www.ams.usda.gov/mnreports/ams_<id>.pdf` with plain GET → HTTP 200 (S5–S10).
2. **No API key is needed to download the PDFs** and a keyless "public" API lists publication metadata (S11), but **the data API itself (`marsapi.ams.usda.gov/services/v1.2/reports/<id>`) refused an unauthenticated call with HTTP 403** (observed 2026-10-27). USDA docs say a free eAuthentication-based account/API key is needed (S12, S13). Registration is a step for **Ridge** – I did not do it.
3. **Reports are regional aggregates, not elevator-by-elevator.** Each row = state sub-region (e.g., SD "North Central") × commodity × delivery period with a basis *range*, price range, simple average and year-ago average. The old per-town Sioux Falls text report (`SF_GR110`) is no longer a current product in what I could retrieve (S14, S15).
4. **Cash price = futures settlement + basis** is verifiable directly in the report (worked examples in §4; I checked every example by arithmetic).
5. **Sunflowers are the weakest coverage:** report 2887 on 2026-10-26 had **no confection or oil-type sunflower rows**, **no SD location**, and **no basis**; only High-Oleic bids at two North Dakota processors (Enderlin, West Fargo) plus Colorado/Kansas NuSun/High-Oleic rows – all quoted in **$/cwt delivered** (S10).
6. **Licensing:** USDA site content is generally public domain with attribution requested (S16). I **could not find** a My Market News–specific terms-of-use page. The futures settlements printed inside the USDA reports originate with exchanges; CME's own website terms bar redistribution/derived databases without written consent (S17) – **unresolved risk** for republishing futures numbers (see §7).

---

## 1. Report inventory

Release times: from the keyless MARS public listing (`publishedDate`, converted from MDT to America/Chicago) for **Mon 2026-10-26** (S11). Only one day's timestamp per report was retrievable, so "typical" = that one observation; for SD and Iowa a second data point exists from the MMN file repository for Mon 2026-10-19 (SD 2:46 pm, Iowa 2:44 pm; time-zone label not shown on that page – S18, search snippet only). Treat all times as "approx. 12:45–3:40 pm Central, each business day"; **re-measure over several weeks before scheduling pollers**.

| # | Report (title in USDA feed) | MARS ID / slug | Commodities (observed 10/26) | Geography | Frequency | Release 10/26 (Chicago) | Formats retrieved / listed | Link |
|---|---|---|---|---|---|---|---|---|
| 1 | South Dakota Daily Grain Bids | **3186** / `AMS_3186` (market "Grain – South Dakota", Point of Sale – Grain, from Minneapolis, MN – S19) | US#2 Yellow Corn; US#1 Soybeans; US#1 HRS wheat (14% protein); US#1 HRW wheat; US#2 White Oats | SD in 5 sub-regions: North Central, Northeast, Southeast, Central, East Central | Daily (business days) – S20 | 2:28 pm | PDF (S5); MMN page; JSON/XLSX via keyed API (S13) | S5, S19 |
| 2 | North Dakota Daily Grain Bids | **3878** / `AMS_3878` | US#2 Yellow Corn; US#2 Soybeans; US#1 Milling HRS (14%) | ND: Northwest, North Central, Northeast, Central, East Central | Daily | 2:46 pm | PDF (S6) | S6, S21 |
| 3 | Nebraska Daily Elevator Grain Bids | **3225** / `AMS_3225` | US#2 Yellow Corn; US#2 Sorghum; US#1 Soybeans; US#1 HRW wheat | NE: Northwest, Northeast, Southwest, Southeast, South, East, Central (varies by crop) | Daily | 2:05 pm | PDF (S7) | S7 |
| 4 | Southern Minnesota Daily Grain Bids | **3049** / `AMS_3049` | US#2 Yellow Corn; US#1 Soybeans – *no wheat* | "South" only, with Current and deferred (May) delivery rows | Daily | 1:50 pm | PDF (S8) | S8, S22 |
| 5 | Iowa Daily Cash Grain Bids | **2850** / `AMS_2850` (Des Moines, IA – S23) | US#2 Yellow Corn; US#1 Soybeans (+ state-average header line) – *no wheat* | IA: Northwest, North Central, Northeast, Southwest, South Central, Southeast; separate Terminal (Council Bluffs) and Mills/Processors tables | Daily | 3:29 pm | PDF (S9) | S9, S23 |
| 6 | National Daily Sunflower, Canola, Millet, and Flaxseed Report | **2887** / `AMS_2887` (MN Dept. of Ag Market News) | Canola; White Millet; US#1 NuSun sunflower; US#1 High-Oleic sunflower | Named locations (Hallock MN; Enderlin, Velva, West Fargo ND; Akron CO; Flagler, Otis, Paoli, Peetz, Roggen CO; Jamestown KS) | Daily (the USDA State Grain Reports index labels one link "National Weekly Sunflower and Flaxseed Report" for the same PDF – S24 – but the report itself is daily-dated 10/26) | 3:35 pm | PDF (S10) | S10 |
| 7 | Iowa – Southern Minnesota Barge Terminal Grain Bids (barge basis; useful as a "river" reference) | **3043** | Corn, soybeans | North Iowa / South Iowa / South Minnesota MS River barge elevators | Daily | 3:36 pm | PDF (S25) | S25 |
| 8 | Minneapolis Daily Grain Report | **3046** | Corn & soy terminal; US#1 Northern/Dark Northern Spring wheat delivered Chicago/beyond; oats | Minneapolis terminal | Daily | 1:50 pm | PDF (S26) | S26 |
| 9 | Minneapolis Basis Report / "MIAX Futures Floor Trading Summary" (MS_GR112) | **3045** | HRS wheat basis by protein vs Dec | Minneapolis (MIAX floor) | Daily | 12:45 pm | PDF (S27) | S27 |
| 10 | Kansas City Board of Trade Daily Wheat Bids | **3223** | HRW wheat by protein, FOB rail, basis vs Dec | Kansas City | Daily | 1:51 pm | PDF (S28) | S28 |

Notes
- Every one of these PDFs repeats the same **"Futures Settlements" header block** (CBOT corn/soy/wheat/oats, KCBT wheat, "MGE" wheat), so one report is enough to capture settlements (S5).
- **Excluded as outside 300 mi (informational):** Montana Daily Elevator Grain Bids `AMS_2771` (S29); Colorado, Kansas, Wyoming bids (S24 index).
- **Sioux Falls-specific / per-elevator report:** the legacy `SF_GR110` text report (Oct 2017 archived copy lists ~65 towns with corn/soy/DNS/HRW bids – S15) – today `https://www.ams.usda.gov/mnreports/SF_GR110.txt` answers HTTP 302 to `search.ams.usda.gov` (observed 2026-10-27), and I could not open the redirect target (TLS error). **Treat per-town SD bids as "could not be found" in current USDA products.**
- **Other grain-related reports in the same public catalog that are not in the six** (not opened, listed only because they appear in S11): National Weekly Non-GMO/GE Grain Report (2920), National Organic Grain and Feedstuffs (3802), Grains Inspected for Export weekly (3071), National Grain & Oilseed Processor Feedstuff Report (3511). A "National Sunflower & Oilseed Weekly Summary" exists in ESMIS but its **latest release is Dec 6 2018** – treat as discontinued (S30).
- **Weekends/holidays:** the SD archive in ESMIS lists only business days (S20).

---

## 2. Access and API

### 2.1 Fetching without any key (observed 2026-10-27)

| What | URL pattern | Result |
|---|---|---|
| Latest PDF of a report | `https://www.ams.usda.gov/mnreports/ams_<ID>.pdf` e.g. `.../ams_3186.pdf` | **HTTP 200, `application/pdf`**, `Last-Modified: Mon, 26 Oct 2026 19:28:06 GMT` (= 2:28 pm Chicago) – S5. `Cache-Control: no-cache`. Always the *latest* only. |
| Keyless publication metadata (JSON or TXT) | `https://marsapi.ams.usda.gov/services/v3.1/public/listPublishedReports/{nbrOfDays\|all}?format=json` ; `.../public/listPublishedReport/{slug_id}?format=json` ; `.../public/listCorrectedReports` | **HTTP 200.** Documented as `"security":"Public"` at `https://marsapi.ams.usda.gov/services/help/more` (S11, S31). Returns `id, fileName, fileExtension, publishedDate, publishedDateMilliseconds, reportBeginDate, reportEndDate, reportTitle, correction, final`. **Metadata only – no prices.** Useful for "has today's report posted?" polling. |
| Keyless data API | `https://marsapi.ams.usda.gov/services/v1.2/reports/3186` | **HTTP 403** `{"errorCode":403,"message":"Access is denied"…}` (observed). Consistent with docs: "API requests without authentication will also fail" (S12). |
| Public Data page (CSV filter/download) | `https://mymarketnews.ams.usda.gov/public_data` | Exists per search snippet (S32); **could not open** the host, so I cannot say whether it needs login. FAQ says an account is needed for saved queries and >5,000 rows (S33). |
| Archive of past PDFs | MMN File Repository `https://mymarketnews.ams.usda.gov/filerepo/reports` (S18) and ESMIS `https://esmis.nal.usda.gov/publication/south-dakota-daily-grain-bids` (S20) | ESMIS list showed history through at least Sep 30 2025 (page may lag). Could not fetch MMN filerepo. |

**robots/terms check.** `https://www.ams.usda.gov/robots.txt` (observed) disallows only admin/search/user/core paths – **not `/mnreports/`** (S34). `https://mymarketnews.ams.usda.gov/robots.txt` and `marsapi…/robots.txt`: **could not be retrieved** (timeout / 404). Only one GET per report was made. USDA general policy: public information, attribution requested (S16). **No scraping of HTML pages was done**; only the published PDFs and the keyless JSON endpoint named in the API's own `/services/help` were requested.

### 2.2 The free API key (step for Ridge)

- **Base URL:** `https://marsapi.ams.usda.gov/services/v1.2/reports` (S12, S33). Older doc pages show `v1.1` (S19, S35); the API's own help lists `v3.1` for the public endpoints (S31). Which version is current for data calls: **not confirmed** – test `v1.2` first (the version in the official Authentication/FAQ pages).
- **Auth:** HTTPS Basic auth; **API key = username, empty password**: `curl -u YOUR_API_KEY: https://marsapi.ams.usda.gov/services/v1.2/reports/3186` (S12). Plain HTTP fails; "does not support open web browser calls" – so the app must call it **server-side** and never ship the key to the browser (S12).
- **How to get the key:** log in at My Market News → eAuthentication (eAuth) page → "Register" → email confirmation (a few hours) → log in → click your name → "Show API key" (S12). Free (S33). Key is personal and "must only be utilized by that user… do not share" (S12) – **a public app should proxy/cache; do not embed or share the key.** Whether a single key may back a public service: **not addressed in the docs I could read – ask mymarketnews@usda.gov** (Ridge's step; I contacted no one).
- **Free account benefits / limits:** unregistered 5,000 rows/request vs registered 100,000 (S33, S36). FAQ: "No" limit on number of queries in a time frame, only rows (S36). FAQ also says a no-registration sample key existed but "will be removed sometime in the future" (S36) – my keyless call was refused, so assume it's gone. A different USDA API (LMPR) warns it will temporarily block IPs doing high-frequency requests (S37) – prudent to follow the same etiquette (one pull/report/day).
- **Query syntax (from docs, search snippets only):**
  - List reports: `/reports`; one report: `/reports/<slug_id>` or `/reports/<slug_name>` e.g. `/reports/1095`, `/reports/MD_DA953` (S38).
  - All sections: `/reports/3186?q&allSections=true` (S19).
  - Filter: `/reports/3046/Report Detail?q=report_date=09/17/2024;commodity=Corn,Soybeans` (S39); date range `report_begin_date=06/06/2017:07/01/2017` (S40, S41).
  - A third-party-generated OpenAPI file (not USDA) lists `startDate`, `endDate` (max 180 days), `limit`, `offset`, `sort_by`, `sort_order` (S42) – **unverified, do not rely on it**; it is also livestock-oriented.
  - Output: JSON (and XLSX) (S43); no webhooks (S36).
- **Sample request URLs (to try after Ridge has a key; not executed by me):**
  - `curl -u $MARS_KEY: "https://marsapi.ams.usda.gov/services/v1.2/reports/3186?q&allSections=true"`
  - `curl -u $MARS_KEY: "https://marsapi.ams.usda.gov/services/v1.2/reports/2887?q=report_begin_date=10/01/2026:10/26/2026"`
  - Same pattern for 3878, 3225, 3049, 2850.
- **Response shape:** *could not be confirmed.* I could not obtain a real MARS JSON response for any grain report (key required; docs host unreachable). USDA says reports return "sections" selectable with `allSections=true` (S19, S40); a third-party schema lists livestock-style fields (`slug_id, slug_name, report_date, published_date, commodity, class, grade, region, price_unit…` – S42, S44) and **does not document grain basis/price-range fields**. → First task after getting a key: save one raw response per report and freeze the real field names.

### 2.3 Terms/licensing for reuse

- USDA website policy: "Most information… is considered public domain… freely distributed or copied, but use of appropriate byline… requested. 'U.S. Department of Agriculture.'" Some materials are copyrighted and labelled (S16).
- Market News Data Mart (mandatory-report site, **not MMN**) states: "no restrictions on who may obtain this data or how it may be used. However, if the data is published and identified as USDA data, it cannot be altered in any way" (S37/S45). This is the closest published USDA-AMS Market News reuse statement I found; it is for a different site, so apply by analogy only.
- Report disclaimer text: prices are voluntary reports; outliers may be excluded; reporters recertified every two years (S19).
- **Could not be found:** a MMN/MARS-API terms-of-use page; an explicit statement allowing a key to serve a public app.

---

## 3. Field dictionary (as printed in the PDFs; JSON names unconfirmed – see §2.2)

Header (every PDF): report title, "Grain Report for MM/DD/YYYY – Final", price-info line (Iowa adds "State Average Price: Corn -- $4.12 (-.43Z) Down 1 cent | Soybeans -- $11.70 (-.72X) Down 16 cents"), source/contact footer, link to the report page (S5–S10).

**Futures Settlements block** (identical in all):

| Field | Meaning | Unit |
|---|---|---|
| Exchange | `CBOT`, `KCBT`, `MGE` (label for the Minneapolis exchange; now operated as MIAX Futures – the label in the report is still "MGE") | – |
| Commodity | Corn, Soybeans, Wheat (CBOT = SRW), White Oats; KCBT Wheat (= KC HRW); MGE Wheat (= HRS) | – |
| Closing Settlement Price "as of" date | Settlement for that trade date | **cents per bushel** (e.g., 455.00 = $4.55) |
| (Month Year) | Contract delivery month; 7 listed per commodity (MGE: 6) | month code legend in report |

**Cash-bid table row** (one row per region × commodity × delivery):

| Column | Meaning | Unit / values seen |
|---|---|---|
| Commodity + grade heading | e.g., "US #2 Yellow Corn (Bulk)", "US #1 Soybeans (Bulk)", "US #1 Hard Red Spring Wheat (Bulk)", "US #1 Hard Red Winter Wheat (Bulk)". **Grade differs by state** (ND soybeans and corn are #2; SD/IA/NE/MN soybeans #1; ND HRS is "Milling") | text |
| Market-type subheading | "Country Elevators – Conventional", "Terminal Elevators", "Barge Loading Elevators", "Mills and Processors", "Terminals/Mills/Processors" | text |
| Region/Location | Sub-state region (SD/ND/NE/IA/MN) or city (2887) | text; **definitions not published** (see §6) |
| Sale Type | `Bid` (also `Nominal`, `Bid/Ask/Trade` in Minneapolis) | text |
| Protein | Wheat only: `14.0%` (HRS), `Ordinary` (HRW) | % |
| Basis | Range *low to high* with a **suffix letter = futures month the basis is against**; e.g., `-90.00Z to -80.00Z` | **cents/bu**; (sunflower/canola tables: `$/Cwt`, blank) |
| Basis Change | vs prior day: `UNCH`, `UP n`, `DN n`; may be a range `UNCH-DN 10.00` | cents/bu |
| Price | Low-high (or single) **cash price** | **$/bu** (sunflower: **$/cwt**) |
| Price Change | vs prior day, same range style | $/bu |
| Average | Simple average of reporters' prices for the row (report states "simple averages" – S19) | $/bu |
| Year Ago | Average a year earlier; **often blank** | $/bu |
| Freight | `DLVD-T` (delivered, truck; SD/NE/IA/MN) or `FOB-T` (ND) – ND is not directly comparable with SD | code table in report |
| Delivery | `Current`, or deferred month `Nov`, `Dec`, `May`, `Apr`…; Barge rows add "River Open" | text |

Month-code legend (printed in each report): F Jan, G Feb, H Mar, J Apr, K May, M Jun, N Jul, Q Aug, U Sep, V Oct, X Nov, Z Dec (S5). Freight codes: FOB, DLVD, CIF; T truck, R rail, B barge… (S5).

**Sunflower-specific (2887):** no basis columns populated; units **$/cwt**; delivered (`DLVD-T`) bids; many rows for the same processor × delivery month (Current, Nov, Dec, Jan, Feb, Mar) (S10).

---

## 4. Reading futures settlements and cash bids

**Formula:** cash price ($/bu) = [futures settlement (¢/bu) + basis (¢/bu)] / 100, using the futures month named by the basis suffix letter. **Basis sign:** negative = cash *below* futures ("under"); positive = above. The Minneapolis report shows a positive basis (+160 to +240 Z) because that quote is *delivered Chicago/beyond by rail* (S26).

**Checked examples from the 2026-10-26 reports** (futures from the block in S5):

| Crop | Report/region | Basis suffix → futures used | Arithmetic | Printed price |
|---|---|---|---|---|
| Corn | SD North Central | Z → CBOT Dec 26 = 455.00 | 455.00 − 90 = 365.00 → $3.65; 455.00 − 80 → $3.75 | 3.6500-3.7500 ✔ |
| Soybeans | SD North Central | X → CBOT Nov 26 = 1241.25 | 1241.25 − 80 = 1161.25 → $11.6125; −55 → $11.8625 | 11.6125-11.8625 ✔ |
| HRS | SD North Central, 14% | Z → **MGE** Dec 26 = 634.00 | 634 − 80 → $5.54; −70 → $5.64 | 5.5400-5.6400 ✔ |
| HRW | SD North Central | Z → **KCBT** Dec 26 = 659.00 | 659 − 90 → $5.69 | 5.6900 ✔ |
| Corn | NE Northwest | Z, **positive** basis | 455 + 40 → $4.95; 455 − 2 → $4.53 | 4.5300-4.9500 ✔ (S7) |
| Corn (deferred) | S. MN "South", May delivery | K → CBOT May 27 = 477.50 | 477.50 − 50 → $4.275; −35 → $4.425 | 4.2750-4.4250 ✔ (S8) |

(The inference that Z-suffixed wheat bases refer to MGE vs KCBT Dec by class is mine, confirmed only by this arithmetic; the report does not say so explicitly.)

**Which contract months matter** (contract months from exchange specs):
- **Corn (CBOT ZC):** Dec, Mar, May, Jul, Sep (S46). Fall cash bids reference **Dec**; winter/spring deferred bids reference Mar/May (S8 shows K).
- **Soybeans (CBOT ZS):** Nov, Jan, Mar, May, Jul, Aug, Sep (S46). Fall bids reference **Nov (X)**; deferred K (May).
- **Winter wheat (KC HRW, ticker KE):** Jul, Sep, Dec, Mar, May (S46). Report labels it KCBT.
- **SRW (CBOT ZW):** same months; Ridge's list has no SRW crop but the settlement block prints it (S46).
- **Spring wheat (Minneapolis HRS, MIAX Futures; ticker MWE):** Mar, May, Jul, Sep (new crop), Dec; 5,000 bu; $/bu quote; last trade day = business day before the 15th (S47).
- All CBOT/KC contracts: 5,000 bu; ZC/ZS/ZW/KE settle at **1:15 pm CT** (S46). USDA posts the report 1–2 hours *after* that (§1).
- **Sunflowers:** no liquid futures contract is listed in any source I opened; prices are posted bids in **$/cwt delivered** at processors (S10). Whether a *thin* sunflower contract exists: **could not be found/verified**. The app should present flat price only, with month-to-month "carry" via the Current/Nov/Dec/Jan… rows.

**Delivery periods:** `Current` = nearby/prompt delivery bid (basis typically against the nearby benchmark month shown by suffix); deferred rows name delivery month (S5, S8). "River Open" on barge rows = delivery after the Mississippi opens in spring (S25).

**Where free settlement data comes from:**
1. **The USDA reports themselves** (primary, free, already paired with the cash bids, same day) – S5.
2. CME delayed quotes page exists (`https://www.cmegroup.com/market-data/browse-data/delayed-quotes.html`, S48) and CME says delayed ≥10 minutes (S17/S48 summary), **but** CME's Data Terms of Use allow only personal, non-commercial viewing "in the form presented", and prohibit collecting, copying, compiling, redistributing, scraping or building databases without prior written authorization (S17). → **Do not scrape CME.** A CME Information License Agreement is required for display/non-display use of delayed data in an application (S49, search snippet).
3. MIAX (HRS) settlements: a free redistributable public source **could not be verified**; MIAX publishes contract specs (S47) and lists a daily settlement period (search snippet S50, not opened).
- **Caveat:** USDA's report shows *settlements* (end-of-day); there are no intraday/real-time quotes. Timestamp them "as of 10/26/2026 settlement".

---

## 5. Geography: which areas fall within ~300 miles of Gann Valley

**Method.** Origin: Gann Valley, SD ≈ **44.0335° N, 98.9884° W** (S51). Distance = **great-circle (haversine) straight-line miles**, Earth radius 3,958.8 mi, to approximate town/corner coordinates **that I supplied from general knowledge (not individually cited; verify against a gazetteer)**. Not road miles. USDA does **not** publish boundaries for "North Central/Northeast/…" regions in the documents I found (the LPGMN Regional Terms PDF, S52, defines barge, port and exchange regions but **not** these state sub-regions), so sub-regions are matched to towns by common-sense geography only.

Selected distances (miles): Burke SD 61 · Pierre 71 · Aberdeen 102 · Watertown 110 · Brookings 110 · Valentine NE 112 · Sioux Falls 117 · Beresford SD 129 · Sisseton 147 · Norfolk NE 159 · Marshall MN 161 · Sioux City IA 168 · Worthington MN 171 · Morris MN 185 · **Enderlin ND 192 · Jamestown ND 199** · Spencer IA 202 · Bismarck 211 · Rapid City 211 · Grand Island NE 218 · North Platte NE 219 · **West Fargo ND 221** · Fargo 224 · Omaha 247 · Mankato MN 248 · Council Bluffs IA 249 · Lincoln NE 251 · Dickinson ND 269 · Scottsbluff NE 280 · Grand Forks ND 285 · Minneapolis 289 · Velva ND 293 · Mason City IA 296 · **Out:** Ames IA 304 · Minot 310 · Jamestown KS 310 · Des Moines 320 · Rochester MN 324 · Hallock MN 341 · Akron CO 344 · Williston 361 · Miles City MT 372 · Dubuque IA 432.

State-extent corner checks: SD – all four corners 167–280 mi (**whole state inside**). NE – NE corner 154, NW 263, SW 332, SE 337 → **roughly the northern/central 70–80 % of NE inside; the far southern tier and SW panhandle outside**. ND – SE corner 177, SW 280 but NE/NW corners 354–419 → **southern ~half to two-thirds of ND**. MN – SW corner 132, far NW 381 → **southwest/west-central MN inside; the 3049 "South" report mostly covers this**. IA – NW corner 125, SW 288, NE 390, SE 462 → **western/northwest IA inside**.

| Report | Regions that fall inside 300 mi (rough) | Outside / uncertain |
|---|---|---|
| SD 3186 | All 5 (North Central, Northeast, Southeast, Central, East Central) | none |
| ND 3878 | South/east-central ND (Enderlin 192, Jamestown 199, Fargo 224, Bismarck 211). Likely **Central, East Central** and southern parts of North Central/Northeast/Northwest | Northern portions of Northwest/North Central/Northeast (Minot 310, Williston 361) – region boundaries unknown |
| NE 3225 | Northeast, East, Central, Northwest (Valentine 112, Norfolk 159, Grand Island 218, Alliance 237) | Parts of South/Southeast/Southwest (SE corner 337, SW 332) |
| MN 3049 | "South" (SW MN inside; Mankato 248; Rochester 324 borderline outside) | Eastern part of "South" |
| IA 2850 | Northwest, North Central, Southwest (Council Bluffs 249), parts of Northeast/South Central | Southeast, eastern Northeast |
| Sunflowers 2887 | Enderlin ND 192, West Fargo ND 221, Velva ND 293 | Hallock MN 341, all CO/KS rows |
| Terminals | Minneapolis 289 (reports 3046/3045 inside); Council Bluffs 249 | Kansas City (3223, FOB rail) outside; Mississippi River barge points (3043) outside |

---

## 6. Gaps and risks

1. **No individual elevator bids** in the current reports – only regional ranges/averages (S5–S9). The 2017-era per-town SD text report is gone from the current catalog and its URL redirects (S15, observed). **Elevator-level (within 300 mi) would require another source, which I was told not to contact.**
2. **Region definitions unpublished.** The 5-region SD scheme is visible, but I found no official county list (a search engine found only third-party county lists that do not establish USDA's definitions – S53). Regional Terms PDF lacks them (S52). The reports' "Trade Regions / Misc Info – click here" link points to that PDF (verified from the PDF's link annotations).
3. **Crop coverage holes.** Corn+soy: SD, ND, NE, S.MN, IA ✔. HRS: SD, ND only (+Minneapolis terminal 3046). HRW: SD, NE (+ KC 3223). No wheat in IA/S.MN reports. NE has no HRS. **No sunflowers outside 2887**, which on 10/26 had **no oil/confection rows and no SD point** – only 2 ND processors for High-Oleic; NuSun only in CO (Akron, 344 mi). Whether oil-type/confection rows appear seasonally: **not determinable from one day**.
4. **Comparability:** ND is FOB-T with US#2 grades; SD/NE/IA/MN are delivered-truck with US#1 soy; HRW "Ordinary" protein; sunflower in $/cwt.
5. **Lag / timing:** one daily final per business day, ~12:45–3:40 pm CT (S11); futures are settlements, not live; Mon–Fri only; holiday behavior not checked. "Final" flag exists; corrections list via `listCorrectedReports` (S31) – plan to re-pull.
6. **PDF-only without a key.** Layout is stable multi-column text; wrapped rows exist (e.g., barge region name on two lines, S25) and ranges like `UNCH-DN 10.00` (S7, S9). Parsing needs tests; prefer API JSON once keyed.
7. **API terms:** key is per-user and must not be shared (S12); API cannot be called from browsers (S12); the FAQ warns the unregistered sample key will be removed (S36); data migration to API is "one commodity at a time" over 2–3 years (S36, date of that FAQ unknown), so confirm 3186/3878/3225/3049/2850/2887 are on the API (the search-snippet pages show them with API URLs: S19 for 3186; others not individually confirmed).
8. **CME licensing risk** for re-displaying futures numbers lifted from USDA reports – USDA claims no restriction, exchange terms apply to exchange data (S16, S17). Unresolved; consider showing futures as "per USDA AMS report" with attribution, or ask USDA/CME.
9. **My Market News host unreachable from my box** – several doc pages (API Reports/Filtering/Examples, viewReport pages, public_data, robots) were only seen as search snippets. Re-verify on a normal browser.
10. **Report dates:** my release-time evidence is a single day. Re-collect.

---

## 7. Parsed samples (real, 2026-10-26 reports)

Parsed by a throwaway script (`data-scout/parse_ams.py`) from `pdftotext -layout` of S5 and S10. Raw strings kept (`basis_raw`, `price_raw`) so the future parser can split ranges. Unit reminders: basis in ¢/bu with trailing futures-month letter; prices $/bu (sunflower $/cwt). I did **not** get JSON from the API (key required).

```jsonc
// Futures block (S5): ¢/bu
[
 {
  "exchange": "CBOT",
  "commodity": "Corn",
  "price_cents_bu": 455.0,
  "contract": "Dec 26"
 },
 {
  "exchange": "CBOT",
  "commodity": "Soybeans",
  "price_cents_bu": 1241.25,
  "contract": "Nov 26"
 },
 {
  "exchange": "CBOT",
  "commodity": "Wheat",
  "price_cents_bu": 616.0,
  "contract": "Dec 26"
 },
 {
  "exchange": "KCBT",
  "commodity": "Wheat",
  "price_cents_bu": 659.0,
  "contract": "Dec 26"
 },
 {
  "exchange": "MGE",
  "commodity": "Wheat",
  "price_cents_bu": 634.0,
  "contract": "Dec 26"
 }
]
```

**Corn** – SD 3186 (S5)
```json
{
  "slug": "3186",
  "report_date": "10/26/2026",
  "commodity": "US #2 Yellow Corn",
  "region": "North Central",
  "sale_type": "Bid",
  "protein": null,
  "basis_raw": "-90.00Z to -80.00Z",
  "basis_change_raw": "UNCH",
  "price_raw": "3.6500-3.7500",
  "price_change_raw": "DN 0.0100",
  "avg_price": 3.7029,
  "year_ago_avg": 3.5589,
  "freight": "DLVD-T",
  "delivery": "Current"
}
```
**Soybeans** – SD 3186
```json
{
  "slug": "3186",
  "report_date": "10/26/2026",
  "commodity": "US #1 Soybeans",
  "region": "North Central",
  "sale_type": "Bid",
  "protein": null,
  "basis_raw": "-80.00X to -55.00X",
  "basis_change_raw": "UNCH",
  "price_raw": "11.6125-11.8625",
  "price_change_raw": "DN 0.1525",
  "avg_price": 11.7292,
  "year_ago_avg": null,
  "freight": "DLVD-T",
  "delivery": "Current"
}
```
**Spring wheat (HRS)** – SD 3186
```json
{
  "slug": "3186",
  "report_date": "10/26/2026",
  "commodity": "US #1 Hard Red Spring Wheat",
  "region": "North Central",
  "sale_type": "Bid",
  "protein": "14.0%",
  "basis_raw": "-80.00Z to -70.00Z",
  "basis_change_raw": "UNCH",
  "price_raw": "5.5400-5.6400",
  "price_change_raw": "DN 0.0750",
  "avg_price": 5.57,
  "year_ago_avg": 4.8125,
  "freight": "DLVD-T",
  "delivery": "Current"
}
```
**Winter wheat (HRW)** – SD 3186
```json
{
  "slug": "3186",
  "report_date": "10/26/2026",
  "commodity": "US #1 Hard Red Winter Wheat",
  "region": "North Central",
  "sale_type": "Bid",
  "protein": "Ordinary",
  "basis_raw": "-90.00Z",
  "basis_change_raw": "UNCH",
  "price_raw": "5.6900",
  "price_change_raw": "DN 0.0550",
  "avg_price": 5.69,
  "year_ago_avg": 4.1925,
  "freight": "DLVD-T",
  "delivery": "Current"
}
```
**Sunflowers (High-Oleic)** – 2887, Enderlin ND (S10); two of its rows (Current and Dec delivery):
```json
{
  "slug": 2887,
  "report_date": "10/26/2026",
  "commodity": "US #1 High Oleics Sunflower Seeds",
  "location": "Enderlin, ND",
  "sale_type": "Bid",
  "basis": null,
  "price_usd_cwt": 25.9,
  "price_change": "DN 0.35",
  "avg_usd_cwt": 25.9,
  "year_ago_usd_cwt": 21.0,
  "freight": "DLVD-T",
  "delivery": "Current"
},
{
  "slug": 2887,
  "report_date": "10/26/2026",
  "commodity": "US #1 High Oleics Sunflower Seeds",
  "location": "Enderlin, ND",
  "sale_type": "Bid",
  "basis": null,
  "price_usd_cwt": 26.25,
  "price_change": "UNCH",
  "avg_usd_cwt": 26.25,
  "year_ago_usd_cwt": 21.15,
  "freight": "DLVD-T",
  "delivery": "Dec"
}
```
Note: the SD sample's `avg_price` for soybeans has no year-ago value because the PDF prints none for that row.

---

## 8. Recommended minimal data map

| App feature | Source report(s) | Fields | Refresh |
|---|---|---|---|
| "Today's cash bids" per state region – corn, soy | 3186 (SD, home state), 3878 (ND), 3225 (NE), 3049 (S.MN), 2850 (IA) | region, commodity, grade, basis_low/high, basis_month, price_low/high, avg, delivery, freight, report_date | Poll the keyless `listPublishedReport/<id>?format=json` (S31) every ~15 min from 12:30–4:00 pm CT, Mon–Fri; fetch data when `publishedDate` changes; re-pull on `correction=true` |
| Wheat – spring | 3186 + 3878 (+3046/3045 Minneapolis for terminal reference) | protein, basis (vs MGE Dec etc.), price range, avg | same |
| Wheat – winter | 3186 + 3225 (+3223 KC) | protein "Ordinary", basis vs KC | same |
| Sunflower prices | 2887 | commodity (High-Oleic, NuSun), location (Enderlin, West Fargo, Velva?), delivery month, $/cwt, change, year-ago | same, with "no oil/confection or SD bid today" empty-state |
| Futures settlement strip | Header block of any of the reports (use 3186) | exchange, commodity, month, ¢/bu, as-of date | daily with report; label "settlement as of …" |
| Basis & "price vs last year" | Same rows | basis range, avg vs year_ago | daily |
| Basis history charts | Own archive of daily pulls (and API history `report_begin_date` ranges, S40, once keyed; ESMIS PDFs for SD back to 2025, S20) | basis_mid by region/crop/month | nightly append |
| Delivery-period carry (spread across months) | 3049 (S.MN current vs May), 2887 (sunflower months), 3043 (barge) | delivery, price | daily |
| Map / "within 300 mi" filter | Static table from §5 (region → in/out) | region name only | review each season |
| Attribution footer | – | "Source: USDA AMS Livestock, Poultry & Grain Market News, report <id>, <date>, <time>" + link to viewReport/<id> | static |

**Build order suggestion (not building anything now):** (1) keyless PDF + listPublished poller with parser tests → ship; (2) Ridge registers for key → swap to JSON; (3) resolve CME/USDA futures-reuse question; (4) ask USDA for region definitions & MMN terms.

**Actions that only Ridge can take (none done by me):** register for My Market News/eAuth and copy the API key; email mymarketnews@usda.gov (address printed in every report) about terms for a public app, the region definitions, JSON field list and sunflower coverage.

---

## Source list

- **S5** SD Daily Grain Bids PDF (fetched 2026-10-27; includes futures block): https://www.ams.usda.gov/mnreports/ams_3186.pdf
- **S6** ND Daily Grain Bids PDF: https://www.ams.usda.gov/mnreports/ams_3878.pdf
- **S7** NE Daily Elevator Grain Bids PDF: https://www.ams.usda.gov/mnreports/ams_3225.pdf
- **S8** Southern MN Daily Grain Bids PDF: https://www.ams.usda.gov/mnreports/ams_3049.pdf
- **S9** Iowa Daily Cash Grain Bids PDF: https://www.ams.usda.gov/mnreports/ams_2850.pdf
- **S10** National Daily Sunflower, Canola, Millet, Flaxseed PDF: https://www.ams.usda.gov/mnreports/ams_2887.pdf
- **S11** Keyless MARS public published-reports listing (observed; times converted MDT→Chicago): https://marsapi.ams.usda.gov/services/v1/public/listPublishedReports/all and https://marsapi.ams.usda.gov/services/v3.1/public/listPublishedReports/7?format=json
- **S12** MMN API Authentication (search snippet): https://mymarketnews.ams.usda.gov/mymarketnews-api/authentication
- **S13** MMN API Technical Instructions (JSON/XLSX; search snippet): https://mymarketnews.ams.usda.gov/mars-api/getting-started/technical-instructions
- **S14** USDA State Grain Reports index (observed): https://www.ams.usda.gov/market-news/state-grain-reports
- **S15** Archived Sioux Falls closing-bids text report (2017): https://mymarketnews.ams.usda.gov/filerepo/sites/default/files/3186/2017-10-23/788077/SF_GR11020171023.TXT ; current legacy URL (302): https://www.ams.usda.gov/mnreports/SF_GR110.txt
- **S16** USDA Policies and Links (public domain/attribution; fetched): https://www.usda.gov/about-usda/policies-and-links
- **S17** CME Data Terms of Use (fetched): https://www.cmegroup.com/trading/market-data-explanation-disclaimer.html
- **S18** MMN File Repository listing (search snippet): https://mymarketnews.ams.usda.gov/filerepo/reports
- **S19** SD report page (slug, description, API URL; search snippet): https://mymarketnews.ams.usda.gov/viewReport/3186
- **S20** ESMIS SD Daily Grain Bids archive: https://esmis.nal.usda.gov/publication/south-dakota-daily-grain-bids
- **S21** ND report page (search snippet): https://mymarketnews.ams.usda.gov/viewReport/3878
- **S22** S. MN report page (search snippet): https://mymarketnews.ams.usda.gov/viewReport/3049
- **S23** Iowa report page (search snippet): https://mymarketnews.ams.usda.gov/viewReport/2850
- **S24** Sunflower report page (search snippet): https://mymarketnews.ams.usda.gov/viewReport/2887 (index entries in S14)
- **S25** Iowa–S. MN Barge Terminal PDF: https://www.ams.usda.gov/mnreports/ams_3043.pdf
- **S26** Minneapolis Daily Grain Report PDF: https://www.ams.usda.gov/mnreports/ams_3046.pdf
- **S27** Minneapolis Basis / MIAX floor summary PDF: https://www.ams.usda.gov/mnreports/ams_3045.pdf
- **S28** Kansas City Daily Wheat Bids PDF: https://www.ams.usda.gov/mnreports/ams_3223.pdf
- **S29** Montana Daily Elevator Grain Bids PDF: https://www.ams.usda.gov/mnreports/ams_2771.pdf
- **S30** ESMIS National Sunflower & Oilseed Weekly Summary (last release Dec 6 2018): https://esmis.nal.usda.gov/publication/national-sunflower-oilseed-weekly-summary
- **S31** MARS API self-documenting help (public endpoints; observed): https://marsapi.ams.usda.gov/services/help and https://marsapi.ams.usda.gov/services/help/more
- **S32** MMN Public Data page (search snippet): https://mymarketnews.ams.usda.gov/public_data
- **S33** MMN account benefits (5,000 vs 100,000 rows; search snippet): https://mymarketnews.ams.usda.gov/faqs/what-my-market-news-account-and-what-are-benefits
- **S34** AMS robots.txt (observed): https://www.ams.usda.gov/robots.txt
- **S35** MMN Basic Instructions (v1.1 endpoint; search snippet): https://mymarketnews.ams.usda.gov/mars-api/getting-started/basic-instructions
- **S36** MMN API FAQs (search snippet): https://mymarketnews.ams.usda.gov/mymarketnews-api/faqs
- **S37** LMPR API User Guide (keyless LMPR API; abuse blocking): https://mpr.datamart.ams.usda.gov/LMPRS-API-User-Guide.pdf
- **S38** MMN API Reports page (search snippet): https://mymarketnews.ams.usda.gov/mymarketnews-api/reports
- **S39** MMN API Filtering page (search snippet): https://mymarketnews.ams.usda.gov/mymarketnews-api/filtering
- **S40** MMN API Examples page (search snippet): https://mymarketnews.ams.usda.gov/mymarketnews-api/examples
- **S41** MMN API landing page (search snippet): https://mymarketnews.ams.usda.gov/mymarketnews-api
- **S42** Third-party generated (not USDA) OpenAPI: https://raw.githubusercontent.com/api-evangelist/agricultural-marketing-service/refs/heads/main/openapi/agricultural-marketing-service-reports-api-openapi.yml
- **S43** *(same as S13)*
- **S44** Third-party schema summary (not USDA): https://apis.io/json-structure/agricultural-marketing-service/mars-api-report-data-structure/
- **S45** Market News Data Mart statement on use: https://mpr.datamart.ams.usda.gov/
- **S46** CME Grain and Oilseed Fact Card (contract months, 1:15 pm CT settlement; fetched): https://www.cmegroup.com/trading/agricultural/files/AC-268_Grains_FC_FINAL_SR.pdf
- **S47** MIAX HRSW contract specs (fetched): https://www.miaxglobal.com/miax_futures_hrsw_futures_contract_specifications.pdf
- **S48** CME Delayed Quotes: https://www.cmegroup.com/market-data/browse-data/delayed-quotes.html
- **S49** CME Information License Agreement (search snippet): https://www.cmegroup.com/market-data/files/information-license-agreement-june-2026.pdf
- **S50** MIAX daily settlement periods (search snippet, not opened): https://www.miaxglobal.com/miax_futures_onyx_daily_settlement_periods_and_configurations.pdf
- **S51** Gann Valley coordinates: https://geo.mytopo.com/feature/south-dakota/buffalo/census/2584554/gann-valley-census-designated-place/ and https://topoquest.com/place/south-dakota/census/gann-valley-census-designated-place/2584554
- **S52** LPGMN Regional Terminology (fetched): https://www.ams.usda.gov/sites/default/files/media/2020RegionalTerms.pdf
- **S53** Third-party county lists (not authoritative): https://qa.morningagclips.com/cash-basis/
