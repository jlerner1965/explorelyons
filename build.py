#!/usr/bin/env python3
"""Build explorelyons.com into ./public.

No dependencies beyond the Python 3 standard library.

    python3 build.py            # writes public/
    python3 build.py --serve    # builds, then serves public/ on :8000

Pages live in src/pages/*.html. Each starts with a JSON block between
`<!--meta` and `-->` (title, description, path, nav, og_image ...), followed
by the page body. The layout is src/layout.html. Photographs are referenced
with {{pic name="downtown" alt="..." sizes="..." class="..." style="..."}} and
expanded to a <picture> with jpeg and webp sources. Directory rows and event
lists are rendered from src/data/*.json so every page works without script.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "public")
SITE = "https://explorelyons.com"
TODAY = dt.date.today()
REVIEWED = TODAY.strftime("%B %Y")

NAV = [
    ("explore", "/explore/", "Explore"),
    ("eat-shop", "/eat-shop/", "Eat &amp; Drink"),
    ("stay", "/stay/", "Stay"),
    ("outdoors", "/outdoors/", "Trails &amp; River"),
    ("events", "/events/", "Events"),
    ("plan-a-visit", "/plan-a-visit/", "Plan a Visit"),
    ("live-here", "/community/", "Live here"),
]

PHOTO_WIDTHS = [400, 560, 700, 1000, 1400]
PHOTO_DIMS = {}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def jpeg_size(path):
    """Width and height of a baseline/progressive JPEG, from its SOF marker."""
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return w, h
        length = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + length
    return None


def photo_dims(name):
    if name not in PHOTO_DIMS:
        largest = None
        for w in PHOTO_WIDTHS:
            p = os.path.join(SRC, "assets", "photos", f"{name}-{w}.jpg")
            if os.path.exists(p):
                largest = (w, p)
        if not largest:
            raise SystemExit(f"photo not found: {name}")
        PHOTO_DIMS[name] = (largest[0], jpeg_size(largest[1]))
    return PHOTO_DIMS[name]


def picture(attrs):
    name = attrs["name"]
    alt = attrs.get("alt", "")
    sizes = attrs.get("sizes", "(max-width: 900px) calc(100vw - 48px), 50vw")
    style = attrs.get("style", "")
    loading = attrs.get("loading", "lazy")
    maxw, (w, h) = photo_dims(name)
    widths = [x for x in PHOTO_WIDTHS if x <= maxw]
    jpg = ", ".join(f"/assets/photos/{name}-{x}.jpg {x}w" for x in widths)
    webp = ", ".join(f"/assets/photos/{name}-{x}.webp {x}w" for x in widths)
    fetch = ' fetchpriority="high"' if loading == "eager" else ""
    return (
        f'<picture><source type="image/webp" srcset="{webp}" sizes="{sizes}">'
        f'<img src="/assets/photos/{name}-{widths[0]}.jpg" srcset="{jpg}" sizes="{sizes}" '
        f'alt="{html.escape(alt, quote=True)}" width="{w}" height="{h}" loading="{loading}" decoding="async"{fetch}'
        f'{" style=" + chr(34) + html.escape(style, quote=True) + chr(34) if style else ""}></picture>'
    )


PIC_RE = re.compile(r"\{\{pic\s+([^}]*)\}\}")
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def expand_pictures(text):
    def sub(m):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        return picture(attrs)
    return PIC_RE.sub(sub, text)


# ---------------------------------------------------------------- data ----

def load_json(name):
    return json.loads(read(os.path.join(SRC, "data", name)))


def fmt_date(d):
    return d.strftime("%a, %B ") + str(d.day)


def expand_events(data, horizon_days=200):
    """One-off events plus weekly / monthly series, expanded into dated
    occurrences from today to the horizon. Returns a sorted list."""
    occ = []
    for ev in data["events"]:
        d = dt.date.fromisoformat(ev["date"])
        end = dt.date.fromisoformat(ev.get("end", ev["date"]))
        day = d
        while day <= end:
            o = dict(ev)
            o["date"] = day.isoformat()
            occ.append(o)
            day += dt.timedelta(days=1)
    horizon = TODAY + dt.timedelta(days=horizon_days)
    for s in data.get("series", []):
        day = TODAY
        while day <= horizon:
            if day.weekday() == s["weekday"]:
                ok = True
                if "weeks" in s:  # e.g. [1, 3] = first and third of the month
                    nth = (day.day - 1) // 7 + 1
                    ok = nth in s["weeks"]
                if ok and day.isoformat() not in s.get("skip", []):
                    o = dict(s)
                    o["date"] = day.isoformat()
                    occ.append(o)
            day += dt.timedelta(days=1)
    occ.sort(key=lambda o: (o["date"], o.get("sort", o.get("time", ""))))
    return occ


def event_card(o, link_mode):
    d = dt.date.fromisoformat(o["date"])
    when = f'{fmt_date(d)} &#183; {html.escape(o.get("time", "All day"))}'
    meta = " &#183; ".join(html.escape(x) for x in [o.get("organizer"), o.get("cost")] if x)
    venue = html.escape(o.get("venue", ""))
    if link_mode == "link":
        action = f'<a class="l-link" href="/events/?date={o["date"]}#cal-h">View details <span aria-hidden="true">&#8594;</span></a>'
    else:
        action = f'<button type="button" class="l-jump" data-jump="{o["date"]}" style="margin-top:auto;align-self:start;background:none;border:0;border-bottom:1px solid currentColor;color:var(--l-sky-ink);font:inherit;font-size:.9375rem;font-weight:500;cursor:pointer;padding:0 0 1px">View on the calendar <span aria-hidden="true">&#8594;</span></button>'
    return (
        f'<article class="l-up" data-event-id="{html.escape(o["id"])}" data-event-date="{o["date"]}">'
        f'<div class="l-label">{when}</div>'
        f'<h3 class="l-h3">{html.escape(o["title"])}</h3>'
        f'<div class="l-body">{venue}</div>'
        f'<div class="l-small">{meta}</div>'
        f'{action}</article>'
    )


def render_upcoming(occ, limit, link_mode):
    items = [o for o in occ if o["date"] >= TODAY.isoformat()]
    # Show a horizon of `limit` entries at build time; the script trims past
    # ones again in the browser, so keep a few spares for it to fall back on.
    spare = items[: limit + 12]
    return "".join(event_card(o, link_mode) for o in spare)


def render_directory(data):
    cats = data["categories"]
    listings = data["listings"]
    counts = {c["slug"]: 0 for c in cats}
    for l in listings:
        for c in l["categories"]:
            counts[c] += 1
    chips = [f'<label class="l-chip"><input type="radio" name="category" value="all" checked><span class="l-chip-l"><span data-chip-label>All categories</span> <span class="l-chip-n">{len(listings)}</span></span></label>']
    opts = [f'<option value="all" selected>All categories ({len(listings)})</option>']
    for c in cats:
        chips.append(f'<label class="l-chip"><input type="radio" name="category" value="{c["slug"]}"><span class="l-chip-l"><span data-chip-label>{html.escape(c["name"])}</span> <span class="l-chip-n">{counts[c["slug"]]}</span></span></label>')
        opts.append(f'<option value="{c["slug"]}">{html.escape(c["name"])} ({counts[c["slug"]]})</option>')
    groups = []
    for gi, c in enumerate(cats):
        rows = []
        for l in sorted(listings, key=lambda x: x["name"].lower()):
            if c["slug"] != l["categories"][0]:
                continue
            tags = " ".join(html.escape(next(k["name"] for k in cats if k["slug"] == s)) + ("" if i == len(l["categories"]) - 1 else " &#183;") for i, s in enumerate(l["categories"]))
            search = " ".join([l["name"], l.get("address", ""), l.get("blurb", "")] + [next(k["name"] for k in cats if k["slug"] == s) for s in l["categories"]])
            site = ""
            if l.get("url"):
                host = re.sub(r"^https?://(www\.)?", "", l["url"]).rstrip("/")
                site = f'<a class="l-link" href="{html.escape(l["url"])}" rel="noopener" style="white-space:nowrap;font-size:.875rem">{html.escape(host)} <span aria-hidden="true">&#8599;</span></a>'
            phone = f' &#183; <a href="tel:{re.sub(r"[^0-9+]", "", l["phone"])}" style="color:inherit">{html.escape(l["phone"])}</a>' if l.get("phone") else ""
            pin = f'<a class="l-link" href="#map" data-pin="{l["slug"]}" style="white-space:nowrap;font-size:.875rem">On the map <span aria-hidden="true">&#8595;</span></a>' if l.get("lat") else ""
            rows.append(
                f'<article class="l-dir-row" data-dir-row data-slug="{l["slug"]}" data-cats="{" ".join(l["categories"])}" data-search="{html.escape(search, quote=True)}">'
                f'<div><h3>{html.escape(l["name"])}</h3>'
                f'<p class="l-body" style="margin:6px 0 0;font-size:.9375rem;max-width:62ch">{html.escape(l.get("blurb", ""))}</p>'
                f'<div class="l-tags"><span>{tags}</span></div></div>'
                f'<div style="text-align:right;display:grid;gap:8px;justify-items:end">{site}{pin}</div>'
                f'<div class="l-meta">{html.escape(l.get("address", ""))}{phone}'
                f'{" &#183; " + html.escape(l["hours"]) if l.get("hours") else ""}'
                f' &#183; Checked {html.escape(l.get("checked", ""))}</div>'
                f'</article>'
            )
        if rows:
            groups.append(
                f'<details class="l-dir-group" data-dir-group {"open" if gi == 0 else ""}>'
                f'<summary style="cursor:pointer;padding:16px 0;border-top:2px solid var(--l-evergreen);font-family:var(--l-serif);font-size:1.375rem;color:var(--l-evergreen)">{html.escape(c["name"])} <span class="l-label l-label--quiet" style="margin-left:10px">{len(rows)}</span></summary>'
                f'{"".join(rows)}</details>'
            )
    return {
        "chips": "".join(chips),
        "options": "".join(opts),
        "groups": "".join(groups),
        "count": str(len(listings)),
    }


def render_stay(data):
    cards = []
    for l in data["listings"]:
        if "stay-the-night" not in l["categories"]:
            continue
        site = ""
        if l.get("url"):
            host = re.sub(r"^https?://(www\.)?", "", l["url"]).rstrip("/")
            site = f'<a class="l-link" href="{html.escape(l["url"])}" rel="noopener">{html.escape(host)} <span aria-hidden="true">&#8599;</span></a>'
        pin = f'<a class="l-link" href="#map" data-pin="{l["slug"]}">On the map <span aria-hidden="true">&#8595;</span></a>' if l.get("lat") else ""
        cards.append(
            f'<article class="l-stay-card"><h3 class="l-h3">{html.escape(l["name"])}</h3>'
            f'<div class="l-label l-label--quiet" style="margin-top:6px">{html.escape(l.get("address", ""))}</div>'
            f'<p class="l-body" style="margin:10px 0 0;font-size:.9375rem">{html.escape(l.get("blurb", ""))}</p>'
            f'<div style="display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:12px">{site}{pin}</div>'
            f'<div class="l-small" style="margin-top:8px;font-size:.8125rem">Checked {html.escape(l.get("checked", ""))}</div></article>'
        )
    return "".join(cards)


def build_pins(biz, places):
    pins = []
    for l in biz["listings"]:
        if not l.get("lat"):
            continue
        cat = l["categories"][0]
        kind = "stay" if "stay-the-night" in l["categories"] else ("culture" if cat == "venues-culture" else ("outdoor" if cat == "outdoor-recreation" else ("shop" if cat in ("shops-gifts", "arts-galleries", "grocery-provisions") else "eat")))
        pins.append({"id": l["slug"], "name": l["name"], "kind": kind, "lat": l["lat"], "lng": l["lng"], "addr": l.get("address", ""), "url": l.get("url"), "cats": l["categories"]})
    for pl in places["places"]:
        pins.append({"id": pl["id"], "name": pl["name"], "kind": pl["kind"], "lat": pl["lat"], "lng": pl["lng"], "addr": "", "url": pl.get("url"), "href": pl.get("href"), "blurb": pl.get("blurb", "")})
    return pins


def pins_for(pins, which):
    if which == "all":
        return pins
    if which == "eat":
        return [p for p in pins if p["kind"] in ("eat", "shop", "culture", "outdoor", "stay") or p["id"] in ("main-street", "sandstone-park", "lavern-park", "bohn-park", "library", "town-hall", "west-junction", "east-junction")]
    if which == "stay":
        return [p for p in pins if p["kind"] == "stay" or p["id"] in ("main-street", "lavern-park", "bohn-park", "planet-bluegrass", "sandstone-park", "west-junction", "east-junction")]
    if which == "outdoors":
        return [p for p in pins if p["kind"] in ("park", "trail") or p["id"] in ("main-street", "apple-valley-bridge", "river-gauge", "west-junction", "east-junction", "st-vrain-trailhead")]
    return pins


# --------------------------------------------------------------- pages ----

META_RE = re.compile(r"^<!--meta\s*(\{.*?\})\s*-->\s*", re.S)


def crumbs(meta):
    if meta["path"] == "/":
        return ""
    return (
        '<nav class="l-crumbs" aria-label="Breadcrumb"><div class="l-wrap"><ol>'
        '<li><a href="/">Home</a></li>'
        f'<li><span aria-current="page">{html.escape(meta["crumb"])}</span></li>'
        "</ol></div></nav>"
    )


def jsonld(meta):
    graph = [{
        "@type": "WebSite",
        "name": "ExploreLyons.com",
        "url": SITE + "/",
        "description": "An independent guide to things to do in Lyons, Colorado.",
    }, {
        "@type": "WebPage",
        "name": meta["title"],
        "url": SITE + meta["path"],
        "description": meta["description"],
    }]
    if meta["path"] == "/":
        graph.append({
            "@type": "TouristDestination",
            "name": "Lyons, Colorado",
            "url": SITE + "/",
            "description": "A sandstone town at the confluence of the North and South St. Vrain, twenty minutes north of Boulder: Main Street, the whitewater park, Hall Ranch and Planet Bluegrass.",
            "touristType": ["hikers", "mountain bikers", "families", "music fans", "anglers"],
            "geo": {"@type": "GeoCoordinates", "latitude": 40.2247, "longitude": -105.2714},
            "includesAttraction": [
                {"@type": "TouristAttraction", "name": n, "url": SITE + u} for n, u in (
                    ("Main Street historic district", "/explore/#mainstreet"),
                    ("LaVern M. Johnson Park and the whitewater park", "/outdoors/#river"),
                    ("Hall Ranch", "/outdoors/#trails"),
                    ("Planet Bluegrass", "/explore/#music"),
                    ("Lyons Redstone Museum", "/explore/#art"),
                )
            ],
        })
    if meta["path"] != "/":
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": meta["crumb"], "item": SITE + meta["path"]},
            ],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graph})


def build():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(SRC, "assets"), os.path.join(OUT, "assets"))
    for f in ("favicon.svg", "apple-touch-icon.png", "robots.txt"):
        p = os.path.join(SRC, "static", f)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(OUT, f))

    layout = read(os.path.join(SRC, "layout.html"))
    events = load_json("events.json")
    occ = expand_events(events)
    biz = load_json("businesses.json")
    places = load_json("places.json")
    directory = render_directory(biz)
    stay_cards = render_stay(biz)
    pins = build_pins(biz, places)
    upcoming_json = json.dumps([
        {k: o.get(k) for k in ("id", "title", "date", "time", "venue", "address", "organizer", "cost", "detail", "url")}
        for o in occ if o["date"] >= TODAY.isoformat()
    ], ensure_ascii=False)

    urls = []
    pages_dir = os.path.join(SRC, "pages")
    for fn in sorted(os.listdir(pages_dir)):
        if not fn.endswith(".html"):
            continue
        raw = read(os.path.join(pages_dir, fn))
        m = META_RE.match(raw)
        if not m:
            raise SystemExit(f"{fn}: missing meta block")
        meta = json.loads(m.group(1))
        body = raw[m.end():]
        body = body.replace("{{upcoming_home}}", render_upcoming(occ, 3, "link"))
        body = body.replace("{{weekend_list}}", render_upcoming(occ, 6, "link"))
        body = body.replace("{{stay_cards}}", stay_cards)
        body = re.sub(r"\{\{pins:(\w+)\}\}", lambda m: json.dumps(pins_for(pins, m.group(1)), ensure_ascii=False).replace("</", "<\\/"), body)
        body = body.replace("{{upcoming_list}}", render_upcoming(occ, 10, "jump"))
        body = body.replace("{{events_json}}", upcoming_json.replace("</", "<\\/"))
        for k, v in directory.items():
            body = body.replace("{{dir_" + k + "}}", v)
        body = body.replace("{{today_long}}", TODAY.strftime("%B ") + str(TODAY.day) + TODAY.strftime(", %Y"))
        body = expand_pictures(body)

        nav_html = "\n".join(
            f'<a href="{href}"{" class=" + chr(34) + "l-on" + chr(34) if key == meta.get("nav") else ""}>{label}</a>'
            for key, href, label in NAV
        ) + f'\n<a class="l-nav-cta{" l-on" if meta.get("nav") == "contact" else ""}" href="/contact/">Submit a listing</a>'

        page = layout
        for k, v in {
            "title": html.escape(meta["title"], quote=True),
            "description": html.escape(meta["description"], quote=True),
            "path": meta["path"],
            "og_image": meta.get("og_image", "downtown"),
            "og_alt": html.escape(meta.get("og_alt", "Main Street in Lyons, Colorado, with the red sandstone hogback behind"), quote=True),
            "head_extra": meta.get("head_extra", ""),
            "jsonld": jsonld(meta),
            "body_class": meta.get("body_class", "l-page"),
            "nav": nav_html,
            "crumbs": crumbs(meta),
            "body": body,
            "reviewed": REVIEWED,
        }.items():
            page = page.replace("{{" + k + "}}", v)
        out_path = os.path.join(OUT, meta["path"].strip("/"), "index.html") if meta["path"] != "/" else os.path.join(OUT, "index.html")
        write(out_path, page)
        if meta.get("sitemap", True):
            urls.append(meta["path"])

    # GitHub Pages and most static hosts serve /404.html for missing paths.
    shutil.copy(os.path.join(OUT, "404", "index.html"), os.path.join(OUT, "404.html"))
    shutil.rmtree(os.path.join(OUT, "404"))

    write(os.path.join(OUT, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>\n" for u in urls)
          + "</urlset>\n")
    print(f"built {len(urls)} pages into public/ ({len(occ)} event occurrences, reviewed {REVIEWED})")


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
        print("serving public/ at http://localhost:8000/")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
