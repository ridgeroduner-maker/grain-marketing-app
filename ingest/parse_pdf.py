"""Parse AMS Market News 'Daily Grain Bids' PDFs (public, no API key) via pdftotext -layout.

Verified against the live 2026-10-26 reports 3186, 3878, 3225, 3049, 2850, 2887.
Requires the `pdftotext` binary (poppler-utils)."""
import re, subprocess, datetime, urllib.request
from .config import PDF_URL, PUBLISHED_URL, COMMODITY_RULES

MONTH = {"F": "Jan", "G": "Feb", "H": "Mar", "J": "Apr", "K": "May", "M": "Jun",
         "N": "Jul", "Q": "Aug", "U": "Sep", "V": "Oct", "X": "Nov", "Z": "Dec"}

def fetch_pdf(slug, timeout=60):
    req = urllib.request.Request(PDF_URL.format(slug=slug), headers={"User-Agent": "Mozilla/5.0 grain-app"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

_TZ_OFFSETS = {"MDT": -6, "MST": -7, "CDT": -5, "CST": -6, "EDT": -4, "EST": -5, "PDT": -7, "PST": -8}

def parse_published(s):
    """'2026-10-26 13:28:06 MDT' (MARS publishedDate) -> '2026-10-26T14:28:06-05:00' in America/Chicago, or None."""
    import zoneinfo
    m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ([A-Z]{3})$", (s or "").strip())
    if not m or m.group(2) not in _TZ_OFFSETS:
        return None
    dt = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=datetime.timezone(datetime.timedelta(hours=_TZ_OFFSETS[m.group(2)])))
    return dt.astimezone(zoneinfo.ZoneInfo("America/Chicago")).isoformat(timespec="seconds")

def fetch_posted_at(slug, report_date=None, timeout=30):
    """When USDA published the report, via the keyless public MARS metadata endpoint (no prices, no key; spec S11).
    Returns ISO string (America/Chicago) or None. If report_date (YYYY-MM-DD) is given, the metadata must be for that date."""
    import json
    try:
        req = urllib.request.Request(PUBLISHED_URL.format(slug=slug), headers={"User-Agent": "Mozilla/5.0 grain-app"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reps = json.load(r).get("reports") or []
        for rep in reps:
            if report_date and rep.get("reportBeginDate") != report_date:
                continue
            return parse_published(rep.get("publishedDate"))
    except Exception:
        return None
    return None

def pdf_to_text(pdf_bytes):
    p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf_bytes, capture_output=True, check=True)
    return p.stdout.decode("utf-8", "replace")

_CHG = r"(?:UNCH|UP \d+\.\d+|DN \d+\.\d+)"
ROW_TAIL = re.compile(
    r"(?P<price>\d+\.\d+(?:-\d+\.\d+)?)\s+"
    r"(?P<pchg>" + _CHG + r"(?:-" + _CHG + r")?)\s+"
    r"(?P<avg>\d+\.\d+)(?:\s+(?P<ya>\d+\.\d+))?\s+"
    r"(?P<freight>(?:DLVD|FOB|CIF)-[A-Z/]+)\s+(?P<delivery>\S.*?)\s*$")
ROW_HEAD = re.compile(r"^\s*(?P<loc>.*?)\s*\b(?P<sale>Bid|Offer|Trade)\b\s*(?P<mid>.*)$")
BASIS = re.compile(r"(-?\d+(?:\.\d+)?)([A-Z])(?: to (-?\d+(?:\.\d+)?)([A-Z]))?")
PROTEIN = re.compile(r"^(Ordinary|\d+(?:\.\d)?%)\s*")
FUT_ROW = re.compile(r"^\s*(CBOT|KCBT|MGE)\s+(.+?)\s{2,}(\d.*)$")
FUT_CELL = re.compile(r"(\d+(?:\.\d+)?)\s*\(([A-Za-z]{3} \d\d)\)")

def _commodity(heading):
    h = heading.lower()
    for name, pat in COMMODITY_RULES:
        if re.search(pat, h):
            return name
    return None

def _range(s):
    if "-" in s:
        a, b = s.split("-")
        return float(a), float(b)
    return float(s), float(s)

def parse_report(text, slug, title, state):
    """Return dict(report_date, bids=[...], futures=[...], skipped=[...])."""
    out = {"report_date": None, "bids": [], "futures": [], "skipped": []}
    m = re.search(r"Grain Report for (\d\d)/(\d\d)/(\d{4})", text)
    if not m:
        raise ValueError(f"report {slug}: no 'Grain Report for MM/DD/YYYY' line")
    out["report_date"] = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    status = "Final" if re.search(r"Grain Report for \S+ - Final", text) else "Preliminary"
    out["status"] = status

    heading = None          # raw commodity heading
    commodity = None        # our name or None (ignored)
    section = ""            # buyer type
    basis_unit = ""
    price_unit = ""
    has_protein = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        fm = FUT_ROW.match(line)
        if fm and "(" in fm.group(3):
            exch, com, rest = fm.groups()
            for price, label in FUT_CELL.findall(rest):
                out["futures"].append({"exchange": exch, "commodity": com.strip(),
                                       "contract": label, "settle_cents": float(price)})
            continue
        if re.search(r"\(Bulk\)\s*$|\(Bagged\)\s*$", line) and "Region" not in line:
            heading = line.strip()
            commodity = _commodity(heading)
            continue
        if re.match(r"^\s*(Country Elevators|Terminal Elevators|Terminals/Mills/Processors|Mills and Processors|Terminals|Processors)\b.*-", line):
            section = line.strip().split(" - ")[0].strip()
            continue
        if "Region/Location" in line:
            has_protein = "Protein" in line
            bu = re.search(r"Basis \(([^)]*)\)", line)
            pu = re.search(r"Price\(([^)]*)\)", line)
            basis_unit = bu.group(1) if bu else ""
            price_unit = pu.group(1) if pu else ""
            continue
        t = ROW_TAIL.search(line)
        if not t or heading is None:
            continue
        h = ROW_HEAD.match(line[: t.start()] + " ")
        if not h:
            continue
        loc, sale, mid = h.group("loc").strip(), h.group("sale"), h.group("mid").strip()
        if commodity is None:
            continue  # oats, sorghum, canola ... outside scope
        protein = ""
        pm = PROTEIN.match(mid)
        if pm:
            protein = pm.group(1)
            mid = mid[pm.end():]
        bm = BASIS.search(mid)
        b_lo = b_hi = None
        b_code = ""
        if bm:
            b_lo = float(bm.group(1))
            b_hi = float(bm.group(3)) if bm.group(3) is not None else b_lo
            b_code = bm.group(2)
        lo, hi = _range(t.group("price"))
        row = {
            "commodity": commodity, "heading": heading, "location": loc, "section": section,
            "sale_type": sale, "protein": protein,
            "grade": re.sub(r"\s*\((Bulk|Bagged)\)\s*$", "", heading),
            "bid_low": lo, "bid_high": hi, "bid_avg": float(t.group("avg")),
            "unit": price_unit, "basis_low": b_lo, "basis_high": b_hi,
            "basis_unit": basis_unit if bm else "", "basis_futures_month": MONTH.get(b_code, ""),
            "freight": t.group("freight"), "delivery": t.group("delivery"),
            "report_date": out["report_date"], "source_report": f"AMS_{slug}",
            "source_title": title, "state": state,
        }
        if not loc:
            out["skipped"].append(("no location", row))
            continue
        out["bids"].append(row)
    return out
