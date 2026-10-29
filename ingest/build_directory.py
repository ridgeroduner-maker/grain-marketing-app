"""Build public/data/directory.json from the elevator directory CSV (a compiled copy of public state licence lists).

    python3 -m ingest.build_directory --csv /path/to/elevator-directory-v2.csv [--out public/data/directory.json] [--dropped-report PATH]

RUN LOCALLY by whoever refreshes the directory; the result (public/data/directory.json) is what gets committed. The source CSV is NOT in git
(data/source/ and data/elevator-directory*.csv are git-ignored: it carries source notes, licence numbers and counties) and neither
./build_dist.sh nor CI needs it: they only validate the committed JSON (python3 -m ingest.build_directory --check).

The Directory layer is NAMES AND TOWNS ONLY: no prices, phones, addresses, licence numbers, counties or source notes ever reach the output.
It is a separate data file: nothing here touches data/grain.db, latest.json, best-bid ranking, alerts or the bid table.

Input columns (header names, case-insensitive; extra columns are ignored and never copied):
  required  name, town, state, lat, lon
  optional  source_url   (decides which state list a row came from, and so the list's agency and date; see SOURCES)
  optional  category, bid_page_url, geocode_quality, lat_display, lon_display, source_list_date (fallback date only)
  ignored   notes, crops, miles_from_gann_valley (distance is recomputed), licence_class, colocated_n, display_offset, anything else

Rows are DROPPED (and counted in directory.json "dropped"; names go only to the optional local --dropped-report) when: the name is empty or a
placeholder ("NAME"); the name does not look like a business (NO INDIVIDUALS: see is_business); the town is empty / has a digit; the state is not
two letters; lat/lon are missing or impossible; geocode_quality says not found; the point is more than 300 mi (+1 mi rounding tolerance) from
Gann Valley (true lat/lon, never the display ones); the category says individual; or the row duplicates another (same normalised name + town +
state). A bid_page_url that is not a plain http(s) link is cleared (the row stays). Nothing is guessed or repaired."""
import argparse, csv, datetime, hashlib, json, math, re, sys
from pathlib import Path

try:
    from . import config
except ImportError:                                   # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ingest import config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "source" / "elevator-directory.csv"          # git-ignored working copy of the source CSV
DEFAULT_OUT = ROOT / "public" / "data" / "directory.json"
SCHEMA = "grain-directory-2"
# The source CSV rounded miles, so a row can sit a few tenths past 300. A 1-mile tolerance keeps those.
ROUND_TOLERANCE_MILES = 1.0
PLACEHOLDER_NAMES = {"NAME", "N/A", "NA", "NONE", "NULL", "TBD", "UNKNOWN", "TEST"}
INDIVIDUAL_CATEGORIES = {"individual", "person", "sole proprietor", "sole_proprietor", "individual license holder"}
# NO INDIVIDUALS. A name is kept only if it has a business marker (whole word, case-insensitive), or two different "weak" markers.
# Conservative: when unsure the row is dropped. The list of dropped names (and kept-but-borderline ones) goes to a LOCAL report only.
STRONG_MARKERS = frozenset("""INC INCORPORATED LLC LLP LP LTD CORP CORPORATION CO COMPANY COOP COOPERATIVE COOPERATIVES OP ASSN ASSOCIATION ASSOC SOCIETY
    EXCHANGE UNION EQUITY ELEVATOR ELEVATORS GRAIN GRAINS FARMERS GROWERS PRODUCERS AG AGRI AGRONOMY AGRICULTURE FEED FEEDS SEED SEEDS MILL MILLS MILLING
    PROCESSING PROCESSORS PROCESSOR ETHANOL TERMINAL PARTNERS PARTNERSHIP GROUP ENERGY RENEWABLE FUELS BIOFUELS INDUSTRIES PRODUCTS FOODS CREAMERY MALTING
    SUPPLY STORAGE WAREHOUSE COMMODITIES COMMODITY MARKETING CRUSH CRUSHING SOY SOYA SOYBEAN BEAN BEANS SUNFLOWER INTERNATIONAL INTL STOCK NUTRITION
    BROKERAGE""".split())
