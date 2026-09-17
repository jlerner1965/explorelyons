// Responsive photo pipeline. Run once when a photo is added or replaced:
//   node tools/images.mjs <source-dir>        e.g. node tools/images.mjs photos-new
// Requires `sharp` (npm i sharp) — it is not needed to build the site.
//
// Each source file becomes /assets/photos/<name>-<width>.{jpg,webp} at every
// width the source can fill. The file name is the slug the pages refer to, so
// overwriting an existing slug replaces that photo everywhere it appears.
import sharp from 'sharp';
import { readdirSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { basename, extname, join, relative } from 'node:path';
import { execSync } from 'node:child_process';

const src = process.argv[2];
if (!src) {
  console.error('usage: node tools/images.mjs <source-dir>');
  process.exit(1);
}
const root = new URL('../', import.meta.url).pathname;
const out = join(root, 'src/assets/photos/');
mkdirSync(out, { recursive: true });
const widths = [400, 560, 700, 1000, 1400];

// Where each slug is already used, so you know which alt text and captions to
// revisit after a replacement.
const uses = new Map();
const walk = (dir) => {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== 'photos' && e.name !== 'fonts') walk(p); continue; }
    if (!/\.(html|json)$/.test(e.name)) continue;
    for (const m of readFileSync(p, 'utf8').matchAll(/pic name="([a-z0-9-]+)"|"photo":\s*"([a-z0-9-]+)"/g)) {
      const slug = m[1] || m[2];
      if (!uses.has(slug)) uses.set(slug, new Set());
      uses.get(slug).add(relative(root, p));
    }
  }
};
walk(join(root, 'src'));

let wrote = 0;
for (const file of readdirSync(src).sort()) {
  if (!/\.(jpe?g|png|webp|tiff?)$/i.test(file)) continue;
  const name = basename(file, extname(file));
  if (!/^[a-z0-9-]+$/.test(name)) {
    console.error(`  skipped ${file} — name the file in lowercase-with-hyphens; it becomes the slug`);
    continue;
  }
  const image = sharp(join(src, file)).rotate();
  const meta = await image.metadata();
  const usable = widths.filter((w) => w <= meta.width);
  if (!usable.length) {
    console.error(`  skipped ${file} — ${meta.width}px wide, under the 400px minimum`);
    continue;
  }
  // WebP usually wins, but on a grainy or heavily textured photograph it comes
  // out bigger than the jpeg at the same quality. Writing it anyway would make
  // every browser that prefers webp download the larger file, so each width is
  // weighed and the whole set is kept or dropped together -- a partial set
  // would leave the build offering a smaller image to a wide screen.
  const webps = [];
  let webpWins = true;
  for (const w of usable) {
    const jpg = await image.clone().resize({ width: w }).jpeg({ quality: 78, mozjpeg: true }).toBuffer();
    const webp = await image.clone().resize({ width: w }).webp({ quality: 74 }).toBuffer();
    writeFileSync(join(out, `${name}-${w}.jpg`), jpg);
    webps.push([w, webp]);
    if (webp.length >= jpg.length) webpWins = false;
  }
  for (const [w, buf] of webps) {
    const p = join(out, `${name}-${w}.webp`);
    if (webpWins) writeFileSync(p, buf);
    else rmSync(p, { force: true });
  }
  wrote++;
  console.log(`${name}  ${meta.width}x${meta.height}  ->  ${usable.join(', ')}${webpWins ? '  (jpeg + webp)' : '  (jpeg only \u2014 webp came out larger)'}`);
  if (meta.width < 1400) console.log(`  note: under 1400px, so it will soften on wide screens and in link previews`);
  const where = uses.get(name);
  if (where) console.log(`  already used in: ${[...where].join(', ')} — check the alt text still describes it`);
  else console.log(`  new slug. Place it with:  {{pic name="${name}" alt="…"}}`);
}
if (wrote) {
  console.log(`\n${wrote} photo${wrote === 1 ? '' : 's'} written. Next: python3 build.py, then add a credit row in src/pages/privacy.html.`);
  try { execSync('git status --short src/assets/photos', { cwd: root, stdio: 'inherit' }); } catch {}
}
