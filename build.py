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
import hashlib
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
ICS_STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# Where the contact form posts. Formspree, Basin, Formsubmit and the rest all
# accept a plain POST of the form fields, so any of them works here: paste the
# endpoint URL and both paths start working at once -- fetch() for visitors
# with scripting, and an ordinary form POST (landing on /thanks/) for those
# without. Left empty, the form says plainly that nothing was sent and offers
# the editor's address instead, rather than pretending to deliver.
FORM_ENDPOINT = ""

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


def og_image_url(name):
    """Absolute URL of the largest rendered width of a photo. Not every photo
    reaches 1400px, so the width is looked up rather than assumed: a card
    pointing at a width that was never written is a broken share image."""
    maxw, _ = photo_dims(name)
    return f"{SITE}/assets/photos/{name}-{maxw}.jpg"


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


ASSET_RE = re.compile(r"/assets/(?:css|js)/[A-Za-z0-9._-]+\.(?:css|js)")
ASSET_HASH = {}


def version(url):
    """`/assets/js/guide.js` -> `/assets/js/guide.js?v=1a2b3c4d`.

    Everything under /assets is served with a one-year immutable
    Cache-Control, which is right for the photographs and the fonts (their
    names change when they do) but wrong for the stylesheet and the scripts,
    which are edited in place. Stamping the content hash on the URL is what
    makes the header honest: edit the file and returning visitors get the new
    one, leave it alone and nobody refetches it."""
    if url not in ASSET_HASH:
        with open(os.path.join(SRC, url.lstrip("/")), "rb") as f:
            ASSET_HASH[url] = hashlib.sha256(f.read()).hexdigest()[:8]
    return f"{url}?v={ASSET_HASH[url]}"


def version_assets(text):
    return ASSET_RE.sub(lambda m: version(m.group(0)), text)


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


def render_itineraries(data):
    out = []
    for it in data["itineraries"]:
        steps = "".join(
            f'<li class="l-step"><div class="l-step-when">{html.escape(st["when"])}</div><div>'
            f'<h3 class="l-h3" style="font-size:1.25rem;color:var(--l-redrock)">{html.escape(st["title"])}</h3>'
            f'<p class="l-body" style="margin:8px 0 0;font-size:.9375rem;max-width:60ch">{html.escape(st["detail"])}</p>'
            + (f'<a class="l-link" href="{html.escape(st["href"])}" style="display:inline-block;margin-top:8px">Details <span aria-hidden="true">&#8594;</span></a>' if st.get("href") else "")
            + "</div></li>"
            for st in it["steps"]
        )
        tips = "".join(f"<li>{html.escape(t)}</li>" for t in it.get("tips", []))
        out.append(
            f'<section class="l-itin" id="{it["slug"]}" aria-labelledby="{it["slug"]}-h">'
            f'<div class="l-wrap"><div class="l-g2-wide" style="align-items:start">'
            f'<div><div class="l-label">{html.escape(it["kicker"])}</div>'
            f'<h2 class="l-h2" id="{it["slug"]}-h" style="margin-top:12px;color:var(--l-redrock)">{html.escape(it["title"])}</h2>'
            f'<p class="l-lead" style="margin:14px 0 0;max-width:46ch">{html.escape(it["blurb"])}</p>'
            f'<dl class="l-dl"><div><dt>Best for</dt><dd>{html.escape(it["best_for"])}</dd></div>'
            f'<div><dt>Season</dt><dd>{html.escape(it["season"])}</dd></div>'
            f'<div><dt>Getting around</dt><dd>{html.escape(it["getting_around"])}</dd></div></dl>'
            f'<figure class="l-photo-natural" style="margin:22px 0 0">{{{{pic name="{it["photo"]}" alt="{html.escape(it["alt"], quote=True)}" sizes="(max-width: 900px) calc(100vw - 48px), 36vw"}}}}</figure>'
            f'</div>'
            f'<div><ol class="l-steps">{steps}</ol>'
            + (f'<div class="l-callout l-callout--paper" style="margin-top:22px"><div class="l-label">Worth knowing</div><ul class="l-body" style="margin:10px 0 0;padding-left:18px;font-size:.9375rem">{tips}</ul></div>' if tips else "")
            + "</div></div></div></section>"
        )
    return "".join(out)


