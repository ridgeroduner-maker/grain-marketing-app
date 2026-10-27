"""Static configuration for the grain ingest. Edit here, not in code."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("GRAIN_DB", DATA_DIR / "grain.db"))

# Gann Valley, SD (approx) and service radius.
CENTER_LAT, CENTER_LON = 44.0, -98.9
RADIUS_MILES = 300.0

MARS_BASE = "https://marsapi.ams.usda.gov/services/v1.2"
PDF_URL = "https://www.ams.usda.gov/mnreports/ams_{slug}.pdf"   # public, no key
API_KEY_ENV = "USDA_AMS_API_KEY"

# AMS Market News report slugs we ingest. `state` = default state for rows whose
# location is a region name (e.g. "North Central"). state=None => the location
# text already carries "Town, ST" (national reports).
# Slugs verified to exist & be current on 2026-10-27 (PDF fetched, 200 OK).
REPORTS = [
    {"slug": 3186, "title": "South Dakota Daily Grain Bids",            "state": "SD"},
    {"slug": 3878, "title": "North Dakota Daily Grain Bids",            "state": "ND"},
    {"slug": 3225, "title": "Nebraska Daily Elevator Grain Bids",       "state": "NE"},
    {"slug": 3049, "title": "Southern Minnesota Daily Grain Bids",      "state": "MN"},
    {"slug": 2850, "title": "Iowa Daily Cash Grain Bids",               "state": "IA"},
    {"slug": 2887, "title": "National Daily Sunflower, Canola, Millet, and Flaxseed Report", "state": None},
]
# Candidates checked but outside the 300-mile circle (kept for reference):
#   2771 Montana, 3239 Wyoming (SE corner ~330 mi), 2912 Colorado, 3223 KC wheat.

# Our five commodities. Order matters: first match wins. Matched against the
# commodity heading line in the report, e.g. "US #1 Hard Red Spring Wheat (Bulk)".
COMMODITY_RULES = [
    ("sunflowers",   r"sunflower"),
    ("spring_wheat", r"spring wheat"),
    ("winter_wheat", r"winter wheat"),
    ("corn",         r"\bcorn\b"),
    ("soybeans",     r"\bsoybeans?\b"),
]

# Approximate bounding boxes (lat_min, lat_max, lon_min, lon_max) used ONLY to
# place AMS *region* names ("North Central" ...) on the map.
STATE_BBOX = {
    "SD": (42.48, 45.94, -104.06, -96.44),
    "ND": (45.94, 49.00, -104.05, -96.55),
    "NE": (40.00, 43.00, -104.05, -95.31),
    "MN": (43.50, 49.38, -97.24, -89.49),
    "IA": (40.38, 43.50, -96.64, -90.14),
}
# (east_fraction, north_fraction) inside the state bbox. APPROXIMATION of the
# AMS trade regions (AMS defines them by county; see README open questions).
REGION_FRACTIONS = {
    "northwest": (0.20, 0.80), "north central": (0.50, 0.80), "northeast": (0.80, 0.80),
    "west": (0.15, 0.50), "central": (0.50, 0.50), "east central": (0.75, 0.50), "east": (0.88, 0.50),
    "southwest": (0.20, 0.20), "south central": (0.50, 0.20), "south": (0.50, 0.15), "southeast": (0.80, 0.20),
}