WEAK_MARKERS = frozenset("ENTERPRISES HOLDINGS FARM FARMS SERVICE SERVICES SONS BROS BROTHERS TRUCKING TRANSPORT LAND TRADING CROP CROPS FAMILY".split())
SOFT_STRONG = frozenset("AG CO LP OP STOCK INTL GROUP".split())     # kept, but listed as borderline in the local report when they are the only marker
# geocode_quality (primary token before ';'). The popup says "the town's approximate center", which is only true for town-level values.
TOWN_LEVEL_QUALITY = {"", "town_centroid", "town", "place", "place_centroid", "census_place", "city_centroid", "city", "census_place_centroid",
                      "census_township_centroid", "census_cdp_centroid", "geonames_populated_place"}
NOT_FOUND_QUALITY = {"none", "failed", "fail", "unmatched", "not_found", "notfound", "unknown", "missing"}
FLAG_MAP = {"buyer_licence_address_may_be_office": "office", "county_mismatch_check": "check"}      # + ambiguous_name_N_places -> "ambiguous"
NAME_MAX = 120
SUFFIX_WORDS = {"INC", "LLC", "CO", "COMPANY", "CORP", "CORPORATION", "LTD", "LP", "LLP", "THE"}

# One entry per state list. The date is a property of the LIST (Data Scout changelog, Oct 28, 2026), not of a row: a merged row cites several lists and
# the per-row source_list_date column does not line up with them. `kind` = how the date is worded: "as of" (the list prints one) or "fetched"
# (live page with no date: we only know when it was fetched).
SOURCES = {
    "SD": {"agency": "South Dakota Public Utilities Commission", "list": "Grain Warehouses/Grain Buyers list", "url": "https://puc.sd.gov/warehouse/", "date": "2026-10-23", "kind": "as of"},
    "ND": {"agency": "North Dakota Department of Agriculture", "list": "Grain Storage Warehouse Licenses", "url": "https://lars.ndda.nd.gov/public/allLicenses/4/", "date": "2026-10-28", "kind": "fetched"},
    "NE-LOC": {"agency": "Nebraska Public Service Commission", "list": "Licensed Grain Warehouses (Location Capacity Report)", "url": "https://psc.nebraska.gov/grain", "date": "2026-10-28", "kind": "as of"},
    "NE-DLR": {"agency": "Nebraska Public Service Commission", "list": "Grain Dealer List", "url": "https://psc.nebraska.gov/grain", "date": "2026-09-29", "kind": "as of"},
    "NE": {"agency": "Nebraska Public Service Commission", "list": "Licensed Grain Warehouses", "url": "https://psc.nebraska.gov/grain", "date": "", "kind": "as of"},
    "IA": {"agency": "Iowa Department of Agriculture and Land Stewardship", "list": "Licensed Grain Dealers and Licensed Grain Warehouses", "url": "https://iowaagriculture.gov/administrative/licensed-businesses-ag-directories", "date": "2026-10-28", "kind": "fetched"},
    "MN": {"agency": "Minnesota Department of Agriculture", "list": "Licensing Information Search", "url": "https://www2.mda.state.mn.us/webapp/lis/default.jsp", "date": "2026-10-28", "kind": "fetched"},
}
# (substring of source_url, key): first match wins. The ND /12/ page is another list on the same ND LARS site.
SOURCE_MATCH = [("puc.sd.gov", "SD"), ("lars.ndda.nd.gov", "ND"), ("Location%20Capacity", "NE-LOC"), ("Location Capacity", "NE-LOC"),
                ("Grain%20Dealer%20List", "NE-DLR"), ("Grain Dealer List", "NE-DLR"), ("psc.nebraska.gov", "NE"), ("iowaagriculture.gov", "IA"), ("www2.mda.state.mn.us", "MN")]
REQUIRED = ("name", "town", "state", "lat", "lon")


class DirectoryError(Exception):
    pass


def haversine(a, b, c, d):
    R = 3958.7613; rad = math.pi / 180; dp = (c - a) * rad; dl = (d - b) * rad
    x = math.sin(dp / 2) ** 2 + math.cos(a * rad) * math.cos(c * rad) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def clean(s, limit=None):
    """Trim, collapse whitespace, drop control characters, cap the length."""
    s = re.sub(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029\ufeff]", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit].strip() if limit else s


