"""Build a clearly-labelled SAMPLE dataset (data/sample.db -> public/data-sample/).

Locations/commodities mirror the real latest ingest, but 45 days of prices are a
SYNTHETIC seeded random walk. Every row has is_sample=1 and the UI shows a SAMPLE banner.
Exists only so charts/alerts can be demoed before real history accumulates."""
import datetime, random, sys
from . import config, db, export_json

def main():
    real = db.connect()
    base = real.execute("""SELECT b.*, l.state, l.name, l.section, l.lat, l.lon, l.geo_method, l.distance_mi
                           FROM bids b JOIN locations l ON l.id=b.location_id
                           WHERE b.report_date=(SELECT MAX(report_date) FROM bids)""").fetchall()
    if not base:
        sys.exit("no real data yet - run python3 -m ingest.ingest first")
    p = config.DATA_DIR / "sample.db"
    if p.exists():
        p.unlink()
    s = db.connect(p)
    end = datetime.date.fromisoformat(base[0]["report_date"])
    rng = random.Random(42)
    for r in base:
        s.execute("""INSERT OR IGNORE INTO locations(state,name,section,lat,lon,geo_method,distance_mi) VALUES (?,?,?,?,?,?,?)""",
                  (r["state"], r["name"], r["section"], r["lat"], r["lon"], r["geo_method"], r["distance_mi"]))
        lid = s.execute("SELECT id FROM locations WHERE state=? AND name=? AND section=?", (r["state"], r["name"], r["section"])).fetchone()[0]
        scale = 0.004 if r["unit"] == "$/Bu" else 0.003
        lo, hi, avg = r["bid_low"], r["bid_high"], r["bid_avg"] or r["bid_high"]
        pts = []
        for d in range(0, 45):
            pts.append((end - datetime.timedelta(days=d), lo, hi, avg))
            step = rng.gauss(0, scale) * hi
            lo, hi, avg = lo - step, hi - step, avg - step
        for day, l_, h_, a_ in pts:
            if day.weekday() >= 5:
                continue
            s.execute("""INSERT OR REPLACE INTO bids(commodity,location_id,grade,protein,bid_low,bid_high,bid_avg,unit,
                         basis_low,basis_high,basis_unit,basis_futures_month,basis_low_month,basis_high_month,delivery,freight,sale_type,report_date,
                         source_report,source_title,fetched_at,is_sample) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                      (r["commodity"], lid, r["grade"], r["protein"], round(l_, 4), round(h_, 4), round(a_, 4), r["unit"],
                       r["basis_low"], r["basis_high"], r["basis_unit"], r["basis_futures_month"], r["basis_low_month"], r["basis_high_month"], r["delivery"],
                       r["freight"], r["sale_type"], day.isoformat(), r["source_report"], "SAMPLE " + (r["source_title"] or ""), "SAMPLE"))
    for f in real.execute("SELECT * FROM futures WHERE report_date=(SELECT MAX(report_date) FROM futures)"):
        s.execute("INSERT OR REPLACE INTO futures(report_date,exchange,commodity,contract,settle_cents,source_report,is_sample) VALUES (?,?,?,?,?,?,1)",
                  (f["report_date"], f["exchange"], f["commodity"], f["contract"], f["settle_cents"], "SAMPLE"))
    s.commit()
    export_json.export(s, config.ROOT / "public" / "data-sample", sample=True)

if __name__ == "__main__":
    main()
