"""Draft Terms of Use / Privacy Policy: pages exist and carry the DRAFT notice, required sections and placeholders; the footer links to
them; build_dist.sh ships them; and what the Privacy Policy says is checked against the code (storage, geolocation, cookies, external requests)."""
import html, os, re, shutil, subprocess, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"
DRAFT = "DRAFT - not legal advice, have a lawyer review"
# Hosts that may appear as plain links (or, for the OSM tile URL, as the localhost-only dev tile source) in the app's own files.
LINK_HOSTS = {"mymarketnews.ams.usda.gov", "www.openstreetmap.org", "openstreetmap.org", "opendatacommons.org", "github.com", "leafletjs.com",
              "operations.osmfoundation.org", "protomaps.com", "www.chartjs.org", "www.w3.org", "docs.github.com", "x.invalid", "example.com",
              # Directory layer: the state agency lists named in the footer / Terms credits (plain links; nothing is loaded from them)
              "puc.sd.gov", "lars.ndda.nd.gov", "psc.nebraska.gov", "iowaagriculture.gov", "www2.mda.state.mn.us"}
DEV_ONLY_TILE_HOST = "tile.openstreetmap.org"      # only in mapmode.js, used only on localhost with MAP_TILES_URL empty
TRACKERS = ["googleapis.com", "gstatic.com", "google-analytics", "googletagmanager", "doubleclick.net", "facebook.net", "cloudflareinsights", "jsdelivr.net",
            "unpkg.com", "cdnjs.", "bootstrapcdn", "fontawesome", "typekit", "hotjar", "segment.io", "segment.com", "mixpanel", "sentry.io", "plausible.io", "matomo", "fullstory"]
URL = re.compile(r"(?:https?:)?//([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:[/:?#\"'\s)<>]|$)")


def read(p): return Path(p).read_text(encoding="utf-8")
def app_files(base):                                    # the app's own (non-vendor, non-test) text files
    return [p for p in Path(base).rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".css", ".webmanifest") and "vendor" not in p.parts
            and ".test." not in p.name and "data-sample" not in p.parts and "tiles" not in p.parts]


