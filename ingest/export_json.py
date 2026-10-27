"""Export SQLite -> static JSON consumed by the PWA (public/data or public/data-sample)."""
import datetime, json, sqlite3
from . import config, db

LABELS = {"corn": "Corn", "soybeans": "Soybeans", "spring_wheat": "Spring wheat",
          "winter_wheat": "Winter wheat", "sunflowers": "Sunflowers"}

SECTION_SHORT = {"Country Elevators": "", "Terminal Elevators": "terminal", "Mills and Processors": "mill/processor",
                 "Terminals/Mills/Processors": "terminal/processor"}

def variant_of(commodity, grade, protein):
    """Comparable product bucket for 'best bid' (grade wording differs by state report)."""
    g = (grade or "").lower()
    if commodity == "corn":
        return "Yellow corn"
    if commodity == "soybeans":
        return "Soybeans"
    if commodity in ("spring_wheat", "winter_wheat"):
        return f"{protein} protein" if protein.endswith("%") else (protein or "Ordinary")
    if commodity == "sunflowers":
        return "High oleic" if "oleic" in g else ("NuSun" if "nu sun" in g or "nusun" in g else (grade or "Sunflowers"))
    return grade or ""

def label_of(state, name, section):
    base = name if "," in name else f"{state} {name}"
    extra = SECTION_SHORT.get(section, section)
    return f"{base} ({extra})" if extra else base

def export(con, outdir, sample=False):
    outdir.mkdir(parents=True, exist_ok=True)
    cur = con.cursor()
    rows = cur.execute("""SELECT b.*, l.state, l.name, l.section, l.lat, l.lon, l.geo_method, l.distance_mi
                          FROM bids b JOIN locations l ON l.id=b.location_id
                          ORDER BY b.report_date""").fetchall()
    series, latest = {}, {}
    for r in rows:
        key = (r["commodity"], r["location_id"], r["grade"], r["protein"], r["delivery"])
        series.setdefault(key, []).append(r)
    latest_rows = []
    maxdate = max((r["report_date"] for r in rows), default=None)
    for key, lst in series.items():
        last = lst[-1]
        prev = lst[-2] if len(lst) > 1 else None
        age = (datetime.date.fromisoformat(maxdate) - datetime.date.fromisoformat(last["report_date"])).days if maxdate else 0
        latest_rows.append({
            "commodity": last["commodity"], "location_id": last["location_id"],
            "location": label_of(last["state"], last["name"], last["section"]),
            "variant": variant_of(last["commodity"], last["grade"], last["protein"]),
            "key": "|".join(str(x) for x in key),
            "state": last["state"], "section": last["section"], "lat": last["lat"], "lon": last["lon"],
            "geo_method": last["geo_method"], "distance_mi": last["distance_mi"],
            "grade": last["grade"], "protein": last["protein"], "delivery": last["delivery"],
            "bid_low": last["bid_low"], "bid_high": last["bid_high"], "bid_avg": last["bid_avg"],
            "unit": last["unit"], "basis_low": last["basis_low"], "basis_high": last["basis_high"],
            "basis_unit": last["basis_unit"], "basis_futures_month": last["basis_futures_month"],
            "report_date": last["report_date"], "source_report": last["source_report"],
            "prev_bid_high": prev["bid_high"] if prev else None, "stale_days": age,
        })
    hist = {}
    for key, lst in series.items():
        k = "|".join(str(x) for x in key)
        hist[k] = [[r["report_date"], r["bid_low"], r["bid_high"], r["bid_avg"]] for r in lst]
    fut = cur.execute("""SELECT * FROM futures WHERE report_date=(SELECT MAX(report_date) FROM futures)
                         ORDER BY exchange, commodity""").fetchall()
    meta = {
        "sample": bool(sample), "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "latest_report_date": maxdate, "center": {"lat": config.CENTER_LAT, "lon": config.CENTER_LON},
        "radius_miles": config.RADIUS_MILES, "commodities": LABELS,
        "reports": sorted({r["source_report"] for r in rows}),
        "n_locations": len({r["location_id"] for r in rows}),
        "notes": "End-of-day settlements and regional cash bids from USDA AMS Market News. Not real-time.",
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=1))
    (outdir / "latest.json").write_text(json.dumps(latest_rows, separators=(",", ":")))
    (outdir / "history.json").write_text(json.dumps(hist, separators=(",", ":")))
    (outdir / "futures.json").write_text(json.dumps(
        [{"date": f["report_date"], "exchange": f["exchange"], "commodity": f["commodity"],
          "contract": f["contract"], "settle_cents": f["settle_cents"], "source_report": f["source_report"]} for f in fut],
        separators=(",", ":")))
    print(f"exported {len(latest_rows)} latest rows, {len(hist)} series, {len(fut)} futures -> {outdir}")

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
