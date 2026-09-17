# Drop new photos here

Put original files in this folder, commit them, and the responsive versions get
generated from them. Nothing in here is published — only the resized copies
under `src/assets/photos/` are.

## Naming

The file name becomes the slug the pages refer to, so name it in
lowercase-with-hyphens and no spaces:

    main-street-storefronts.jpg
    hall-ranch-nelson-house.jpg

To **replace** a photo that is already on the site, give the file the existing
slug. Everywhere that photo appears picks up the new one. The current slugs are
the file names in `src/assets/photos/`, minus the `-400`, `-1400` suffixes.

Landscape, at least 1400px wide, straight out of the camera — the tool does the
resizing and compression.

## Generating

    npm install sharp          # once, on your machine
    node tools/images.mjs photos-new
    python3 build.py

The tool prints each slug, the widths it wrote, which pages already use that
slug, and the `{{pic …}}` tag to paste for a new one.

## Placing a new photo

In the relevant file under `src/pages/`:

    {{pic name="main-street-storefronts" alt="Storefronts along Main Street in Lyons, a hanging sign over the sidewalk"}}

Alt text describes what is in the frame for someone who cannot see it. Say what
the thing is and where, not "photo of".

## Credits

Every photo on the site is credited on `/privacy/#photos`. Add a row there with
the photographer, the year, and the licence or a note that it is used with
permission. For each file dropped here, that means knowing:

- where it was taken (the site's premise is that every place named is verified)
- who took it and in what year
- that you have the right to publish it

A photo without those cannot go up.
