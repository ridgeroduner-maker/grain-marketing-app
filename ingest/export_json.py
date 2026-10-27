"""Export SQLite -> static JSON consumed by the PWA (public/data or public/data-sample)."""
import datetime, json, sqlite3, zoneinfo
from . import config, db

LABELS = {"corn": "Corn", "soybeans": "Soybeans", "spring_wheat": "Spring wheat",
          "winter_wheat": "Winter wheat", "sunflowers": "Sunflowers"}

SECTION_SHORT = {"Country Elevators": "", "Terminal Elevators": "terminal", "Mills and Processors": "mill/processor",
                 "Terminals/Mills/Processors": "terminal/processor"}

_FREIGHT_TERM = {"DLVD": "Delivered", "FOB": "FOB", "CIF": "CIF"}
_FREIGHT_MODE = {"T": "truck", "R": "rail", "B": "barge"}

def freight_label(code):
    """'DLVD-T' -> 'Delivered, truck (DLVD-T)'; unknown codes are shown as printed."""
    if not code:
        return "freight not stated"
    term, _, mode = code.partition("-")
    if term not in _FREIGHT_TERM:
        return code
    return f"{_FREIGHT_TERM[term]}, {_FREIGHT_MODE.get(mode, mode.lower())} ({code})" if mode else f"{_FREIGHT_TERM[term]} ({code})"

def variant_of(commodity, grade, protein, freight=""):
    """Comparable product bucket for 'best bid'. Grades are NEVER merged (ND soybeans US #2 vs US #1 elsewhere stay
    separate) and different freight terms (delivered vs FOB) are separate too."""
    parts = [grade or LABELS.get(commodity, commodity)]
    if commodity in ("spring_wheat", "winter_wheat"):
        parts.append(f"{protein} protein" if (protein or "").endswith("%") else "ordinary protein (no premium)")
    parts.append(freight_label(freight))
    return " · ".join(parts)

def basis_ref(commodity, month):
    ex = config.BASIS_EXCHANGE.get(commodity)
    return f"{ex} {month} futures" if ex and month else ""

def label_of(state, name, section):
    base = name if "," in name else f"{state} {name}"
    extra = SECTION_SHORT.get(section, section)
    return f"{base} ({extra})" if extra else base

CENTRAL = zoneinfo.ZoneInfo("America/Chicago")

def _label_for(source_report):
    for rep in config.REPORTS:
        if f"AMS_{rep['slug']}" == source_report:
            return f"{rep['state'] or 'Sunflower'} ({rep['slug']})"
    return source_report

def now_central():
    return datetime.datetime.now(CENTRAL).replace(microsecond=0)

def central_iso(ts):
    """ISO string with an explicit Central offset. Naive stored times were written on a Central-time box (see README)."""
    if not ts:
        return None
    d = datetime.datetime.fromisoformat(ts)
    return (d.replace(tzinfo=CENTRAL) if d.tzinfo is None else d.astimezone(CENTRAL)).isoformat(timespec="seconds")

class ExportGuardError(RuntimeError):
    """Raised instead of exporting when the new data looks broken (row count fell sharply)."""

def business_days_between(d0, d1):
    """Weekdays from d0 (exclusive) to d1 (inclusive); 0 if d1 <= d0. Holidays are not modelled."""
    n, d = 0, d0
    while d < d1:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n

def _outside(cur, today):
    """Bids whose (approximate) location is beyond the radius but within the margin: newest edition per report only."""
    out = []
    for r in cur.execute("""SELECT o.* FROM outside_bids o WHERE o.report_date=(SELECT MAX(x.report_date) FROM outside_bids x WHERE x.source_report=o.source_report)
                            AND o.report_date=(SELECT MAX(b.report_date) FROM bids b WHERE b.source_report=o.source_report)
                            ORDER BY o.distance_mi"""):
        age = (today - datetime.date.fromisoformat(r["report_date"])).days
        if age > config.STALE_EXPIRE_DAYS:
            continue
        out.append({"commodity": r["commodity"], "variant": variant_of(r["commodity"], r["grade"], r["protein"], r["freight"]),
                    "location": label_of(r["state"], r["location"], r["section"]), "grade": r["grade"], "protein": r["protein"],
                    "delivery": r["delivery"], "freight_label": freight_label(r["freight"]),
                    "bid_low": r["bid_low"], "bid_high": r["bid_high"], "unit": r["unit"], "distance_mi": r["distance_mi"],
                    "report_date": r["report_date"], "source_report": r["source_report"], "report_status": r["report_status"],
                    "posted_at": central_iso(r["posted_at"]) if r["posted_at"] else None,
                    "precision": "town" if r["geo_method"] == "gazetteer_town" else "region", "approximate": r["geo_method"] != "gazetteer_town"})
    return out

