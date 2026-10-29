"""USDA AMS MARS API client (needs a free key in env USDA_AMS_API_KEY).

STATUS: written from the public MARS docs + a published sample response row
(see tests/test_mars_normalize.py). NOT yet exercised against the live API
because no key was available during development. Auth = HTTP Basic, API key as
username, empty password.  Field names below (note the spaces: 'price Min')
are as published in AMS's own example output."""
import base64, json, os, re, datetime, urllib.parse, urllib.request
from .config import MARS_BASE, API_KEY_ENV, COMMODITY_RULES
from .parse_pdf import MONTH

class NoApiKey(RuntimeError):
    pass

def _key():
    k = os.environ.get(API_KEY_ENV, "").strip()
    if not k:
        raise NoApiKey(f"{API_KEY_ENV} is not set")
    return k

def _get(url, timeout=60):
    tok = base64.b64encode(f"{_key()}:".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + tok, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_report_detail(slug, date_iso=None, limit=100000):
    """Rows of 'Report Detail' for one slug. date_iso 'YYYY-MM-DD' => that report_date."""
    q = ""
    if date_iso:
        d = datetime.date.fromisoformat(date_iso)
        q = f"report_date={d.strftime('%m/%d/%Y')}"
    url = f"{MARS_BASE}/reports/{slug}/" + urllib.parse.quote("Report Detail") + "?" + urllib.parse.urlencode({"q": q, "limit": limit})
    data = _get(url)
    if isinstance(data, list):           # API returns a list of section objects
        rows = []
        for sec in data:
            if sec.get("reportSection") == "Report Detail":
                rows += sec.get("results", [])
        return rows
    return data.get("results", [])

def fetch_report_range(slug, start_iso, end_iso):
    """Backfill: report_date between start and end (MM/DD/YYYY;MM/DD/YYYY range syntax per MARS docs)."""
    s = datetime.date.fromisoformat(start_iso).strftime("%m/%d/%Y")
    e = datetime.date.fromisoformat(end_iso).strftime("%m/%d/%Y")
    url = f"{MARS_BASE}/reports/{slug}/" + urllib.parse.quote("Report Detail") + "?" + urllib.parse.urlencode({"q": f"report_begin_date={s}:{e}"})
    data = _get(url)
    rows = []
    for sec in (data if isinstance(data, list) else [data]):
        rows += sec.get("results", [])
    return rows

def _commodity(c, grade):
    h = f"{c or ''} {grade or ''}".lower()
    for name, pat in COMMODITY_RULES:
        if re.search(pat, h):
            return name
    return None

def normalize_rows(rows, slug, title, state):
    """MARS rows -> same dict shape as parse_pdf.parse_report()['bids']."""
    out, skipped = [], []
    for r in rows:
        com = _commodity(r.get("commodity"), r.get("grade"))
        if not com:
            continue
        loc = (r.get("trade_loc") or r.get("location_City") or "").strip()
        if r.get("location_City") and r.get("location_State"):
            loc = f"{r['location_City']}, {r['location_State']}"
        d = datetime.datetime.strptime(r["report_date"], "%m/%d/%Y").date().isoformat()
        lo, hi = r.get("price Min"), r.get("price Max")
        if lo is None and hi is None:
            continue
        lo = lo if lo is not None else hi
        hi = hi if hi is not None else lo
        fut = r.get("basis Min Futures Month") or ""
        m = re.search(r"\(([A-Z])\)", fut)
        mh = re.search(r"\(([A-Z])\)", r.get("basis Max Futures Month") or "") or m
        prot = r.get("protein") or ""
        row = {
            "commodity": com, "heading": r.get("grade") or r.get("commodity"), "location": loc,
            "section": r.get("delivery_point") or "", "sale_type": r.get("sale Type") or "Bid",
            "protein": str(prot) if prot else "",
            "grade": " ".join(x for x in [r.get("grade"), r.get("commodity"), r.get("class")] if x),
            "bid_low": float(lo), "bid_high": float(hi),
            "bid_avg": r.get("avg_price"), "unit": r.get("price_unit") or "",
            "basis_low": r.get("basis Min"), "basis_high": r.get("basis Max"),
            "basis_unit": r.get("basis_unit") or "",
            "basis_futures_month": MONTH.get(m.group(1), "") if m else "",
            "basis_low_month": MONTH.get(m.group(1), "") if m else "", "basis_high_month": MONTH.get(mh.group(1), "") if mh else "",
            "freight": f"{r.get('freight') or ''}-{r.get('trans_mode') or ''}".strip("-"),
            "delivery": "Current" if (r.get("current") or "").lower() == "yes" else (r.get("delivery_start") or "Deferred"),
            "report_date": d, "source_report": f"AMS_{slug}", "source_title": title,
            "state": r.get("market_location_state") or state,
        }
        if not loc:
            skipped.append(("no location", row)); continue
        out.append(row)
    return out, skipped
