#!/usr/bin/env bash
# Called only by the refresh-alert job in .github/workflows/pages.yml (never by hand). Opens ONE GitHub issue labelled
# "refresh-failure" when the build or deploy failed (or comments on the one already open) and closes it after the next fully
# successful run. Uses only the gh CLI that GitHub-hosted runners ship with and the built-in job token (issues: write).
# Inputs (env): BUILD_RESULT, DEPLOY_RESULT, PARTIAL_RESULT (success|failure|skipped|cancelled), INGEST_FAILED (lines, may be empty),
# RUN_URL, EVENT_NAME. PARTIAL_RESULT=failure means a partial publish: the good reports went live, some reports are unavailable.
set -euo pipefail
LABEL="refresh-failure"
TITLE="Daily data refresh is failing"
now="$(TZ=America/Chicago date '+%a %b %-d, %Y %-I:%M %p CT')"
open_issues="$(gh issue list --label "$LABEL" --state open --json number --jq '.[].number' 2>/dev/null || true)"

if [ "${BUILD_RESULT:-}" = "failure" ] || [ "${DEPLOY_RESULT:-}" = "failure" ] || [ "${PARTIAL_RESULT:-}" = "failure" ]; then
  if [ "${BUILD_RESULT:-}" = "failure" ]; then
    where="The build failed, so nothing was published. The live site still shows the last good data (fail-safe)."
  elif [ "${DEPLOY_RESULT:-}" = "failure" ]; then
    where="The build passed but publishing to GitHub Pages failed. The live site still shows the last good data."
  else
    where="Partial publish: the USDA reports that parsed were published; the failed report(s) below are shown as unavailable on the site."
  fi
  details="${INGEST_FAILED:-}"
  [ -n "$details" ] || details="(no report-level failure recorded: see the run log for the failing step)"
  body="$(printf '**Refresh failed** (%s, trigger: %s)\n\n%s\n\nReports / reason:\n```\n%s\n```\n\nRun log: %s\n\nThis issue closes itself after the next successful publish run.' \
    "$now" "${EVENT_NAME:-unknown}" "$where" "$details" "${RUN_URL:-}")"
  first="$(printf '%s\n' "$open_issues" | head -n 1)"
  if [ -n "$first" ]; then
    gh issue comment "$first" --body "$body"
    echo "commented on open refresh-failure issue #$first"
  else
    gh label create "$LABEL" --color B60205 --description "The daily USDA data refresh or publish failed" >/dev/null 2>&1 || true
    gh issue create --title "$TITLE" --label "$LABEL" --body "$body"
  fi
elif [ "${BUILD_RESULT:-}" = "success" ] && [ "${DEPLOY_RESULT:-}" = "success" ]; then
  for n in $open_issues; do
    gh issue close "$n" --comment "Fixed: this run published successfully ($now): ${RUN_URL:-}"
    echo "closed refresh-failure issue #$n"
  done
else
  echo "build=${BUILD_RESULT:-?} deploy=${DEPLOY_RESULT:-?}: no alert change"
fi