def tokens(name):
    return re.sub(r"[^A-Z0-9 ]", " ", name.upper().replace("&", " AND ")).split()


def norm_name(s):
    return " ".join(w for w in tokens(s) if w not in SUFFIX_WORDS)


def is_business(name):
    """(keep?, borderline?). Keep = a strong business marker word, or two different weak ones. Anything else (a plain personal name, a family
    name with only 'Farms' or '& Sons', an unknown brand with no marker) is dropped: when unsure, drop."""
    t = set(tokens(name)); strong = t & STRONG_MARKERS; weak = t & WEAK_MARKERS
    if strong: return True, strong <= SOFT_STRONG
    if len(weak) >= 2: return True, True
    return False, bool(weak)


def parse_date(s):
    """ISO date string from YYYY-MM-DD, M/D/YYYY or 'Month D, YYYY'; '' when blank; None when present but unreadable."""
    s = clean(s)
    if not s: return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try: return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError: pass
    return None


def source_keys(urls):
    """Ordered, de-duplicated list keys for a source_url cell (one URL, or several joined by ' ; ' / '|' / newline)."""
    out = []
    for u in re.split(r"\s*(?:;|\||\n)\s*", urls or ""):
        for sub, key in SOURCE_MATCH:
            if sub in u:
                if key not in out: out.append(key)
                break
    return out


def fallback_date(r):
    """Only for rows whose source list is unknown: the first readable ISO date in source_list_date (never trusted to line up with the URLs)."""
    for part in re.split(r"\s*;\s*", r.get("source_list_date") or ""):
        d = parse_date(part)
        if d: return d
    return ""


def safe_link(url):
    """The firm's own bid page, only if it is a plain http(s) URL with a real host and no credentials; else ''."""
    u = clean(url, 400)
    if not u: return ""
    m = re.match(r"^https?://([^/?#@\s]+)(?:[/?#]\S*)?$", u, re.I)
    if not m or "." not in m.group(1) or re.search(r"[\s<>\"'\\]", u): return ""
    return u


def make_id(name, town, state):
    return hashlib.sha1(f"{norm_name(name)}|{town.upper()}|{state}".encode()).hexdigest()[:10]


def geocode(q):
    """'census_place_centroid;buyer_licence_address_may_be_office' -> ('census_place_centroid', ['office'])."""
    parts = [re.sub(r"[\s-]+", "_", p.strip().lower()) for p in (q or "").split(";") if p.strip()]
    if not parts: return "", []
    flags = []
    for f in parts[1:]:
        f = "ambiguous" if f.startswith("ambiguous_name") else FLAG_MAP.get(f, "")
        if f and f not in flags: flags.append(f)
    return parts[0], flags


