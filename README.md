# ExploreLyons.com

An independent community guide to Lyons, Colorado. The page structure and
editorial posture follow [TownofNiwot.com](https://townofniwot.com/): a light
sticky masthead, numbered quick links, a dark events band, framed photographs,
definition rows, and every fact linked to its official source.

The design system is Lyons' own, "red rock and river" (see the top of
`src/assets/css/guide.css`):

- **Colour** from the Lyons Formation sandstone (`--l-sandstone`, `--l-redrock`,
  `--l-canyon`), the St. Vrain (`--l-river`, `--l-river-deep`), festival gold
  and warm sandstone-dust paper grounds.
- **Type**: Fraunces (variable, with italics) for display and headings,
  Bricolage Grotesque for body, labels and navigation. Both self-hosted.
- **Devices**: three-band *strata* rules (under the wordmark and every section
  head), a thin teal *river line* at the two big page transitions, a hogback
  silhouette in the hero, and photographs cut like flagstone with a chamfer on
  two corners. No rounded corners anywhere.
- **Photography**: 30 Creative Commons and public-domain photographs of Lyons,
  each credited on `/privacy/#photos`.

## Pages

| Path | What it is |
| --- | --- |
| `/` | Home: hero, quick links, "This weekend" module with the live river chip, coming-up events, explore cards, FAQ, trip and live-here panels |
| `/explore/` | Five places in walking order: Main Street, the river and parks, trails, public art and the museum, Planet Bluegrass |
| `/eat-shop/` | Searchable, filterable business directory rendered from `src/data/businesses.json`, with a map |
| `/itineraries/` | Five step-by-step days from `src/data/itineraries.json`; cards on Home and Explore with a "Good now" tag by month |
| `/stay/` | Lodging cards from the directory, the Town campground, festival-weekend advice, nearby towns, a map |
| `/outdoors/` | The live St. Vrain level (Colorado DWR gauge SVCLYOCO) with plain-language tubing levels, the whitewater park, fishing, a trail table for five areas, a map |
| `/events/` | Upcoming list, month calendar, annual fixtures and the weekly rhythm, from `src/data/events.json` |
| `/plan-a-visit/` | Directions, parking passes, visitor center, seasons, lodging |
| `/community/` | Community groups, public bodies, and a who-to-contact resident resources list |
| `/our-story/` | Timeline from the quarries to the 2013 flood and the rebuild |
| `/civic/` | Mayor and trustees, meetings, boards and commissions, elections, official bodies |
| `/contact/` | Submission form (needs a form endpoint; see below) |
| `/privacy/` | Privacy, sources and photo credits |

## Build

No dependencies beyond Python 3.

```sh
python3 build.py            # writes public/
python3 build.py --serve    # builds, then serves public/ at http://localhost:8000/
```

`src/layout.html` is the shared chrome. Each page in `src/pages/` starts with a
JSON meta block, then its body. Photographs are placed with
`{{pic name="downtown" alt="…" sizes="…"}}` and expanded into responsive
`<picture>` elements (jpeg + webp at 400–1400px) from `src/assets/photos/`.

### Content updates

- **A business**: add an object to `src/data/businesses.json` with a `checked` date.
- **A dated event**: add it to `events` in `src/data/events.json`. Weekly and
  first/third-Monday fixtures live in `series` and are expanded by the build.
  Past events drop off the upcoming lists automatically in the browser; rebuild
  periodically so the calendar horizon rolls forward.
- **The month module**: `src/data/now.json` has one entry per month; the build writes the current month and the browser re-picks by its own date.
- **An itinerary**: add an object to `src/data/itineraries.json` (steps, tips, months); it renders on `/itineraries/` and as a card.
- **A photo**: put the original in `photos-new/` and run
  `node tools/images.mjs photos-new` (needs `npm i sharp`), then credit it on
  `/privacy/#photos`. `photos-new/README.md` has the naming and credit rules.

### The calendar feed

`build.py` writes `public/events.ics`, a subscribable iCalendar feed linked from
`/events/#subscribe` and from the footer. One-off events become single VEVENTs;
the `series` entries become recurring ones (`FREQ=WEEKLY` or, for the
first/third-Monday fixtures, `FREQ=MONTHLY;BYDAY=1MO,3MO`), so a subscriber's
calendar keeps filling in between rebuilds rather than stopping at the site's
horizon. `skip` dates become `EXDATE`s.

Times are parsed from the human strings in `events.json` (`"5–8 pm"`,
`"7 am–1 pm"`, `"6:30–8:30 pm"`). A start with no published end gets an hour and
says so in the description; anything unparseable goes in as all-day rather than
at a guessed hour. The feed carries a `VTIMEZONE` for `America/Denver`, so a
7 pm meeting stays at 7 pm across the daylight-saving change.

### Live data and the map

