# Enhancement plan — Grain Marketing App

Tied to milestones M0–M7 (and the already-planned M8 verify-closest pass). Free tools only. Items that need Graden’s approval are marked **Needs approval**.

This plan assumes the decisions already on the build-plan Page: USDA regional prices plus a link to each elevator’s own bid page, distances always from Kimball, rank by midpoint minus trucking, no futures in v1, no Barchart/DTN scraping.

---

## Do first (unblocks accurate M2–M6)

### E1. Farmer-facing bid links — M2 seed data, M6 screens
**Why:** 205 “bid pages” are APIs. A Bushel sample returned 404; DTN returned 403. The “View bid” button would fail for CHS, Farmers Pride, Landus, POET/ADM Gradable API rows, and others.

**What to do (free):**

- When importing the cleaned CSV, if `bid_url` is an API and `website` is already a cash-bids page (all 70 Bushel/CHS rows have one), use the website as the in-app link and keep the API URL only as a private note, never shown and never fetched by the app.
- For Gradable, prefer the existing `/market/...` website already in the CSV over the `/api/...` URL.
- For homepage-only links and the Farmers Cooperative Society 404, leave the link labeled unverified until a human finds the real board (M8).
- Add a one-line in-app notice when a link is unverified. The later “report a bad link” feature can stay post-MVP, but M6 should not send people to raw API URLs.

**Approval:** none, as long as we only reuse URLs already in the data.

### E2. Import the cleaned list, then verify collisions — M2, M8
**Why:** 24 AgMark duplicates are already merged. Four same-pin pairs (Holdrege, Holyoke, Earlham, Chappell) and many town-level shared pins will otherwise show up as duplicate cards.

**What to do:**

- Seed `elevators` from `research/grain_elevators_cleaned.csv`, not the raw file. Keep `origin_source`, `audit_flags`, and alternate URLs.
- Do not auto-delete the four same-pin pairs or the 18 `z` / `.OLD` operators. Mark them unverified.
- **Needs approval (M8, already in the plan):** who walks the closest ring (Graden, Grain Scout, or both), and whether 60 road miles is the right first ring. Liberty Grain in Kimball should be first, because it has no pin and no bid page.

### E3. Correct USDA region mapping, including gaps — M1, M2, M4
**Why:** Applying AMS_3049 (Southern Minnesota only) to Fergus Falls or the Red River Valley would show the wrong price. ND is FOB-T; the other planned reports are DLVD-T. Oats in SD are not statewide.

**What to do:**

- In M1, record freight basis (FOB vs delivered), delivery period, protein, and units (`$/bu` vs `$/cwt`) on each parsed row.
- Map elevators to USDA *regions*, not just states. If a Minnesota location is not clearly in the Southern Minnesota report area, show “not covered” rather than the South range. Do not use AMS_3045 (MIAX futures floor). AMS_3046 is Minneapolis *terminal* bids only; use it only if an elevator is actually a Minneapolis-area terminal, and label it that way.
- Show the already-planned “not covered” label for oats outside the SD regions that actually print oats, spring wheat outside SD/ND, winter wheat outside SD/NE/KS/CO, and sunflowers with no AMS_2887 town match.
- For AMS_2887, match by town name (Enderlin, West Fargo, and others as they appear). ADM Enderlin is in the list but disabled and tagged canola only — review during M8. Store sunflower prices in $/cwt, as planned.
- **Needs approval:** should the app say plainly that oats are only in parts of South Dakota, and that spring wheat is only in SD and ND? (This is already an open question on the plan Page; the audit supports answering yes.)

### E4. Honest net-price math — M6
**Why:** A single $0.00405/bu/mile rate, taken from the Iowa 100-mile custom average, undercharges a short haul. ND FOB prices are not the same kind of number as delivered prices elsewhere. Midpoint minus trucking is an estimate, not a bid.

**What to do (still free, still farmer-editable):**

- Keep $4.05/loaded mile and 1,000 bu as the *starting* default, with the A3-10 source and the “1,000 bu unverified” note on the About screen.
- Optionally offer a simple two-point default that uses the same survey’s 25-mile and 100-mile averages, so short hauls cost more per mile. Do not invent a South Dakota rate.
- Do not mix FOB and delivered midpoints in one ranked list without a label. Either rank within comparable freight terms, or show a “FOB vs delivered” tag on ND rows.
- Keep the planned disclaimer on the ranking screen, first-run screen, and every alert.
- **Needs approval:** is $4.05 and 1,000 bu the right default for the Kimball area, or does Graden want different numbers?

---

## During build (M0–M7)

### E5. Accounts, keep-alive, and adapters — M0, M4
- **Needs approval (still outstanding):** Graden creates the free Supabase, Expo, and OpenRouteService accounts himself. USDA MyMarketNews is optional because of the PDF fallback. Apple’s $99 waits until after Expo Go.
- In M4, make the weekday ingest job also touch the project (or document a manual mid-winter check-in) so the Supabase free tier is less likely to pause after a week idle. This was not re-verified against current Supabase rules; test it on the free project once it exists.
- PDF and API adapters must ignore the futures settlement table on every AMS report. Parse cash ranges only. Watch the 2-second Edge Function CPU limit; one report per call is still the safe approach.
- AMS_3226 has no PDF (merged into 2850 in 2020). Do not add a 3226 fetcher.

### E6. Routing batch and the 300-mile cut — M3
- Replace straight-line `miles` with OpenRouteService road miles and drive time from Kimball, in chunks, on the HeiGIT host.
- Drop anything over 300 *road* miles. Expect some of the 899 (875 cleaned) to fall out, including likely VERBIO Nevada, IA (already 300.15 miles straight-line).
- Liberty Grain cannot be routed until it has coordinates.

### E7. In-app coverage and history — M5–M7
- First-run and Prices screens should list which crops have gaps, not only a generic “not covered” on a row.
- History charts: flat midpoint as the main line; USDA-printed basis only as a second view, never combined with a futures quote.
- Alerts stay on flat midpoint vs a farmer-set target, at most once per day, as planned.
- Use Expo push on the free tier.

---

## Later (after M7, still free unless noted)

- M8 human verification, closest first, including Liberty Grain and the flagged collisions.
- Map view and “report a bad link.”
- Optional: call nearby elevators for bid-page URLs and crops. **Needs approval before any call.**
- Futures only with a source the app is allowed to show, plus legal review. Not in v1.
- App Store / TestFlight: **Needs approval** of the $99 Apple Developer Program. Android / Play Store ($25) after iPhone.
- GitHub or Origin private backup of this repo: **Needs approval** and a GitHub sign-in. The audit commit stays local until then.

---

## Suggested order once M0 is unblocked

1. M1 report spike, including freight terms and the Minnesota gap check (E3).
2. M2 database + import cleaned CSV + store farmer-facing links (E1, E2).
3. M3 road distances (E6).
4. M4 ingest with futures tables stripped and a pause-avoidance check (E5).
5. M5–M6 app shell, ranking, disclaimers, FOB/delivered labels (E4, E7).
6. M7 alerts and history (E7).
7. M8 verify closest, after Graden picks who does it (E2).
