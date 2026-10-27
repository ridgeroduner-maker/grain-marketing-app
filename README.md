# Grain Marketing App (working title)

Public app for farmers (phone + computer, PWA) showing futures and elevator cash bids/basis within 300 miles of Gann Valley, SD.

## Decisions so far (Ridge, Oct 27, 2026)
- Public app, free tools only.
- Crops: corn, spring wheat, winter wheat, soybeans, sunflowers.
- Features: map, best bid near me, price alerts, history charts. No profit calculator.
- Futures: end-of-day settlements only (from USDA reports). No paid CME data at launch.
- Prices: USDA AMS Market News regional data only at launch. No contact or permission requests to elevators.
- Sunflowers: thin coverage is OK (no futures exist; cash bids only).
- Nothing is published, sent, or paid for without Ridge typing APPROVE.

## Team
- BOBBY (Chief) coordinates.
- Data Scout: USDA data spec (in progress).
- Builder: app build with Grok on Ridge's laptop (Grok 1.0.52, Node, Python, Git 2.56 installed).
- Reviewer: checks numbers, staleness, licensing/attribution.

## Research summary (public sources, Oct 27, 2026)
- USDA AMS Market News: SD 3186, ND 3878, NE 3225, S. MN 3049, sunflowers 2887, Iowa 2850 (unverified). Free API needs a free key. Public domain; credit advised.
- CME/Barchart/Alpha Vantage/Yahoo/Stooq: not safe for a public app without paid licenses.
- Starter elevators (link-out only, not copied): Agtegra, CHS Farmers Alliance (Mitchell), Ringneck Energy (Onida), Glacial Lakes Energy, POET plants, others.
- Free stack: haversine for the 300-mile radius, Leaflet or MapLibre, Chart.js, Cloudflare Pages or Vercel, Supabase or Cloudflare D1, web push.

## Next steps
1. Data Scout finishes the USDA data spec.
2. Ridge gets a free USDA API key (his account).
3. Builder scaffolds the app with Grok, saves to this repo.
4. Reviewer checks. Ridge approves before anything goes public.