def coord(v):
    try:
        x = float(clean(v))
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def build_rows(reader):
    fields = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in fields]
    if missing: raise DirectoryError("directory CSV is missing required column(s): " + ", ".join(missing))
    reader.fieldnames = fields
    v2 = any(c in fields for c in ("category", "source_list_date", "bid_page_url", "geocode_quality", "lat_display", "lon_display"))
    dropped = {k: 0 for k in ("bad_name", "not_business", "bad_town", "bad_state", "bad_coords", "not_geocoded", "outside_radius", "individual", "duplicate")}
    cleared = {"bad_link": 0, "bad_display_coords": 0}
    out, seen, total, drops, border = [], {}, 0, [], []
    for r in reader:
        if not any((v or "").strip() for v in r.values() if isinstance(v, str)): continue       # blank line
        total += 1
        name, town, st = clean(r.get("name"), NAME_MAX), clean(r.get("town"), 80), clean(r.get("state")).upper()
        def drop(reason): dropped[reason] += 1; drops.append((reason, name, town, st))
        if not name or name.upper() in PLACEHOLDER_NAMES: drop("bad_name"); continue
        keep, bl = is_business(name)
        if not keep: drop("not_business"); continue
        if not town or re.search(r"\d", town): drop("bad_town"); continue
        if not re.fullmatch(r"[A-Z]{2}", st): drop("bad_state"); continue
        gq, flags = geocode(r.get("geocode_quality"))
        if gq in NOT_FOUND_QUALITY: drop("not_geocoded"); continue
        lat, lon = coord(r.get("lat")), coord(r.get("lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): drop("bad_coords"); continue
        mi = haversine(config.CENTER_LAT, config.CENTER_LON, lat, lon)        # distance from the TRUE coordinates
        if mi > config.RADIUS_MILES + ROUND_TOLERANCE_MILES: drop("outside_radius"); continue
        cat = clean(r.get("category"), 60)
        if cat.lower() in INDIVIDUAL_CATEGORIES: drop("individual"); continue
        key = (norm_name(name), town.upper(), st)
        link = safe_link(r.get("bid_page_url"))
        if clean(r.get("bid_page_url")) and not link: cleared["bad_link"] += 1
        row = {"id": make_id(name, town, st), "name": name, "town": town, "state": st, "lat": round(lat, 5), "lon": round(lon, 5)}
        dl, dn = coord(r.get("lat_display")), coord(r.get("lon_display"))             # marker placement for co-located rows (display only)
        if dl is not None and dn is not None and -90 <= dl <= 90 and -180 <= dn <= 180 and haversine(lat, lon, dl, dn) <= 2.0:
            row["dlat"], row["dlon"] = round(dl, 5), round(dn, 5)
        elif clean(r.get("lat_display")) or clean(r.get("lon_display")): cleared["bad_display_coords"] += 1
        keys = source_keys(r.get("source_url"))
        if not keys and fallback_date(r): row["date"] = fallback_date(r)
        row.update({"mi": round(mi), "category": cat, "src": keys, "link": link, "gq": gq or "town_centroid"})
        if flags: row["fl"] = flags
        if key in seen:                                         # same firm listed twice: keep the richer row
            dropped["duplicate"] += 1; drops.append(("duplicate", name, town, st))
            old = out[seen[key]]
            for f in ("link", "category"):
                if not old[f] and row[f]: old[f] = row[f]
            for k in row["src"]:
                if k not in old["src"]: old["src"].append(k)
            continue
        if bl: border.append((name, town, st))
        seen[key] = len(out); out.append(row)
    out.sort(key=lambda x: (x["state"], x["town"].upper(), x["name"].upper(), x["id"]))
    return out, {"read": total, "kept": len(out), "dropped": dropped, "cleared": cleared, "schema_v2": v2, "drops": drops, "borderline_kept": border}


def validate_doc(doc):
    """Checks used by --check (build_dist.sh / CI-style checks run it on the COMMITTED json; they never see the source CSV). Returns a list of problems."""
    bad = []
    allowed = {"id", "name", "town", "state", "lat", "lon", "dlat", "dlon", "mi", "category", "src", "link", "gq", "fl", "date"}
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA: return [f"schema is not {SCHEMA}"]
    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows: return ["no rows"]
    if doc.get("count") != len(rows): bad.append("count does not match the number of rows")
    if set(doc) - {"schema", "format", "count", "center", "sources", "dropped", "cleared", "rows"}: bad.append("unexpected top-level field(s): " + ", ".join(sorted(set(doc) - {"schema", "format", "count", "center", "sources", "dropped", "cleared", "rows"})))
    ids = set()
    for r in rows:
        if not isinstance(r, dict) or set(r) - allowed: bad.append("row with unexpected field(s): " + str(sorted(set(r) - allowed) if isinstance(r, dict) else r)[:80]); continue
        for f in ("id", "name", "town", "state", "lat", "lon", "mi", "src", "link", "gq"):
            if f not in r: bad.append(f"row {r.get('id')} lacks {f}")
        if r.get("id") in ids: bad.append("duplicate id " + str(r.get("id")))
        ids.add(r.get("id"))
        if r.get("link") and not safe_link(r["link"]): bad.append(f"unsafe link in row {r.get('id')}")
        if not is_business(r.get("name", ""))[0]: bad.append(f"name without a business marker: row {r.get('id')}")
        if not isinstance(r.get("lat"), (int, float)) or not isinstance(r.get("lon"), (int, float)) or r.get("mi", 999) > config.RADIUS_MILES + ROUND_TOLERANCE_MILES: bad.append(f"bad position/distance in row {r.get('id')}")
        for k in r.get("src", []):
            if k not in doc.get("sources", {}): bad.append(f"row {r.get('id')} cites unknown source {k}")
    if any(re.search(r"\bcount(y|ies)\b", str(r.get(f, "")), re.I) for r in rows for f in ("town", "category", "gq", "link", "fl", "date")): bad.append("county text outside a business name")
    raw = json.dumps(doc)
    if re.search(r"licen[sc]e\s*(no|number|#)?\s*\d|permit type|NOT BIDS|[\w.+-]+@[\w-]+\.[\w.]+|\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}", raw, re.I): bad.append("notes, licence, county, email or phone text found")
    if '"notes"' in raw or '"licence' in raw or '"license' in raw: bad.append("notes/licence field found")
    return bad


def build(csv_path=DEFAULT_CSV, out_path=DEFAULT_OUT):
    p = Path(csv_path)
    if not p.is_file(): raise DirectoryError(f"directory CSV not found: {p} (the source CSV is not in git; pass --csv)")
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows, rep = build_rows(csv.DictReader(f))
    if not rows: raise DirectoryError("directory CSV produced no usable rows")
    used = sorted({k for r in rows for k in r["src"]})
    doc = {"schema": SCHEMA, "format": "v2" if rep["schema_v2"] else "v1", "count": len(rows),
           "center": {"lat": config.CENTER_LAT, "lon": config.CENTER_LON, "radius_miles": config.RADIUS_MILES},
           "sources": {k: SOURCES[k] for k in used}, "dropped": rep["dropped"], "cleared": rep["cleared"], "rows": rows}
    problems = validate_doc(doc)
    if problems: raise DirectoryError("output failed validation: " + "; ".join(problems[:5]))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return doc, rep


def write_report(path, rep):
    """LOCAL report (keep it out of git): every dropped row with its reason, and kept names that were only barely business-like."""
    lines = ["# Directory build: dropped rows and borderline names (LOCAL ONLY - contains names; never commit)", "",
             f"read {rep['read']}, kept {rep['kept']}, dropped {sum(rep['dropped'].values())}: {rep['dropped']}", "", "## Dropped (reason | name | town | state)"]
    lines += [" | ".join(d) for d in sorted(rep["drops"])]
    lines += ["", "## Borderline but KEPT (only a soft business marker such as AG/CO/GROUP, or two weak ones)"]
    lines += [" | ".join(b) for b in sorted(set(rep["borderline_kept"]))]
    Path(path).parent.mkdir(parents=True, exist_ok=True); Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build public/data/directory.json from the (git-ignored) source CSV, or --check the committed JSON.")
    ap.add_argument("--csv", default=str(DEFAULT_CSV)); ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dropped-report", default="", help="write the dropped names / borderline cases to this LOCAL file (never inside the repo's tracked tree)")
    ap.add_argument("--check", action="store_true", help="only validate the committed JSON (schema, count > 0, no notes/licence fields); needs no CSV")
    a = ap.parse_args(argv)
    if a.check:
        try:
            doc = json.loads(Path(a.out).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print("ERROR: cannot read", a.out, e, file=sys.stderr); return 1
        bad = validate_doc(doc)
        if bad: print("ERROR: directory.json invalid:", "; ".join(bad[:8]), file=sys.stderr); return 1
        print(f"directory.json OK: {doc['count']} rows, schema {doc['schema']}"); return 0
    try:
        doc, rep = build(a.csv, a.out)
    except DirectoryError as e:
        print("ERROR:", e, file=sys.stderr); return 1
    if a.dropped_report: write_report(a.dropped_report, rep)
    nd = sum(rep["dropped"].values())
    print(f"directory: {rep['kept']} of {rep['read']} rows kept ({doc['format']} format); dropped {nd} {rep['dropped']}; cleared {rep['cleared']}; wrote {a.out}"
          + (f"; report {a.dropped_report}" if a.dropped_report else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
