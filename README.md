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
- **Photography**: 31 Creative Commons and public-domain photographs of Lyons,
  each credited on `/privacy/#photos`.

## Pages

| Path | What it is |
| --- | --- |
| `/` | Home: hero, quick links, Town Board notice, upcoming events, explore cards, FAQ, community and visitor panels |
| `/explore/` | Five places in walking order: Main Street, the river and parks, trails, public art and the museum, Planet Bluegrass |
| `/eat-shop/` | Searchable, filterable business directory rendered from `src/data/businesses.json` |
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
- **A photo**: drop a JPEG into a folder and run `node tools/images.mjs <folder>`
  (needs `npm i sharp`), then credit it on `/privacy/#photos`.

### The contact form

`src/pages/contact.html` has `data-endpoint=""` on the form. Put a Formspree
(or similar) endpoint there and submissions post to it; until then the form
explains that nothing was sent and gives the editor's email address.

## Deploy

**Vercel**: import the repository; `vercel.json` sets the build command
(`python3 build.py`) and output directory (`public`), so no framework preset is
needed. Add `explorelyons.com` under the project's Domains.

Any other static host works: point it at `public/` after running `build.py`.

## Credits

Photographs are from Wikimedia Commons under CC BY-SA 3.0 and public domain;
each is credited on the privacy page. Fonts are Instrument Serif and Instrument
Sans (SIL OFL), self-hosted.