def render_itinerary_cards(data):
    cards = []
    for it in data["itineraries"]:
        cards.append(
            f'<article class="l-itin-card" data-months="{" ".join(str(m) for m in it["months"])}">'
            f'<a href="/itineraries/#{it["slug"]}" style="display:block;text-decoration:none">'
            f'{{{{pic name="{it["photo"]}" alt="{html.escape(it["alt"], quote=True)}" sizes="(max-width: 520px) calc(100vw - 48px), (max-width: 1100px) 30vw, 18vw"}}}}'
            f'<div class="l-label" style="margin-top:12px;font-size:11px">{html.escape(it["kicker"])}</div>'
            f'<h3 class="l-h3">{html.escape(it["title"])}</h3>'
            f'<p class="l-body" style="margin:6px 0 0;font-size:.875rem">{html.escape(it["blurb"].split(". ")[0])}.</p>'
            f'<span class="l-tag" data-good-now hidden>Good now</span>'
            f'</a></article>'
        )
    return "".join(cards)


def render_now(data):
    m = data["months"][str(TODAY.month)]
    links = " ".join(f'<a class="l-link" href="{html.escape(h)}"{" rel=noopener" if h.startswith("http") else ""}>{html.escape(t)} <span aria-hidden="true">{"&#8599;" if h.startswith("http") else "&#8594;"}</span></a>' for t, h in m["links"])
    payload = json.dumps(data["months"], ensure_ascii=False).replace("</", "<\\/")
    return (
        f'<div class="l-now" data-now data-now-month="{TODAY.month}">'
        f'<div class="l-label" style="color:var(--l-sandstone-ink)">Right now</div>'
        f'<h2 class="l-h3" data-now-headline style="margin-top:8px;color:var(--l-redrock)">{html.escape(m["headline"])}</h2>'
        f'<p class="l-body" data-now-body>{html.escape(m["body"])}</p>'
        f'<div data-now-links>{links}</div>'
        f'<script type="application/json" data-now-data>{payload}</script>'
        f'</div>'
    )


def denver_iso(date_str, hhmm):
    try:
        from zoneinfo import ZoneInfo
        h, mnt = hhmm.split(":")
        d = dt.date.fromisoformat(date_str)
        return dt.datetime(d.year, d.month, d.day, int(h), int(mnt), tzinfo=ZoneInfo("America/Denver")).isoformat()
    except Exception:
        return f"{date_str}T{hhmm}:00-06:00"


def events_ld(occ, days=60, cap=40):
    items = []
    end = TODAY + dt.timedelta(days=days)
    for o in occ:
        d = dt.date.fromisoformat(o["date"])
        if d < TODAY or d > end:
            continue
        ev = {
            "@type": "Event",
            "name": o["title"],
            "startDate": denver_iso(o["date"], o.get("sort", "09:00")),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "name": o.get("venue", "Lyons, Colorado"), "address": {"@type": "PostalAddress", "streetAddress": o.get("address", ""), "addressLocality": "Lyons", "addressRegion": "CO", "postalCode": "80540", "addressCountry": "US"}},
        }
        if o.get("organizer"):
            ev["organizer"] = {"@type": "Organization", "name": o["organizer"]}
        if o.get("detail"):
            ev["description"] = o["detail"]
        if o.get("url"):
            ev["url"] = o["url"]
        if o.get("cost") and o["cost"].lower().startswith(("free", "no cover")):
            ev["isAccessibleForFree"] = True
        items.append(ev)
        if len(items) >= cap:
            break
    return items


def attractions_ld(places):
    return {
        "@type": "ItemList",
        "name": "Places in and around Lyons, Colorado",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": {"@type": "TouristAttraction", "name": p["name"], "description": p.get("blurb", ""), "url": (SITE + p["href"]) if p.get("href") else p.get("url"), "geo": {"@type": "GeoCoordinates", "latitude": p["lat"], "longitude": p["lng"]}}}
            for i, p in enumerate(places["places"])
        ],
    }


