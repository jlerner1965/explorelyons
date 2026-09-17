// Responsive photo pipeline. Run once when a photo is added or replaced:
//   node tools/images.mjs <source-dir>
// Requires `sharp` (npm i sharp) — it is not needed to build the site.
import sharp from 'sharp';
import { readdirSync, mkdirSync } from 'node:fs';
import { basename, extname, join } from 'node:path';

const src = process.argv[2];
const out = new URL('../src/assets/photos/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });
const widths = [400, 560, 700, 1000, 1400];

for (const file of readdirSync(src)) {
  if (!/\.(jpe?g|png)$/i.test(file)) continue;
  const name = basename(file, extname(file));
  const image = sharp(join(src, file)).rotate();
  const meta = await image.metadata();
  for (const w of widths) {
    if (w > meta.width) continue;
    await image.clone().resize({ width: w }).jpeg({ quality: 78, mozjpeg: true }).toFile(join(out, `${name}-${w}.jpg`));
    await image.clone().resize({ width: w }).webp({ quality: 74 }).toFile(join(out, `${name}-${w}.webp`));
  }
  console.log(name, `${meta.width}x${meta.height}`);
}
