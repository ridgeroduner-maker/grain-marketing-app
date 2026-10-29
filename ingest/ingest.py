"""Daily ingest: AMS grain bids -> SQLite, 300-mile haversine filter.

Usage:
  python3 -m ingest.ingest                 # today's published reports (PDF, keyless; MARS if key set)
  python3 -m ingest.ingest --source pdf    # force keyless PDF path
  python3 -m ingest.ingest --source mars --date 2026-10-26
  python3 -m ingest.ingest --source mars --backfill-days 90   # needs USDA_AMS_API_KEY
  python3 -m ingest.ingest --export        # also regenerate public/data/*.json
Never writes anywhere but the local SQLite file and public/data/. Publishes nothing."""
import argparse, datetime, json, sys, traceback
from . import config, geo, db, parse_pdf, mars_api, export_json

def upsert(con, bids, futures, source_label, slug_state, report_date_for_unlocated=None, posted_at=None, status=None):
    stats = {"kept": 0, "outside_radius": 0, "unlocated": 0, "futures": 0}
    now = export_json.now_central().isoformat()
    for b in bids:
        state = b["state"] or b["location"].rsplit(",", 1)[-1].strip()
        if "," in b["location"]:
            state = b["location"].rsplit(",", 1)[-1].strip()
        hit = geo.locate(state, b["location"], b["section"])
        if not hit:
            con.execute("INSERT OR REPLACE INTO unlocated VALUES (?,?,?,?,?,?)",
                        (b["report_date"], b["source_report"], state, b["location"], b["section"], "no coordinates"))
            stats["unlocated"] += 1
            continue
        lat, lon, method = hit
        dist = geo.haversine_miles(config.CENTER_LAT, config.CENTER_LON, lat, lon)
        if dist > config.RADIUS_MILES:
            stats["outside_radius"] += 1
            if dist <= config.MARGIN_MILES:
                con.execute("""INSERT OR REPLACE INTO outside_bids(report_date,source_report,state,location,section,commodity,grade,protein,
                               delivery,freight,bid_low,bid_high,unit,distance_mi,report_status,posted_at,geo_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (b["report_date"], b["source_report"], state, b["location"], b["section"], b["commodity"], b["grade"], b["protein"],
                             b["delivery"], b["freight"], b["bid_low"], b["bid_high"], b["unit"], round(dist, 1), status, posted_at, method))
                stats["near_margin"] = stats.get("near_margin", 0) + 1
            continue
        con.execute("""INSERT INTO locations(state,name,section,lat,lon,geo_method,distance_mi) VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(state,name,section) DO UPDATE SET lat=excluded.lat, lon=excluded.lon,
                       geo_method=excluded.geo_method, distance_mi=excluded.distance_mi""",
                    (state, b["location"], b["section"], lat, lon, method, round(dist, 1)))
        lid = con.execute("SELECT id FROM locations WHERE state=? AND name=? AND section=?",
                          (state, b["location"], b["section"])).fetchone()[0]
        con.execute("""INSERT OR REPLACE INTO bids(commodity,location_id,grade,protein,bid_low,bid_high,bid_avg,unit,
                       basis_low,basis_high,basis_unit,basis_futures_month,basis_low_month,basis_high_month,delivery,freight,sale_type,report_date,
                       source_report,source_title,fetched_at,posted_at,report_status,is_sample) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                    (b["commodity"], lid, b["grade"], b["protein"], b["bid_low"], b["bid_high"], b["bid_avg"], b["unit"],
                     b["basis_low"], b["basis_high"], b["basis_unit"], b["basis_futures_month"], b["basis_low_month"], b["basis_high_month"], b["delivery"],
                     b["freight"], b["sale_type"], b["report_date"], b["source_report"], b["source_title"], now, posted_at, status))
        stats["kept"] += 1
    for f in futures:
        con.execute("INSERT OR REPLACE INTO futures(report_date,exchange,commodity,contract,settle_cents,source_report,is_sample,posted_at) VALUES (?,?,?,?,?,?,0,?)",
                    (f["report_date"], f["exchange"], f["commodity"], f["contract"], f["settle_cents"], f["source_report"], posted_at))
        stats["futures"] += 1
    return stats

