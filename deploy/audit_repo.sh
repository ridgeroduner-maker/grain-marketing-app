#!/usr/bin/env bash
# READ-ONLY pre-publication audit. Run it before the repo is ever made public. It changes nothing and contacts no one.
#   ./deploy/audit_repo.sh            # audits every branch/tag in the local git history
# It is a quick screen, NOT a replacement for a real secret scanner (gitleaks / trufflehog / GitHub secret scanning); run one of those too.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0; note() { printf '%s\n' "$*"; }; bad() { printf 'FINDING: %s\n' "$*"; fail=1; }

note "== 1. Files that should never be in history (.env, keys, databases, tiles)"
hits=$(git log --all --name-only --pretty=format: | sort -u | grep -Ei '(^|/)\.env($|\.)|\.pem$|\.key$|id_rsa|\.p12$|\.sqlite$|\.db$|\.pmtiles$|credentials|secret' | grep -v '\.env\.example$' || true)
[ -n "$hits" ] && bad "suspicious paths ever committed:"$'\n'"$hits"

note "== 2. Secret-looking strings anywhere in history (all commits, text diffs)"
pat='(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9]{32,}|AIza[0-9A-Za-z_-]{35}|(api[_-]?key|secret|token|password)["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9_\-]{16,})'
hits=$(git log --all -p --no-color -I'^$' 2>/dev/null | grep -E '^\+' | grep -Ei "$pat" | cut -c1-160 | head -20)
[ -n "$hits" ] && bad "possible secrets (review each; USDA_AMS_API_KEY is only the NAME of an env var, not a value):"$'\n'"$hits"

note "== 3. Personal data: author/committer emails in history (these become public)"
git log --all --format='%an <%ae>%n%cn <%ce>' | sort | uniq -c | sort -rn
note "   (Review the list above. GitHub noreply addresses are fine; a personal address would be published.)"

note "== 4. Large blobs in history (GitHub warns at 50 MiB, blocks at 100 MiB; and history is forever)"
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '$1=="blob" && $3>5242880 {printf "%.1f MB  %s\n",$3/1048576,$4}' | sort -rn | head

note "== 5. Tracked files that are ignored/should not ship"
tracked=$(git ls-files | grep -E '(^|/)(\.env|data/grain\.db|data/ingest\.log)$|\.pmtiles$|data-sample' || true)
[ -n "$tracked" ] && bad "tracked but should not be:"$'\n'"$tracked"

note "== 6. Other things only the owner can judge (printed, not tested)"
note "   - README/legal pages contain the owner's name and ridgeroduner@gmail.com ON PURPOSE (legal pages); anything else personal?"
note "   - Review files under review-*/, notes and fixtures for anything private (PDF fixtures are public USDA reports)."
[ $fail -eq 0 ] && note "RESULT: no findings from this quick screen" || note "RESULT: findings above - resolve BEFORE making the repo public"
exit $fail
