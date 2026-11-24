# Grain Marketing App (planning stage)

A free iPhone-first app for farmers near Kimball, SD. It covers elevators within 300 miles and uses USDA AMS regional prices plus links to each elevator's own bid page.

- Research Page: https://cursor.com/canvas/store-5c51f807-ebfb-435c-93d2-bcff0eee7873/7d2e3284-ef60-4cd5-9b4d-914bc78cf128
- Build plan Page: https://cursor.com/canvas/store-5c51f807-ebfb-435c-93d2-bcff0eee7873/9204af4b-44e1-466c-a7d6-946b60e05044
- [AUDIT.md](AUDIT.md) — research and plan audit (November 10, 2026)
- [ENHANCEMENTS.md](ENHANCEMENTS.md) — prioritized next steps, tied to milestones M0–M7

Elevator lists: original `research/grain_elevators.csv` (899 rows, unchanged) and cleaned working copy `research/grain_elevators_cleaned.csv` (875 rows; see the audit for what changed).

## Decisions so far (2026-10-27)
- For farmers around Kimball, and free
- Crops: corn, soybeans, spring wheat, winter wheat, sunflowers, oats
- Features: today's prices, price alerts, elevators ranked by net price after trucking, bid history charts
- Prices come from USDA AMS MyMarketNews regional reports, and each elevator links to its own bid page. No Barchart or DTN scraping.
- iPhone first. Distances are always measured from Kimball. Trucking uses a sourced default that farmers can change.
- Ranking uses the middle of each price range. KS and CO use their own USDA reports (AMS_2886 and AMS_2912). The closest elevators get verified first. Futures come later, after a license or legal review.

## USDA report IDs
SD AMS_3186, ND AMS_3878, NE AMS_3225, IA AMS_2850, S MN AMS_3049, IA-S MN barge AMS_3043, KS AMS_2886, CO AMS_2912, Sunflowers AMS_2887

All nine public PDFs were re-checked on November 10, 2026 and match those titles and areas. Details and gaps are in [AUDIT.md](AUDIT.md).

## Planned stack
Expo/React Native, Supabase free tier, Expo push, OpenRouteService

## Plan update (App Builder, 2026-10-27)
- Each USDA report is used for its own state, so KS and CO use their own reports instead of the nearest state's.
- Ranking and alerts use the flat cash midpoint. History saves the flat midpoint plus basis where the report prints it.
- Trucking default, which farmers can change, is $4.05 per loaded mile and 1,000 bu per load. It comes from the Iowa State 2026 Custom Rate Survey (A3-10). The 1,000 bu per load figure is unverified.
- Coverage gaps: oats only in SD, spring wheat only in SD/ND, winter wheat in SD/NE/KS/CO, and sunflowers quoted by town. Where no report covers an elevator, no price is shown.
- Before M0 can start, Graden has to APPROVE installing Git on the laptop and creating free Supabase, Expo, and OpenRouteService accounts. Apple's $99 isn't needed for M0 because Expo Go works for testing.

## Status note (2026-11-10)
Git is installed on the laptop. The free Supabase, Expo, and OpenRouteService accounts are still outstanding. This repo has been audited and committed locally; it has not been pushed to GitHub or Origin yet.
