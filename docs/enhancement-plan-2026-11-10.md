# Grain Bids app: enhancement plan, 2026-11-10

Written by BOBBY (Chief) for Ridge Roduner, from `docs/audit-2026-11-10.md` (finding IDs F-xx refer to it). **Plan only: nothing here is built, merged or published.** Every item must stay free: GitHub Pages, public repo, free GitHub Actions, free Protomaps map, USDA public data, no paid service and no card.

Effort is in builder hours (my estimates, not measured) and assumes the existing test suite and a Reviewer pass. "Ridge" marks anything only he can do. Anything that publishes needs Ridge's typed APPROVE, as before.

## Priority 0: do first (no new features)

| # | Item | Why | Effort | Needs from Ridge |
|---|---|---|---|---|
| P0-1 | **Merge PR #2** (date parser fix) and confirm the publish run and the live data date | Fixes F-01: site is 11 days stale | 0.5 h (merge, watch run, verify live) | Typed APPROVE |
| P0-2 | After the merge, **re-run the publish once with `workflow_dispatch`** if the first run is skipped or fails, and check the row-count guard (baseline 66 rows, new 67) | Confirms the fix end to end; the first run after an 11-day gap is the riskiest | 0.5 h | none |
| P0-3 | **Decide on the two reminder automations** (pause or keep) | They have been repeating the same ask | 0.1 h | Yes/no |

## Priority 1: make the daily refresh hard to break (the lesson of this outage)

| # | Item | Fixes | Effort | Free? |
|---|---|---|---|---|
| P1-1 | **Failure alert**: when the scheduled run fails, have the workflow open (or update) one GitHub issue titled "Daily refresh failing" with the failing report numbers, and close it on the next success. Ridge gets GitHub's normal issue email. Needs `issues: write` on one small job only. | F-05 | 2 to 3 h | Yes |
| P1-2 | **Per-report fail-soft ingest**: if one report fails to parse, still publish the other reports; keep the failed report's last good rows and let the existing per-report staleness banner flag them (`app.js:88-91` already does this). Keep the hard stop for "all reports failed" and for the 70% row guard. | F-04 | 6 to 8 h incl. tests | Yes |
| P1-3 | **Hide rows older than the 7-day limit in the browser** (read `meta.stale_expire_days`; drop from table, map and Best tab; show one line "N older bids hidden"). Then the rule holds even when the export did not run. | F-02 | 2 to 3 h | Yes |
| P1-4 | **Run tests on pull requests** (`pull_request` trigger running only the test step; no deploy, no secrets). | F-09 | 1 h | Yes |
| P1-5 | **Parser hardening**: make the "Price Change" cell optional in `ROW_TAIL`; count every "Bid" line under an in-scope heading and fail loudly if the parser saw more than it kept; skip `Offer`/`Trade` rows explicitly. Add fixtures from today's reports (including the blank-change example from report 2887). | F-08, F-20 | 3 to 4 h | Yes |
| P1-6 | **Stable location ids**: key alerts and history on `state + name + section` (a slug), not the SQLite id, with a one-time migration of saved alerts in the browser. | F-07 | 3 to 4 h | Yes |
| P1-7 | **Fix "today" to Central in the export** and relabel "Nd old" as "N business days old". | F-11, F-15 | 1 h | Yes |

Order: P1-1 and P1-3 first (small, immediately reduce risk), then P1-5, P1-2, P1-4, P1-6, P1-7. Subtotal about 18 to 24 h.

## Priority 2: pending items Ridge already knows about