def store_skipped(con, skipped):
    """Persist (and print) in-scope rows that could not be placed, instead of dropping them silently."""
    for reason, b in skipped:
        con.execute("""INSERT OR REPLACE INTO skipped_rows(report_date,source_report,state,commodity,heading,section,bid_low,bid_high,unit,delivery,reason,grade,protein,freight)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (b["report_date"], b["source_report"], b.get("state"), b["commodity"], b.get("heading"), b["section"],
                     b["bid_low"], b["bid_high"], b["unit"], b["delivery"], reason, b.get("grade"), b.get("protein"), b.get("freight")))
        print(f"  SKIPPED ({reason}): {b['source_report']} {b['commodity']} {b['section']} {b['bid_low']}-{b['bid_high']} {b['unit']} [{b.get('heading')}]")
    return len(skipped)

def run(source, date_iso, backfill_days, export, accept_row_drop=False):
    con = db.connect()
    started = export_json.now_central().isoformat()
    use_mars = source == "mars" or (source == "auto" and bool(__import__("os").environ.get(config.API_KEY_ENV)))
    summary, failures = [], 0
    if use_mars:
        mars_api._key()   # fail fast with NoApiKey instead of once per report
    for rep in config.REPORTS:
        slug, title, state = rep["slug"], rep["title"], rep["state"]
        try:
            # PDF is always fetched for the futures settlements block (keyless)
            parsed = None
            try:
                pdf = parse_pdf.fetch_pdf(slug)
                parsed = parse_pdf.parse_report(parse_pdf.pdf_to_text(pdf), slug, title, state)
            except Exception as e:
                if not use_mars:
                    raise
                print(f"  [{slug}] PDF unavailable ({e}); continuing with API only", file=sys.stderr)
            bids = parsed["bids"] if (parsed and not use_mars) else []
            if parsed and not use_mars and not bids and slug not in config.MAY_BE_EMPTY:
                raise ValueError(f"report {slug} parsed to zero in-scope bids (layout change?)")
            skipped = parsed["skipped"] if (parsed and not use_mars) else []
            futs = []
            if parsed:
                futs = [dict(f, report_date=parsed["report_date"], source_report=f"AMS_{slug}") for f in parsed["futures"]]
            if use_mars:
                if backfill_days:
                    end = datetime.date.today()
                    rows = mars_api.fetch_report_range(slug, (end - datetime.timedelta(days=backfill_days)).isoformat(), end.isoformat())
                else:
                    rows = mars_api.fetch_report_detail(slug, date_iso)
                bids, skipped = mars_api.normalize_rows(rows, slug, title, state)
            n_skipped = store_skipped(con, skipped)
            rd0 = parsed["report_date"] if parsed else date_iso
            posted = parse_pdf.fetch_posted_at(slug, rd0) if rd0 else None
            st = upsert(con, bids, futs, "mars" if use_mars else "pdf", state,
                        posted_at=posted, status=(parsed or {}).get("status"))
            rd = parsed["report_date"] if parsed else date_iso
            line = f"AMS_{slug} {title[:38]:38} date={rd} parsed={len(bids)} skipped={n_skipped} {st}"
            print(line); summary.append(line)
        except Exception as e:
            failures += 1
            traceback.print_exc()
            summary.append(f"AMS_{slug} FAILED: {e}")
    con.execute("INSERT INTO ingest_runs(started_at,finished_at,source,summary,ok) VALUES (?,?,?,?,?)",
                (started, export_json.now_central().isoformat(), "mars" if use_mars else "pdf",
                 "\n".join(summary), 0 if failures else 1))
    con.commit()
    if export and failures:
        print(f"NOT EXPORTING: {failures} report(s) failed to parse; public/data/ left as it was "
              "(the app will show its age). Fix the parser/report and re-run.", file=sys.stderr)
    elif export:
        try:
            export_json.export(con, config.ROOT / "public" / "data", sample=False, accept_row_drop=accept_row_drop)
        except export_json.ExportGuardError as e:
            print(f"NOT EXPORTING: {e}", file=sys.stderr)
            con.execute("UPDATE ingest_runs SET ok=0 WHERE id=(SELECT MAX(id) FROM ingest_runs)")
            con.commit()
            failures += 1
    return failures

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["auto", "pdf", "mars"], default="auto")
    ap.add_argument("--date", help="YYYY-MM-DD (mars only)")
    ap.add_argument("--backfill-days", type=int, default=0, help="mars only")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--accept-row-drop", action="store_true", help="export even if the row count fell sharply vs the last good export")
    a = ap.parse_args()
    try:
        rc = run(a.source, a.date, a.backfill_days, a.export, a.accept_row_drop)
    except mars_api.NoApiKey as e:
        print(f"ERROR: {e}. Use --source pdf or set the key (see README).", file=sys.stderr); rc = 2
    sys.exit(1 if rc else 0)

if __name__ == "__main__":
    main()