def trips_ld(data):
    return [
        {
            "@type": "TouristTrip",
            "name": it["title"],
            "description": it["blurb"],
            "url": f"{SITE}/itineraries/#{it['slug']}",
            "touristType": it["best_for"],
            "itinerary": {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": st["title"], "description": st["detail"]} for i, st in enumerate(it["steps"])]},
        }
        for it in data["itineraries"]
    ]


FAQ_RE = re.compile(r'<h3 class="l-h3">(.*?)</h3>\s*<p class="l-body">(.*?)</p>', re.S)


def faq_ld(body):
    m = re.search(r'<div class="l-faq">(.*?)</div>\s*</div>\s*</section>', body, re.S)
    if not m:
        return None
    qa = FAQ_RE.findall(m.group(1))
    strip = lambda t: html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": strip(q), "acceptedAnswer": {"@type": "Answer", "text": strip(a)}} for q, a in qa]}


# --------------------------------------------------------------- pages ----

# ------------------------------------------------------------ calendar ----
# A subscribable feed at /events.ics. One-off events become single VEVENTs;
# the weekly and monthly series become recurring ones, so the feed keeps
# working between rebuilds instead of running out at the site's horizon.

CLOCK_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)
ICS_DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
SERIES_ANCHOR = TODAY  # recurrence starts at the next occurrence, not in the past


def parse_clock(part, fallback_meridiem=None):
    m = CLOCK_RE.match(part)
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2) or 0)
    mer = (m.group(3) or fallback_meridiem or "").lower()
    if not mer or not (1 <= h <= 12):
        return None
    if mer == "pm" and h != 12:
        h += 12
    if mer == "am" and h == 12:
        h = 0
    return h * 60 + mins


def parse_time(s):
    """'5-8 pm' -> (1020, 1200) in minutes past midnight. A single time gives
    (start, None); anything unparseable gives None, and the event goes in as
    all-day rather than at a guessed hour."""
    if not s:
        return None
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    if "-" not in s:
        start = parse_clock(s)
        return (start, None) if start is not None else None
    left, right = s.split("-", 1)
    end = parse_clock(right)
    if end is None:
        return None
    start = parse_clock(left)
    if start is None:
        # "5-8 pm": the left side borrows the right side's am/pm, unless that
        # would put the start after the end ("11-1 pm").
        mer = "pm" if end >= 12 * 60 else "am"
        start = parse_clock(left, mer)
        if start is not None and start >= end:
            alt = parse_clock(left, "am" if mer == "pm" else "pm")
            if alt is not None and alt < end:
                start = alt
    if start is None:
        return None
    return (start, end)


