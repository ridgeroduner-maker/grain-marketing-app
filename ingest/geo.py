import csv, json, math
from .config import DATA_DIR, STATE_BBOX, REGION_FRACTIONS

EARTH_RADIUS_MI = 3958.7613

def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))

_gaz = None
def _gazetteer():
    global _gaz
    if _gaz is None:
        _gaz = {}
        with open(DATA_DIR / "gazetteer_places.tsv", encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                name = r["name"]
                for suf in (" city", " town", " village", " CDP", " borough"):
                    if name.endswith(suf):
                        name = name[: -len(suf)]
                        break
                # keep first (cities listed before CDPs is not guaranteed; prefer non-CDP)
                key = (r["state"], name.lower())
                if key not in _gaz or not r["name"].endswith("CDP"):
                    _gaz[key] = (float(r["lat"]), float(r["lon"]))
    return _gaz

_over = None
def _overrides():
    global _over
    if _over is None:
        p = DATA_DIR / "location_overrides.json"
        _over = json.loads(p.read_text()) if p.exists() else {}
        _over.pop("_comment", None)
    return _over

def locate(state, name, section=""):
    """Return (lat, lon, method) or None.
    method: 'override' | 'gazetteer_town' | 'approx_region_centroid'."""
    ov = _overrides()
    for k in (f"{state}|{name}|{section}", f"{state}|{name}"):
        if k in ov:
            return ov[k]["lat"], ov[k]["lon"], "override"
    if "," in name:  # "Enderlin, ND"
        town, st = [x.strip() for x in name.rsplit(",", 1)]
        hit = _gazetteer().get((st, town.lower()))
        if hit:
            return hit[0], hit[1], "gazetteer_town"
        return None
    frac = REGION_FRACTIONS.get(name.lower())
    bbox = STATE_BBOX.get(state)
    if frac and bbox:
        lat = bbox[0] + (bbox[1] - bbox[0]) * frac[1]
        lon = bbox[2] + (bbox[3] - bbox[2]) * frac[0]
        return round(lat, 4), round(lon, 4), "approx_region_centroid"
    return None
