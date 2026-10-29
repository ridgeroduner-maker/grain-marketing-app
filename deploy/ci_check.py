#!/usr/bin/env python3
"""Fail-safe gate for the Pages workflow: exits non-zero (so nothing is deployed and the last published site stays) when the exported
data or the built dist/ looks wrong. Pure standard library; reads local files only.

  python3 deploy/ci_check.py data [--data-dir public/data] [--min-rows 30] [--max-age-days 5]
  python3 deploy/ci_check.py dist [--dist-dir dist] [--data-dir public/data]
"""
import argparse, datetime, json, sys, zoneinfo
from pathlib import Path

REQUIRED_ROW_KEYS = ("commodity", "location", "variant", "bid_low", "bid_high", "unit", "report_date", "source_report",
                     "basis_low", "basis_high", "basis_low_month", "basis_high_month", "basis_ref_low", "basis_ref_high", "distance_mi")


def central_today():
    return datetime.datetime.now(zoneinfo.ZoneInfo("America/Chicago")).date()


def check_data(data_dir, min_rows=30, max_age_days=5, today=None):
    """Return a list of problems (empty = OK)."""
    d, bad = Path(data_dir), []
    today = today or central_today()
    try:
        latest = json.loads((d / "latest.json").read_text())
        meta = json.loads((d / "meta.json").read_text())
        for n in ("history.json", "futures.json", "outside.json"):
            json.loads((d / n).read_text())
    except (OSError, ValueError) as e:
        return [f"cannot read exported data: {e}"]
    if not isinstance(latest, list) or len(latest) < min_rows:
        bad.append(f"only {len(latest) if isinstance(latest, list) else '?'} rows in latest.json (need at least {min_rows})")
        return bad
    if meta.get("sample"):
        bad.append("meta.json says this is SAMPLE data")
    for i, r in enumerate(latest):
        miss = [k for k in REQUIRED_ROW_KEYS if k not in r]
        if miss:
            bad.append(f"row {i} ({r.get('location')}) is missing {miss}"); break
        if not (isinstance(r["bid_high"], (int, float)) and r["bid_high"] > 0 and r["bid_low"] <= r["bid_high"]):
            bad.append(f"row {i} ({r['location']}) has an invalid bid range {r['bid_low']}..{r['bid_high']}"); break
    newest = meta.get("latest_report_date")
    try:
        age = (today - datetime.date.fromisoformat(newest)).days
        if age > max_age_days:
            bad.append(f"newest report date {newest} is {age} days old (limit {max_age_days})")
        if age < 0:
            bad.append(f"newest report date {newest} is in the future")
    except (TypeError, ValueError):
        bad.append(f"meta.latest_report_date is missing or invalid: {newest!r}")
    if not meta.get("last_ingest_ok_at"):
        bad.append("meta.last_ingest_ok_at is empty (no successful ingest recorded)")
    return bad


def check_dist(dist_dir, data_dir):
    d, bad = Path(dist_dir), []
    for need in ("index.html", "app.js", "sw.js", "config.js", "style.css", "manifest.webmanifest", "terms.html", "privacy.html",
                 ".nojekyll", "data/latest.json", "data/meta.json"):
        if not (d / need).is_file():
            bad.append(f"dist/{need} is missing")
    if list(d.rglob("*.test.js")):
        bad.append("dist/ contains *.test.js")
    if list(d.rglob("*data-sample*")):
        bad.append("dist/ contains data-sample")
    if (d / ".env").exists() or list(d.rglob(".env*")):
        bad.append("dist/ contains an .env file")
    try:
        if (d / "data" / "latest.json").read_text() != (Path(data_dir) / "latest.json").read_text():
            bad.append("dist/data/latest.json differs from the exported data")
    except OSError as e:
        bad.append(f"cannot compare data: {e}")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("data"); a.add_argument("--data-dir", default="public/data"); a.add_argument("--min-rows", type=int, default=30); a.add_argument("--max-age-days", type=int, default=5)
    b = sub.add_parser("dist"); b.add_argument("--dist-dir", default="dist"); b.add_argument("--data-dir", default="public/data")
    args = ap.parse_args(argv)
    problems = check_data(args.data_dir, args.min_rows, args.max_age_days) if args.cmd == "data" else check_dist(args.dist_dir, args.data_dir)
    if problems:
        for p in problems:
            print(f"CHECK FAILED: {p}", file=sys.stderr)
        print("Not publishing: the last published site stays as it was.", file=sys.stderr)
        return 1
    print(f"{args.cmd} check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