- **River level**: `assets/js/guide.js` fetches the last two days of 15-minute
  readings from the Colorado Division of Water Resources' public API for station
  `SVCLYOCO` (Saint Vrain Creek at Lyons) and turns the latest one into a
  plain-language level. Without scripting the chip and the panel show static text
  and a link to the gauge. Thresholds live in the `reading()` function.
- **Map**: Leaflet 1.9.4 is vendored in `src/assets/vendor/leaflet/` and loaded
  only when a visitor opens a map, over OpenStreetMap tiles. Pins are built by
  `build.py` from the `lat`/`lng` on each listing in `businesses.json` (geocoded
  once with Nominatim) and from `src/data/places.json`; `{{pins:eat}}`,
  `{{pins:stay}}` and `{{pins:outdoors}}` select subsets per page. A listing
  with coordinates gets an "On the map" link automatically.

### The contact form

Submissions go to `api/contact.py`, the site's own endpoint, which Vercel
deploys as `/api/contact`. It checks the honeypot, requires a name and some
detail, holds each field to a length, and hands the rest to
[Resend](https://resend.com). Standard library only, so there is no
`requirements.txt`. Both paths work: `fetch()` for visitors with scripting, and
an ordinary form POST that the endpoint answers with a redirect to `/thanks/`
for those without. The redirect target is fixed in the code and deliberately
not read from the request, which is what keeps it from being an open redirect.

**Two things to set before it works:**

1. **`RESEND_API_KEY`** in the Vercel project's environment variables. Without
   it the form reports that it is not connected — a 503 and a plain sentence —
   rather than losing a submission quietly.
2. **Verify `explorelyons.com` in Resend**, which means adding the DKIM and SPF
   records it gives you to the domain's DNS. Until that is done Resend will
   only deliver to the address that owns the account, so the editor will not
   get anything sent from `form@explorelyons.com`.

Optional: `CONTACT_TO` (default `editor@explorelyons.com`) and `CONTACT_FROM`
(default `form@explorelyons.com`, which is the address the DNS verifies).

**This is the one thing the site cannot launch without.** "Submit a listing"
is in the nav and footer of every page, and it is the only route for
corrections. After the first deploy, send one submission with scripting on and
one with it off and check both arrive.

An off-site form service works here instead if you would rather not run the
endpoint: put its URL in `FORM_ENDPOINT` at the top of `build.py` and the form
posts there, `_next` included. Its origin has to be added to `connect-src` and
`form-action` in `vercel.json`, and the build will refuse — by name — until it
is. Setting `FORM_ENDPOINT` to `""` puts the form back to saying plainly that
nothing was sent and giving the editor's address.

## Deploy

**Vercel**: import the repository; `vercel.json` sets the build command
(`python3 build.py`) and output directory (`public`), so no framework preset is
needed. Add `explorelyons.com` under the project's Domains.

Any other static host works: point it at `public/` after running `build.py`.

Everything under `/assets` is served `immutable` for a year. That is safe
because the build stamps the stylesheet and the scripts with a hash of their
own contents (`/assets/js/guide.js?v=7508c22c`), so the URL changes whenever
the file does. Photographs and fonts get new names when they change, so they
need no stamp. The one exception is the vendored Leaflet under
`/assets/vendor/`: it is version-pinned, so swapping it means renaming the
folder or clearing the CDN cache.

`vercel.json` also sets the security headers. The Content-Security-Policy is
strict — `script-src 'self'` with no `unsafe-inline`, because every executable
script is a file and the inline blocks are `application/json` data — and names
the only two third parties the pages talk to: `dwr.state.co.us` for the river
gauge and `tile.openstreetmap.org` for map tiles. Anything new the pages reach
for has to be added there, and `build.py` refuses to build if `FORM_ENDPOINT`
is set to an origin the policy would block.

### Keeping it current

`.github/workflows/rebuild.yml` redeploys the site every morning. This matters
more than it looks: the build bakes today's date into "this weekend", into how
far the weekly fixtures are expanded, and into the sitemap and the footer, so a
site deployed once and left alone stops rolling forward. It needs one
repository secret, `VERCEL_DEPLOY_HOOK` — create a Deploy Hook in the Vercel
project under Settings → Git → Deploy Hooks and paste its URL in.

`.github/workflows/build.yml` runs `build.py` on every push and checks that
every page, photo, stylesheet and script a page references was actually
written, so a broken build shows up on the branch rather than in production.

## Credits

Photographs are from Wikimedia Commons and Flickr under Creative Commons
licences and public domain; each is credited, with its licence, on the privacy
page.

Type is Fraunces (Undercase Type) for display and Bricolage Grotesque (Mathieu
Triay) for everything else, both self-hosted Latin subsets under the SIL Open
Font License. The licence requires its text and copyright notice to travel with
the files, so both sit next to them in `src/assets/fonts/` and ship with the
site; `src/assets/fonts/README.txt` says which is which.

The map is Leaflet 1.9.4 (BSD-2-Clause, vendored under `src/assets/vendor/`)
over OpenStreetMap tiles, © OpenStreetMap contributors.