| # | Item | Status | Effort | Needs from Ridge |
|---|---|---|---|---|
| P2-1 | **USDA MARS API key + history backfill.** Free key from the AMS site (steps are in the README, "What Ridge must do to get the (free) API key"; put it in `.env` locally, and as a GitHub Actions secret only if the daily job should use it; never commit it). Then run `--source mars --backfill-days 14` to recover Nov 2 to Nov 6 (F-06) and test the never-run MARS code (F-19). | Key not obtained | 3 to 5 h after the key exists (write the missing `test_mars_normalize.py`, run a live backfill, review) | Create the account and key (about 10 minutes) |
| P2-2 | **Legal review of Terms and Privacy** (F-03). Open questions are the `[[LAWYER]]` / `[[OWNER TO CONFIRM]]` notes: CME permission for futures dollars, acceptable-use wording, liability cap, venue, GitHub log visibility, children's privacy. A free fallback while waiting: set `FUTURES_DISPLAY: 'basis_only'` (already supported) to remove the CME-sensitive piece. | Drafts live with placeholders | 1 to 2 h builder to apply the lawyer's edits and remove the DRAFT banner; lawyer cost unknown (Ridge has said no budget, so a legal-aid or bar-association clinic is the free route; I have not contacted anyone) | Decision and the review itself |
| P2-3 | **WY and MT.** Today the app ingests SD, ND, NE, S. MN, IA and sunflowers. The USDA Wyoming report (3239) and Montana report (2771) are regions, not towns. Wyoming "Southeast" sits about 330 mi from Gann Valley, inside the 350 mi margin, so adding 3239 would show it in the existing "just outside your radius" list. No WY or MT elevator name list was found (WY Dept of Ag has no public list; the MT licence page's list link could not be extracted), so the Directory layer stays at 0 WY/MT rows unless Ridge finds one. | Researched, not built | 2 to 3 h for adding report 3239 and 2771 as margin-only reports with tests; directory rows: blocked on a source | Optional: a source for WY/MT licensed-buyer lists |
| P2-4 | **Opt-in elevator bid submission pilot**, per `/workspace/optin-bids-plan.md`: Ridge-relay first (Option G, manual, weeks 1 to 2), then GitHub issue form + validating Action + allowlist keyed to GitHub user id (Option A), Cloudflare Worker (Option C) only if elevators will not use GitHub. Bids carry the app's staleness rules and a "not USDA, elevator-posted" label. | Plan delivered; Ridge has not decided | MVP 16 to 24 h builder, review 3 to 4 h, pilot 8 to 12 h of Ridge's time over 4 weeks, public launch 2 to 4 h; Option C adds 10 to 14 h | Go/no-go; lawyer questions in the plan's section 6.5; GitHub Pages "commercial transactions" clause check |
| P2-5 | **Directory refresh process**: a documented, repeatable command and a calendar reminder to rebuild from the state lists (SD, ND, NE, IA, MN) every quarter; show the list date per state (already shown). Keep AgState and Gossel/Kimball Grain dropped, as Ridge approved on Oct 28. | Lists dated Sep 29 to Oct 28 | 2 h | Quarterly reminder only |

## Priority 3: quality, security and polish

| # | Item | Fixes | Effort |
|---|---|---|---|
| P3-1 | **Add a CSP meta tag** using the README's policy (no `frame-ancestors`), test every tab (History and Alerts were never run under it). | F-12 | 2 h |
| P3-2 | **Turn on free GitHub protections** (Ridge's call, I changed nothing): secret scanning + push protection, Dependabot security updates, and a branch rule on `main` that requires the test check from P1-4. | F-13 | 0.5 h (Ridge clicks) |
| P3-3 | **Accessibility pass**: raise contrast on the primary and install buttons (darker green), directory muted text; add a data table or `aria-label` for the history chart; give each alert Delete button a unique name; add a skip link; test with VoiceOver or NVDA. | F-17 | 3 to 4 h |
| P3-4 | **Alert state sync**: one source of truth for `lastFiredDate` between the page and the service worker. | F-14 | 1 to 2 h |
| P3-5 | **Holiday awareness**: a small list of US federal holidays so the business-day count and the 5-day CI gate do not misfire (also loosen the gate for code-only deploys). | F-16 | 2 to 3 h |
| P3-6 | **Housekeeping**: update the stale workflow header and README lines, delete the duplicate `docs/pages.yml.txt` copy (or keep it generated), remove merged or dead branches `build/v1` and `fix/single-digit-report-date` (Ridge to say yes before anything is deleted), and write the missing MARS tests. | F-18, F-19, I-3 | 1 to 2 h |
| P3-7 | **Single shared date/format module** for `app.js` and `alerts-core.js`, with tests on both. | I-5, I-6 | 1 to 2 h |
| P3-8 | **Cron timing**: keep both crons but also add a third early-morning run, or accept the lag. Optionally use GitHub's `timezone: "America/Chicago"` schedule key noted in the workflow comment. | F-10 | 0.5 h |
| P3-9 | **Keep-alive for the 60-day schedule rule** (a monthly no-op commit or a reminder), only if the repo goes quiet. | F-21 | 0.5 h |

## Priority 4: new features for farmers (all free, all USDA-sourced)

Pick after P0 to P2; listed best value first.

| # | Feature | Notes | Effort |
|---|---|---|---|
| P4-1 | **Basis view and "basis vs 30-day average"**, using the history that is already collected | Farmers watch basis more than flat price; needs about 30 days of history (or the backfill in P2-1) | 6 to 8 h |
| P4-2 | **Share / print a single bid** (text snippet and a print stylesheet) | No server; builds on existing card | 2 to 3 h |
| P4-3 | **Shorter first screen on phones** (Best bid first, collapse the long notices behind a "How to read this" link, keep the confirm-with-elevator note visible) | The first screen is text-heavy on a 390 px phone | 4 to 6 h |
| P4-4 | **Offline map tiles for the 300-mile area** (cache the 17 MB `plains.pmtiles` in the service worker with range-request handling, only after the user chooses "save map") | Today offline shows the plain map | 6 to 8 h; test on a real phone |
| P4-5 | **Weekly trend sparkline** on each Best-bid card | Uses history.json | 3 to 4 h |
| P4-6 | **Push-style alerts without a server**: stays limited to Periodic Background Sync on installed Chrome/Edge; real push would need a server and is not free to run reliably. Recommend not building. | Keep expectations honest in the alert help text | 0 h |

## Suggested sequence

1. **This week:** P0-1 (after APPROVE), P1-1, P1-3, P1-5.
2. **Next 2 weeks:** P1-2, P1-4, P2-1 (when Ridge has the key), P2-2 decision, P3-2 (Ridge).
3. **Weeks 3 to 6:** P1-6, P1-7, P2-3, P3-1, P3-3, and the Option G relay pilot if Ridge says go (P2-4).
4. **After:** the rest of P3, then P4 by Ridge's choice.

Rough totals: P1 about 18 to 24 h, P2 about 14 to 20 h excluding the opt-in MVP (add 16 to 24 h for it), P3 about 12 to 18 h, P4 about 20 to 30 h.

## Decisions I need from Ridge (nothing proceeds without them)

1. APPROVE the merge of PR #2.
2. Keep or pause the daily reminder automations.
3. Legal pages: seek a free review, or switch futures to basis-only meanwhile?
4. USDA API key: will you create it (about 10 minutes)?
5. Opt-in elevator pilot: go, no-go, or later?
6. OK to enable GitHub secret scanning, push protection, Dependabot and a `main` branch rule yourself?