class LegalPages(unittest.TestCase):
    pages = {"terms.html": ["short", "info-only", "prices", "distance", "futures", "verify", "credits", "warranty", "liability", "law", "directory", "contact"],
             "privacy.html": ["short", "collect", "device", "location", "notifications", "nothird", "directory", "host", "sharing", "kids", "changes"]}

    def test_pages_exist_with_draft_notice_at_top(self):
        for name in self.pages:
            h = read(PUBLIC / name)
            body = h.split("<body", 1)[1]
            self.assertIn(DRAFT, body[:1500], name)               # in the first screenful, before any content
            self.assertIn('class="banner draft"', body[:1500])
            self.assertIn('<meta name="viewport"', h)             # mobile friendly
            self.assertIn('href="style.css"', h)                  # same site styling
            self.assertNotIn("<script", h)                        # static, no JS at all

    def test_required_sections(self):
        for name, ids in self.pages.items():
            h = read(PUBLIC / name)
            for i in ids: self.assertIn(f'id="{i}"', h, f"{name} #{i}")

    def test_terms_content(self):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", read(PUBLIC / "terms.html")))
        for must in ["information only", "trading advice", "financial", "marketing advice", "USDA", "Market News", "delayed", "preliminary", "stale", "wrong",
                     "straight-line", "approximate", "futures", "not live quotes", "CME Group", "not affiliated with", "endorsed",
                     "no warranty", "is not liable", "Call your elevator", "OpenStreetMap", "Protomaps", "Leaflet"]:
            self.assertIn(must.lower(), t.lower(), must)

    def test_privacy_content(self):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", read(PUBLIC / "privacy.html"))).lower()
        for must in ["no accounts", "local storage", "indexeddb", "use my location", "never sent", "no cookies", "no analytics", "github pages", "logs",
                     "same site", "clear this site"]:
            self.assertIn(must, t, must)

    def test_placeholders_present_and_nothing_invented(self):
        for name in self.pages:
            h = read(PUBLIC / name)
            self.assertNotIn("[[EFFECTIVE DATE]]", h, name)                                # set by the owner's instruction (Oct 28, 2026)
            self.assertIn("Effective date: October 28, 2026 &middot;", h, name)
            for filled in ("[[OWNER LEGAL NAME]]", "[[CONTACT EMAIL]]"): self.assertNotIn(filled, h, f"{name} {filled} should be filled")
            self.assertIn("Ridge Roduner (an individual)", h)
            self.assertIn('<a href="mailto:ridgeroduner@gmail.com">ridgeroduner@gmail.com</a>', h)
            self.assertEqual(set(re.findall(r"[A-Za-z0-9._+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", h)), {"ridgeroduner@gmail.com"}, f"{name}: only the owner-supplied email")
            dates = re.findall(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d", re.sub(r"<[^>]+>", " ", h))
            self.assertEqual(dates[0], "October 28, 2026", f"{name}: the effective date (owner-set) comes first")
            # the only other dates are the Directory source-list dates from the reviewer's attribution text (terms section 6), nothing invented
            self.assertLessEqual(set(dates), {"October 28, 2026", "October 23, 2026", "September 29, 2026"} if name == "terms.html" else {"October 28, 2026"}, f"{name}: {dates}")
            if name == "privacy.html": self.assertEqual(dates, ["October 28, 2026"])
        # answered by Ridge (via Bobby): governing state and host are now facts, so their placeholders must be gone; lawyer notes and the rest stay
        terms, priv = read(PUBLIC / "terms.html"), read(PUBLIC / "privacy.html")
        for gone in ("[[GOVERNING STATE", "[[HOST", "TBD"):
            self.assertNotIn(gone, terms); self.assertNotIn(gone, priv)
        self.assertIn("[[LAWYER: courts / venue / dispute process, if any]]", terms)
        self.assertIn("[[LAWYER:", terms); self.assertIn("[[LAWYER:", priv); self.assertIn("[[OWNER TO CONFIRM", priv)

    def test_owner_email_only_on_legal_pages(self):
        for p in app_files(PUBLIC):
            if p.name in ("terms.html", "privacy.html"): continue
            if p.name in ("index.html", "directory.js"):          # owner-approved for the Directory "Report a correction" wording only
                self.assertEqual(set(re.findall(r"[A-Za-z0-9._+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", read(p))), {"ridgeroduner@gmail.com"}, p.name)
                self.assertIn("subject=Directory%20correction", read(p)); continue
            self.assertNotIn("ridgeroduner", read(p).lower(), p.name)

    def test_only_expected_placeholders_remain(self):
        allowed = {"terms.html": {"[[double square brackets]]", "[[OWNER TO CONFIRM WITH LAWYER: whether showing futures settlements needs any permission from CME Group; the owner has decided to show them with USDA credit]]"},
                   "privacy.html": {"[[double square brackets]]"}}
        for name in self.pages:
            found = set(re.findall(r"\[\[[^\]]+\]\]", read(PUBLIC / name)))
            for ph in found:
                self.assertTrue(ph in allowed[name] or ph.startswith(("[[LAWYER", "[[OWNER TO CONFIRM")), f"{name}: unexpected placeholder {ph}")
            self.assertNotIn("[[EFFECTIVE DATE]]", found)

    def test_south_dakota_and_github_pages_facts(self):
        terms = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", read(PUBLIC / "terms.html")))
        self.assertRegex(terms, r"governed by the laws of the State of South Dakota")
        priv = read(PUBLIC / "privacy.html"); host = priv.split('id="host"', 1)[1].split("</section>", 1)[0]
        hosttext = re.sub(r"<[^>]+>", "", host)
        self.assertIn("is hosted on GitHub Pages", hosttext); self.assertIn("IP address", hosttext); self.assertIn("under its own policy", hosttext)
        self.assertIn('href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"', host)

    def test_footer_links_and_cross_links(self):
        idx = read(PUBLIC / "index.html")
        foot = idx.split("<footer>", 1)[1].split("</footer>", 1)[0]
        self.assertIn('href="terms.html"', foot); self.assertIn('href="privacy.html"', foot)
        self.assertIn('href="privacy.html"', read(PUBLIC / "terms.html")); self.assertIn('href="terms.html"', read(PUBLIC / "privacy.html"))

    def test_service_worker_precaches_pages_and_version_bumped(self):
        sw = read(PUBLIC / "sw.js")
        shell = sw.split("const SHELL = [", 1)[1].split("];", 1)[0]
        self.assertIn("'terms.html'", shell); self.assertIn("'privacy.html'", shell)
        self.assertRegex(sw, r"const VERSION = 'grain-v(1\d|[2-9]\d)'")      # bumped when precached files changed (v9 -> v10 for the Directory layer)
        for f in re.findall(r"'([^']+)'", shell):                                # every precached file exists (addAll fails the whole install otherwise)
            if f != "./": self.assertTrue((PUBLIC / f).exists(), f)


class DirectoryLegalText(unittest.TestCase):
    """The reviewer's wording (review doc sections 4 and 5) is in the pages, and what the pages promise is true of the code."""
    @classmethod
    def setUpClass(cls):
        cls.terms = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", read(PUBLIC / "terms.html")))).replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        cls.priv = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", read(PUBLIC / "privacy.html")))).replace("\u2019", "'")
        cls.index = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", read(PUBLIC / "index.html")))).replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')

    def test_terms_edits(self):
        for w in ["The optional Directory layer lists licensed grain firms from state lists; it contains names and towns only, no prices, and is not a source of any bid in this app.",
                  "A firm named on the Directory layer near a region's pin is not necessarily part of that region's report.",
                  "These agencies did not review, verify or endorse this app. Company names belong to their owners and are used only to identify the firm.",
                  "or pretend it is yours or that USDA, CME Group, a state agency or a listed company runs or endorses it. Please do not use the Directory layer to build mailing, calling or sales lists; the South Dakota Public Utilities Commission says its list \"should not be used for solicitation.\"",
                  "Directory layer and links to other websites", "A listing is not a bid, an offer to buy, a recommendation, or a statement that the firm is open, buying, or taking part in this app. Licenses can lapse and lists change.",
                  "we are not responsible for its content, prices, cookies or tracking, and a link does not mean the firm endorses this app or we endorse the firm. To correct or remove a listing, email ridgeroduner@gmail.com.",
                  "Grain Bids is not affiliated with or endorsed by USDA, CME Group, any state agency, or any company named in the Directory.",
                  "DRAFT - not legal advice, have a lawyer review"]:
            self.assertIn(w, self.terms, w)
        self.assertNotIn("not affiliated with or endorsed by USDA or CME Group.", self.terms.replace("not affiliated with, endorsed by, sponsored by or approved by USDA or CME Group", ""))

    def test_privacy_edits(self):
        for w in ["Directory links to other websites open only if you tap them; those sites may use cookies and tracking that we do not control.",
                  "(for example to USDA, OpenStreetMap, state agency lists, and company websites in the Directory) only open if you tap them.",
                  "We do not control them and do not receive anything from them. We ask your browser not to tell them which page you came from.",
                  "If you email us (for example to correct a listing), we receive your email address and message, and use them only to reply and fix the listing.",
                  "The Directory lists businesses from public state lists. Names that look like an individual's personal name are left out. If you are listed and want a correction or removal, email ridgeroduner@gmail.com.",
                  "Grain Bids is not affiliated with or endorsed by USDA, CME Group, any state agency, or any company named in the Directory.",
                  "DRAFT - not legal advice, have a lawyer review"]:
            self.assertIn(w, self.priv, w)

    def test_footer_attribution_in_index_and_terms_is_identical_and_complete(self):
        for name, txt in (("index", self.index), ("terms", self.terms)):
            for w in ["South Dakota Public Utilities Commission, Grain Warehouses/Grain Buyers list, as of October 23, 2026 (https://puc.sd.gov/warehouse/)",
                      "North Dakota Department of Agriculture, Grain Storage Warehouse Licenses (https://lars.ndda.nd.gov/public/allLicenses/4/), undated list, fetched October 28, 2026",
                      "Nebraska Public Service Commission, Licensed Grain Warehouses (Location Capacity Report), as of October 28, 2026, and Grain Dealer List, as of September 29, 2026 (https://psc.nebraska.gov/grain)",
                      "Iowa Department of Agriculture and Land Stewardship, Licensed Grain Dealers and Licensed Grain Warehouses (https://iowaagriculture.gov/administrative/licensed-businesses-ag-directories), undated list, fetched October 28, 2026",
                      "Minnesota Department of Agriculture, Licensing Information Search (https://www2.mda.state.mn.us/webapp/lis/default.jsp), undated list, fetched October 28, 2026",
                      "Compiled from public lists by the app owner. Not reviewed or endorsed by these agencies; may be out of date or incomplete; a license is not a bid or an offer to buy. List dates above, locations approximate."]:
                self.assertIn(w, txt, f"{name}: {w[:60]}")
        self.assertIn("Directory (names and towns only, not prices; not bids): South Dakota", self.index)
        self.assertNotIn("[date]", self.index); self.assertNotIn("[date]", self.terms)

    def test_layer_labels_and_notices_on_the_page(self):
        for w in ["Directory only, NOT bids", "Licensed grain buyers and warehouses from state lists. Names and towns only. No prices.",
                  "For farmers' information only. Do not use this directory to build mailing, calling or sales lists. South Dakota's Public Utilities Commission says its list \"should not be used for solicitation.\"",
                  "Wrong name, wrong town, closed, or a firm that wants to be corrected or removed? Email ridgeroduner@gmail.com with the firm name and town. Please don't send personal details.",
                  "Call your elevator to confirm.", "not offers from any elevator"]:
            self.assertIn(w, self.index, w)

    def test_promises_match_code(self):
        sw = read(PUBLIC / "sw.js"); d = read(PUBLIC / "directory.js")
        self.assertIn("'directory.js'", sw.split("const SHELL = [", 1)[1].split("];", 1)[0])
        # directory.json is fetched only when the layer is turned on, and the service worker's data path (network-first, saved copy) caches it
        self.assertEqual(re.findall(r"fetch\(([^)]*)\)", d), ["'data/directory.json'"])
        self.assertIn("cacheable(r)", sw); self.assertNotIn("directory.json", sw)                  # not precached: only cached once used
        # "We ask your browser not to tell them which page you came from": site-wide meta referrer + per-link referrerpolicy
        for n in ("index.html", "terms.html", "privacy.html"): self.assertIn('<meta name="referrer" content="no-referrer">', read(PUBLIC / n), n)
        self.assertIn('rel="noopener noreferrer" referrerpolicy="no-referrer"', d)
        self.assertNotIn("localStorage", d); self.assertNotIn("document.cookie", d)


class BuiltOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = PUBLIC / "data-sample"; cls.made = not cls.sample.exists()
        r = subprocess.run(["bash", str(ROOT / "build_dist.sh")], cwd=ROOT, capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if k != "MAP_TILES_KEY"})
        assert r.returncode == 0, r.stderr
        cls.dist = ROOT / "dist"

    @classmethod
    def tearDownClass(cls): shutil.rmtree(ROOT / "dist", ignore_errors=True)

    def test_build_dist_includes_pages_identically(self):
        for name in ("terms.html", "privacy.html"):
            self.assertTrue((self.dist / name).exists(), name)
            self.assertEqual(read(self.dist / name), read(PUBLIC / name))
        self.assertIn('href="terms.html"', read(self.dist / "index.html"))

    def test_built_html_loads_nothing_from_outside(self):
        for p in self.dist.glob("*.html"):
            h = read(p)
            for m in re.finditer(r"""<(?:script|img|link|iframe|source|audio|video|embed|object)\b[^>]*?\b(?:src|href|data)=["']([^"']+)["']""", h):
                tag = m.group(0)
                if tag.startswith("<a "): continue
                self.assertFalse(re.match(r"(?:https?:)?//", m.group(1)), f"{p.name}: external resource {m.group(1)}")
            self.assertNotRegex(h, r"@import\s+url\(\s*['\"]?(?:https?:)?//")
            self.assertNotRegex(h, r"url\(\s*['\"]?(?:https?:)?//")
            self.assertNotIn("<iframe", h); self.assertNotRegex(h, r"<form[^>]*\baction=")      # the alert form is local only: no action URL
            for host in URL.findall(h): self.assertIn(host, LINK_HOSTS, f"{p.name}: unexpected host {host} (anchors only)")

    def test_app_files_only_reference_expected_hosts(self):
        for p in app_files(self.dist):
            txt = read(p)
            for host in set(URL.findall(txt)):
                ok = host in LINK_HOSTS or (host == DEV_ONLY_TILE_HOST and p.name == "mapmode.js")
                self.assertTrue(ok, f"{p.name}: unexpected host {host}")
        css = read(self.dist / "style.css"); self.assertNotIn("url(http", css); self.assertNotIn("@import", css)

    def test_no_trackers_cdns_or_fonts_anywhere_including_vendor(self):
        for p in self.dist.rglob("*"):
            if not p.is_file() or p.suffix not in (".html", ".js", ".css", ".webmanifest", ".json"): continue
            low = read(p).lower()
            for t in TRACKERS: self.assertNotIn(t, low, f"{p.relative_to(self.dist)} mentions {t}")

    def test_code_matches_privacy_policy(self):
        app = read(PUBLIC / "app.js"); core = read(PUBLIC / "alerts-core.js"); sw = read(PUBLIC / "sw.js")
        everything = app + core + sw + read(PUBLIC / "mapmode.js") + read(PUBLIC / "index.html") + read(PUBLIC / "directory.js")
        # cookies: never read or written
        self.assertNotIn("document.cookie", everything); self.assertNotIn("cookieStore", everything)
        # storage: exactly the two localStorage keys the policy describes; IndexedDB 'grain-app' copy for the worker; no sessionStorage
        self.assertEqual(set(re.findall(r"localStorage\.(?:getItem|setItem|removeItem)\('([^']+)'", app)), {"grain.me", "grain.alerts"})
        self.assertNotIn("sessionStorage", everything); self.assertIn("indexedDB.open('grain-app'", core)
        # geolocation: one call, inside locate(), which only the "Use my location" button triggers; result goes to localStorage, not the network
        self.assertEqual(app.count("getCurrentPosition"), 1); self.assertEqual(app.count("navigator.geolocation"), 2)
        loc = app.split("function locate()", 1)[1].split("// ---------- alerts", 1)[0]
        self.assertNotIn("fetch(", loc); self.assertNotIn("sendBeacon", loc); self.assertIn("localStorage.setItem('grain.me'", loc)
        self.assertEqual(re.findall(r"\blocate\(\)", app), ["locate()"])                       # only the definition; no automatic call
        self.assertIn("$('btnLocate').onclick = locate", app)
        # notifications: permission requested only from a button click
        self.assertEqual(app.count("requestPermission"), 1); self.assertIn("$('btnNotif').onclick", app)
        # network: no beacons/sockets/XHR; fetches are same-site relative (data files, tile-file Range probe) - none carries user data
        for bad in ("sendBeacon", "XMLHttpRequest", "WebSocket", "EventSource", "navigator.share"): self.assertNotIn(bad, everything)
        for m in re.findall(r"fetch\(([^)]*)\)", app + sw): self.assertNotRegex(m.split(",")[0].strip(), r"^['\"`]?https?:", m)
        self.assertNotIn("state.me", "".join(re.findall(r"fetch\([^)]*\)", app)))
        self.assertNotIn("alerts", "".join(re.findall(r"fetch\([^)]*\)", app)).lower())
        self.assertIn("endsWith('.pmtiles')", sw)                                                  # map tile file is never cached


if __name__ == "__main__":
    unittest.main()
