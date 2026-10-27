import sqlite3
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
  id INTEGER PRIMARY KEY,
  state TEXT NOT NULL,
  name TEXT NOT NULL,            -- 'North Central' or 'Enderlin, ND'
  section TEXT NOT NULL DEFAULT '', -- buyer type: Country Elevators / Terminals ...
  lat REAL, lon REAL,
  geo_method TEXT,               -- override | gazetteer_town | approx_region_centroid
  distance_mi REAL,              -- haversine from Gann Valley
  UNIQUE(state, name, section)
);
CREATE TABLE IF NOT EXISTS bids (
  id INTEGER PRIMARY KEY,
  commodity TEXT NOT NULL,       -- corn|soybeans|spring_wheat|winter_wheat|sunflowers
  location_id INTEGER NOT NULL REFERENCES locations(id),
  grade TEXT NOT NULL DEFAULT '',
  protein TEXT NOT NULL DEFAULT '',
  bid_low REAL, bid_high REAL, bid_avg REAL,   -- 'bid' for ranking = bid_high
  unit TEXT,                     -- $/Bu or $/Cwt
  basis_low REAL, basis_high REAL, basis_unit TEXT, basis_futures_month TEXT,
  delivery TEXT NOT NULL DEFAULT 'Current',
  freight TEXT, sale_type TEXT,
  report_date TEXT NOT NULL,     -- YYYY-MM-DD
  source_report TEXT NOT NULL,   -- AMS_3186 ...
  source_title TEXT,
  fetched_at TEXT,
  posted_at TEXT,                -- when USDA published the report (ISO, America/Chicago); NULL if unknown
  report_status TEXT,            -- Final | Preliminary
  is_sample INTEGER NOT NULL DEFAULT 0,
  UNIQUE(report_date, source_report, commodity, grade, protein, location_id, delivery)
);
CREATE INDEX IF NOT EXISTS idx_bids_lookup ON bids(commodity, location_id, report_date);
CREATE TABLE IF NOT EXISTS futures (
  report_date TEXT NOT NULL, exchange TEXT NOT NULL, commodity TEXT NOT NULL,
  contract TEXT NOT NULL, settle_cents REAL, source_report TEXT, is_sample INTEGER NOT NULL DEFAULT 0, posted_at TEXT,
  PRIMARY KEY(report_date, exchange, commodity, contract)
);
CREATE TABLE IF NOT EXISTS unlocated (       -- rows we could not place on the map
  report_date TEXT, source_report TEXT, state TEXT, name TEXT, section TEXT, reason TEXT,
  PRIMARY KEY(report_date, source_report, state, name, section)
);
CREATE TABLE IF NOT EXISTS ingest_runs (
  id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, source TEXT, summary TEXT, ok INTEGER
);
CREATE TABLE IF NOT EXISTS skipped_rows (    -- in-scope bids the parser could not place (e.g. no region text); shown in the UI
  report_date TEXT, source_report TEXT, state TEXT, commodity TEXT, heading TEXT, section TEXT,
  bid_low REAL, bid_high REAL, unit TEXT, delivery TEXT, reason TEXT,
  PRIMARY KEY(report_date, source_report, commodity, heading, section, delivery, bid_low, bid_high)
);
CREATE TABLE IF NOT EXISTS outside_bids (    -- located bids beyond the radius but within MARGIN_MILES: listed in the UI, never pinned or ranked
  report_date TEXT, source_report TEXT, state TEXT, location TEXT, section TEXT, commodity TEXT,
  grade TEXT DEFAULT '', protein TEXT DEFAULT '', delivery TEXT DEFAULT 'Current', freight TEXT,
  bid_low REAL, bid_high REAL, unit TEXT, distance_mi REAL, report_status TEXT, posted_at TEXT, geo_method TEXT,
  PRIMARY KEY(report_date, source_report, commodity, location, section, grade, protein, delivery)
);
"""

VIEW_SQL = """
CREATE VIEW bids_flat AS
  SELECT b.commodity, l.state||' '||l.name AS location, l.lat, l.lon, l.geo_method, l.distance_mi,
         b.bid_high AS bid, b.bid_low, b.bid_avg, b.unit, b.basis_low, b.basis_high, b.basis_unit,
         b.basis_futures_month, b.delivery, b.grade, b.protein, b.report_date, b.posted_at, b.source_report, b.is_sample
  FROM bids b JOIN locations l ON l.id=b.location_id;
"""

def connect(path=None):
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate(con)
    return con

def _migrate(con):
    """Add columns introduced after the first build to pre-existing local databases; (re)create the view."""
    def cols(t): return {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
    for t, c, typ in (("bids", "posted_at", "TEXT"), ("bids", "report_status", "TEXT"), ("futures", "posted_at", "TEXT"), ("ingest_runs", "ok", "INTEGER"),
                    ("skipped_rows", "grade", "TEXT"), ("skipped_rows", "protein", "TEXT"), ("skipped_rows", "freight", "TEXT"), ("outside_bids", "geo_method", "TEXT")):
        if c not in cols(t):
            con.execute(f"ALTER TABLE {t} ADD COLUMN {c} {typ}")
    con.execute("DROP VIEW IF EXISTS bids_flat")
    con.executescript(VIEW_SQL)
    con.commit()