def ics_escape(s):
    return (str(s).replace("\\", "\\\\").replace(";", "\;")
            .replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n"))


def ics_fold(line):
    """RFC 5545 caps a content line at 75 octets; the rest continues on the
    next line behind a single space. Fold on octets, not characters, so
    multi-byte text is never cut in half."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, first = [], True
    while raw:
        cut = min(75 if first else 74, len(raw))  # continuations carry a space
        while 0 < cut < len(raw) and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(raw[:cut].decode("utf-8"))
        raw, first = raw[cut:], False
    return "\r\n ".join(parts)


def ics_dt(date_str, minutes):
    d = dt.date.fromisoformat(date_str)
    return f"{d.strftime('%Y%m%d')}T{minutes // 60:02d}{minutes % 60:02d}00"


def ics_event(ev, date_str, uid, rrule=None, exdates=()):
    times = parse_time(ev.get("time"))
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{ICS_STAMP}",
        f"SUMMARY:{ics_escape(ev['title'])}",
    ]
    if times:
        start, end = times
        lines.append(f"DTSTART;TZID=America/Denver:{ics_dt(date_str, start)}")
        # No published end time: an hour keeps the entry visible in clients
        # that need a duration, and the listed time goes in the description.
        lines.append(f"DTEND;TZID=America/Denver:{ics_dt(date_str, end if end is not None else min(start + 60, 24 * 60 - 1))}")
    else:
        d = dt.date.fromisoformat(date_str)
        lines.append(f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{(d + dt.timedelta(days=1)).strftime('%Y%m%d')}")
    if rrule:
        lines.append(f"RRULE:{rrule}")
    for x in exdates:
        if times:
            lines.append(f"EXDATE;TZID=America/Denver:{ics_dt(x, times[0])}")
        else:
            lines.append(f"EXDATE;VALUE=DATE:{dt.date.fromisoformat(x).strftime('%Y%m%d')}")
    where = " \u00b7 ".join(x for x in [ev.get("venue"), ev.get("address")] if x)
    if where:
        lines.append(f"LOCATION:{ics_escape(where + ', Lyons, CO 80540')}")
    desc = [x for x in [ev.get("detail")] if x]
    if ev.get("time") and not times:
        desc.append(f"Listed time: {ev['time']}.")
    elif ev.get("time") and times and times[1] is None:
        desc.append(f"Listed time: {ev['time']} (no end time published).")
    meta = " \u00b7 ".join(x for x in [ev.get("organizer"), ev.get("cost")] if x)
    if meta:
        desc.append(meta)
    if ev.get("url"):
        desc.append(ev["url"])
        lines.append(f"URL:{ics_escape(ev['url'])}")
    desc.append(f"Listing: {SITE}/events/")
    lines.append(f"DESCRIPTION:{ics_escape(chr(10).join(desc))}")
    lines.append("END:VEVENT")
    return lines


def ics_feed(data):
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ExploreLyons.com//Lyons Colorado events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Lyons\\, Colorado events",
        "X-WR-CALDESC:Events in Lyons\\, Colorado\\, from ExploreLyons.com. Times come from the organizer; check their page before setting out.",
        "X-WR-TIMEZONE:America/Denver",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
        # US rules since 2007: second Sunday in March, first Sunday in November.
        "BEGIN:VTIMEZONE",
        "TZID:America/Denver",
        "X-LIC-LOCATION:America/Denver",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:-0700",
        "TZOFFSETTO:-0600",
        "TZNAME:MDT",
        "DTSTART:20070311T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:-0600",
        "TZOFFSETTO:-0700",
        "TZNAME:MST",
        "DTSTART:20071104T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    count = 0
    for ev in data["events"]:
        start = dt.date.fromisoformat(ev["date"])
        end = dt.date.fromisoformat(ev.get("end", ev["date"]))
        day = start
        while day <= end:
            # Most ids already carry their date; only a multi-day event needs one.
            uid = ev["id"] if start == end else f"{ev['id']}-{day.isoformat()}"
            body += ics_event(ev, day.isoformat(), f"{uid}@explorelyons.com")
            count += 1
            day += dt.timedelta(days=1)
    for s in data.get("series", []):
        # First occurrence on or after the anchor, so the rule has a real start.
        day = SERIES_ANCHOR
        for _ in range(400):
            if day.weekday() == s["weekday"]:
                nth = (day.day - 1) // 7 + 1
                if "weeks" not in s or nth in s["weeks"]:
                    break
            day += dt.timedelta(days=1)
        else:
            continue
        dow = ICS_DAYS[s["weekday"]]
        rule = (f"FREQ=MONTHLY;BYDAY={','.join(str(n) + dow for n in s['weeks'])}"
                if "weeks" in s else f"FREQ=WEEKLY;BYDAY={dow}")
        skips = [x for x in s.get("skip", []) if dt.date.fromisoformat(x) >= day]
        body += ics_event(s, day.isoformat(), f"{s['id']}@explorelyons.com", rrule=rule, exdates=skips)
        count += 1
    body.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in body) + "\r\n", count


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


def jsonld(meta, extra=None):
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
    graph.extend(extra or [])
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")


def contact_form():
    """The form's attributes, and the note shown when there is no endpoint.

    With an endpoint the form is an ordinary POST, so it works with scripting
    off; `_next` sends those visitors to /thanks/. Without one there is no
    action to give it, so the no-script note carries the email address."""
    if FORM_ENDPOINT:
        attrs = (f'data-endpoint="{html.escape(FORM_ENDPOINT, quote=True)}" method="post" '
                 f'action="{html.escape(FORM_ENDPOINT, quote=True)}"')
        hidden = f'<input type="hidden" name="_next" value="{SITE}/thanks/">'
        note = ""
    else:
        attrs = 'data-endpoint=""'
        hidden = ""
        note = ('<noscript><p class="l-small" style="margin:0;max-width:54ch;color:var(--l-gold-lt)">'
                'This form is not connected to a mail service yet, so the button will not send '
                'anything. Write to <a href="mailto:editor@explorelyons.com" '
                'style="color:var(--l-gold-lt)">editor@explorelyons.com</a> instead.</p></noscript>')
    return attrs, hidden, note


def build():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(SRC, "assets"), os.path.join(OUT, "assets"))
    for f in ("favicon.svg", "apple-touch-icon.png", "robots.txt"):
        p = os.path.join(SRC, "static", f)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(OUT, f))

    layout = read(os.path.join(SRC, "layout.html"))
    form_attrs, form_hidden, form_noscript = contact_form()
    events = load_json("events.json")
    occ = expand_events(events)
    biz = load_json("businesses.json")
    places = load_json("places.json")
    directory = render_directory(biz)
    stay_cards = render_stay(biz)
    pins = build_pins(biz, places)
    itins = load_json("itineraries.json")
    now = load_json("now.json")
    itineraries_html = render_itineraries(itins)
    itinerary_cards = render_itinerary_cards(itins)
    now_module = render_now(now)
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
        body = body.replace("{{itineraries}}", itineraries_html)
        body = body.replace("{{itinerary_cards}}", itinerary_cards)
        body = body.replace("{{now_module}}", now_module)
        body = re.sub(r"\{\{pins:(\w+)\}\}", lambda m: json.dumps(pins_for(pins, m.group(1)), ensure_ascii=False).replace("</", "<\\/"), body)
        body = body.replace("{{upcoming_list}}", render_upcoming(occ, 10, "jump"))
        body = body.replace("{{events_json}}", upcoming_json.replace("</", "<\\/"))
        for k, v in directory.items():
            body = body.replace("{{dir_" + k + "}}", v)
        body = body.replace("{{today_long}}", TODAY.strftime("%B ") + str(TODAY.day) + TODAY.strftime(", %Y"))
        body = body.replace("{{form_attrs}}", form_attrs)
        body = body.replace("{{form_hidden}}", form_hidden)
        body = body.replace("{{form_noscript}}", form_noscript)
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
            "og_image_url": og_image_url(meta.get("og_image", "downtown")),
            "og_alt": html.escape(meta.get("og_alt", "Main Street in Lyons, Colorado, with the red sandstone hogback behind"), quote=True),
            "head_extra": meta.get("head_extra", ""),
            "jsonld": jsonld(meta, {
                "/": [x for x in [faq_ld(body)] if x],
                "/events/": events_ld(occ),
                "/explore/": [attractions_ld(places)],
                "/outdoors/": [attractions_ld(places)],
                "/itineraries/": trips_ld(itins),
            }.get(meta["path"], [])),
            "body_class": meta.get("body_class", "l-page"),
            "nav": nav_html,
            "crumbs": crumbs(meta),
            "body": body,
            "reviewed": REVIEWED,
        }.items():
            page = page.replace("{{" + k + "}}", v)
        page = version_assets(page)
        out_path = os.path.join(OUT, meta["path"].strip("/"), "index.html") if meta["path"] != "/" else os.path.join(OUT, "index.html")
        write(out_path, page)
        if meta.get("sitemap", True):
            urls.append(meta["path"])

    # GitHub Pages and most static hosts serve /404.html for missing paths.
    shutil.copy(os.path.join(OUT, "404", "index.html"), os.path.join(OUT, "404.html"))
    shutil.rmtree(os.path.join(OUT, "404"))

    ics, ics_count = ics_feed(events)
    write(os.path.join(OUT, "events.ics"), ics)

    write(os.path.join(OUT, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>\n" for u in urls)
          + "</urlset>\n")
    print(f"built {len(urls)} pages into public/ ({len(occ)} event occurrences, "
          f"{ics_count} calendar entries, reviewed {REVIEWED})")


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
        print("serving public/ at http://localhost:8000/")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