def export(con, outdir, sample=False, today=None, accept_row_drop=False):
    """today: datetime.date used for staleness (defaults to the real date; sample data uses its own newest date)."""
    outdir.mkdir(parents=True, exist_ok=True)
    cur = con.cursor()
    rows = cur.execute("""SELECT b.*, l.state, l.name, l.section, l.lat, l.lon, l.geo_method, l.distance_mi
                          FROM bids b JOIN locations l ON l.id=b.location_id
                          ORDER BY b.report_date""").fetchall()
    maxdate = max((r["report_date"] for r in rows), default=None)
    if today is None:
        today = datetime.date.fromisoformat(maxdate) if (sample and maxdate) else datetime.date.today()
    # Newest report date per source report: a region/row missing from that report's newest edition has dropped out
    # and must not keep showing its old bid next to fresh ones (history keeps it).
    newest = {}
    for r in rows:
        newest[r["source_report"]] = max(newest.get(r["source_report"], ""), r["report_date"])
    series = {}
    for r in rows:
        key = (r["commodity"], r["location_id"], r["grade"], r["protein"], r["delivery"])
        series.setdefault(key, []).append(r)
    latest_rows, dropped = [], []
    for key, lst in series.items():
        last = lst[-1]
        prev = lst[-2] if len(lst) > 1 else None
        age = (today - datetime.date.fromisoformat(last["report_date"])).days
        if last["report_date"] < newest[last["source_report"]]:
            dropped.append(f'{last["source_report"]} {last["name"]} {last["commodity"]} (last {last["report_date"]})')
            continue
        if age > config.STALE_EXPIRE_DAYS:
            dropped.append(f'{last["source_report"]} {last["name"]} {last["commodity"]} (expired, {age} days old)')
            continue
        latest_rows.append({
            "commodity": last["commodity"], "location_id": last["location_id"],
            "location": label_of(last["state"], last["name"], last["section"]),
            "variant": variant_of(last["commodity"], last["grade"], last["protein"], last["freight"]),
            "key": "|".join(str(x) for x in key),
            "state": last["state"], "section": last["section"], "lat": last["lat"], "lon": last["lon"],
            "geo_method": last["geo_method"],
            # 'town' only where USDA names a town (sunflower processors); everything else is a region bid drawn at an
            # approximate centre we chose, so it is labelled approximate in the UI.
            "precision": "town" if last["geo_method"] == "gazetteer_town" else "region",
            "distance_mi": last["distance_mi"],
            "grade": last["grade"], "protein": last["protein"], "delivery": last["delivery"],
            "freight": last["freight"], "freight_label": freight_label(last["freight"]),
            "bid_low": last["bid_low"], "bid_high": last["bid_high"], "bid_avg": last["bid_avg"],
            "unit": last["unit"], "basis_low": last["basis_low"], "basis_high": last["basis_high"],
            "basis_unit": last["basis_unit"], "basis_futures_month": last["basis_futures_month"],
            "basis_ref": basis_ref(last["commodity"], last["basis_futures_month"]),
            "report_date": last["report_date"], "source_report": last["source_report"],
            "posted_at": last["posted_at"], "report_status": last["report_status"],
            "prev_bid_high": prev["bid_high"] if prev else None,
            "prev_report_date": prev["report_date"] if prev else None,
            "age_days": age, "stale_days": age,
        })
    # Row-count regression guard: a layout change that silently drops rows must not overwrite the last good export.
    prev_file = outdir / "latest.json"
    if not sample and not accept_row_drop and prev_file.exists():
        try:
            prev_n = len(json.loads(prev_file.read_text()))
        except ValueError:
            prev_n = 0
        if prev_n and len(latest_rows) < config.MIN_ROW_RATIO * prev_n:
            raise ExportGuardError(f"new export has {len(latest_rows)} rows vs {prev_n} in the last good export "
                                   f"(< {int(config.MIN_ROW_RATIO * 100)}%); NOT exporting. If this drop is real, re-run with --accept-row-drop.")
    live_keys = {r["key"] for r in latest_rows}
    hist = {}
    for key, lst in series.items():
        k = "|".join(str(x) for x in key)
        hist[k] = [[r["report_date"], r["bid_low"], r["bid_high"], r["bid_avg"]] for r in lst]
    fut_mode = config.futures_display()
    fut = [] if fut_mode == "basis_only" else cur.execute(
        """SELECT * FROM futures WHERE report_date=(SELECT MAX(report_date) FROM futures)
           ORDER BY exchange, commodity""").fetchall()
    skipped = [dict(r) for r in cur.execute(
        """SELECT report_date, source_report, state, commodity, heading, section, bid_low, bid_high, unit, delivery, reason
           , grade, protein, freight
           FROM skipped_rows WHERE report_date=(SELECT MAX(s2.report_date) FROM skipped_rows s2 WHERE s2.source_report=skipped_rows.source_report)
           ORDER BY source_report""")] if not sample else []
    for x in skipped:
        x["variant"] = variant_of(x["commodity"], x.pop("grade"), x.pop("protein"), x.pop("freight"))
    outside = [] if sample else _outside(cur, today)
    ok_run = None if sample else cur.execute("SELECT finished_at FROM ingest_runs WHERE ok=1 ORDER BY id DESC LIMIT 1").fetchone()
    meta = {
        "sample": bool(sample), "generated_at": now_central().isoformat(),
        "last_ingest_ok_at": central_iso(ok_run[0]) if ok_run else None,
        "time_zone": "America/Chicago",
        "export_today": today.isoformat(),
        "latest_report_date": maxdate, "center": {"lat": config.CENTER_LAT, "lon": config.CENTER_LON},
        "radius_miles": config.RADIUS_MILES, "commodities": LABELS,
        "futures_display": fut_mode,
        "stale_expire_days": config.STALE_EXPIRE_DAYS,
        "reports": sorted(newest),
        "report_times": {r["source_report"]: {"report_date": r["report_date"], "posted_at": r["posted_at"], "status": r["report_status"],
                                              "label": _label_for(r["source_report"])}
                         for r in rows if r["report_date"] == newest[r["source_report"]]},
        "dropped_rows": dropped,
        "skipped_rows": skipped,
        "center_name": "Gann Valley, SD",
        "credit": "Source: USDA AMS Livestock, Poultry & Grain Market News (mymarketnews.ams.usda.gov).",
        "n_locations": len({r["location_id"] for r in latest_rows}),
        "notes": "Regional cash bids from USDA AMS Market News, posted about 2 to 4 pm Central each business day. Not real-time.",
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=1))
    (outdir / "outside.json").write_text(json.dumps(outside, separators=(",", ":")))
    (outdir / "latest.json").write_text(json.dumps(latest_rows, separators=(",", ":")))
    (outdir / "history.json").write_text(json.dumps({k: v for k, v in hist.items() if k in live_keys}, separators=(",", ":")))
    (outdir / "futures.json").write_text(json.dumps(
        [{"date": f["report_date"], "exchange": f["exchange"], "commodity": f["commodity"],
          "contract": f["contract"], "settle_cents": f["settle_cents"], "source_report": f["source_report"],
          "posted_at": f["posted_at"]} for f in fut],
        separators=(",", ":")))
    print(f"exported {len(latest_rows)} latest rows ({len(dropped)} dropped/expired), {len(hist)} series, {len(fut)} futures "
          f"[futures_display={fut_mode}], {len(skipped)} unplaced rows -> {outdir}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    if a.sample:
        con = db.connect(config.DATA_DIR / "sample.db")
        export(con, config.ROOT / "public" / "data-sample", sample=True)
    else:
        con = db.connect()
        export(con, config.ROOT / "public" / "data", sample=False)
