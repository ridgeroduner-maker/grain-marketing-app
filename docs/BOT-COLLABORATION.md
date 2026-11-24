# Bot collaboration guide

How Ridge, GradenHolan, and their bots share work on this public repo. Merging to `main` publishes the live site at https://ridgeroduner-maker.github.io/grain-marketing-app/, so treat it carefully.

## Who's who

- **Ridge** (`ridgeroduner-maker`) is the owner.
- **GradenHolan** is the partner, invited with write access.
- Each person's bots work in this same repo. They push branches and open pull requests; they do not push to `main`.

## Branches and pull requests

- Name branches `bot-or-person/topic` (for example `bobby/hide-stale-rows` or `graden/wy-mt-reports`).
- Never push to `main`. Open a pull request instead.
- One pull request per change.
- Merging to `main` publishes the live site. That needs Ridge's typed **APPROVE**. Do not merge without it.

Open pull request **#2** (`fix/report-date-no-leading-zero`) must be merged before **December 1, 2026**. After that date, USDA reports with a single-digit day will break the daily refresh again.

## Pull request description

Use this layout (also in `.github/pull_request_template.md`):

```
## What
<!-- What changed -->

## Why
<!-- Why this change is needed -->

## Tests
<!-- Commands you ran and the result -->

## Data impact
<!-- Effect on bids, ingest, published JSON, or the live site. "None" is fine. -->
```

## Tests to run

The project uses Python's `unittest` (not pytest) and three Node scripts. Run all of these before opening a PR:

```
python3 -m unittest discover -s ingest/tests
node public/alerts-core.test.js
node public/mapmode.test.js
node public/directory.test.js
```

## Rules

- Free tools only. Keep the app free to run (free map provider, GitHub Pages, no paid APIs or paid plans).
- USDA AMS regional data only. Show futures with USDA credit.
- This repo is public. Never commit secrets, API keys, tokens, or credentials.
- The directory layer is **not bids**. It stays off by default, labeled "Directory only, NOT bids," and stays out of best bid, alerts, and the bids table.
- Keep AgState and Gossel (HERBERT GOSSEL & SONS, dba KIMBALL GRAIN CO) out of the directory.
- Do not edit the Terms or Privacy pages without Ridge.
