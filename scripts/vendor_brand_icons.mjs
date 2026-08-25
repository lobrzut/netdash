#!/usr/bin/env node
/**
 * Regenerate app/static/brands/*.svg from the simple-icons npm package.
 *
 * NetDash ships brand icons locally instead of calling cdn.simpleicons.org at
 * render time: a self-hosted dashboard should not phone a third-party CDN, and
 * an offline homelab would otherwise show blank tiles.
 *
 *   npm install simple-icons
 *   node scripts/vendor_brand_icons.mjs
 *
 * Slugs are read from app/icons.py, so adding a brand there and re-running this
 * is the whole workflow. Slugs that no longer exist upstream are reported and
 * MUST be removed from app/icons.py — a dead slug suppresses the favicon
 * fallback and leaves the tile permanently empty.
 *
 * Icons are CC0-1.0 (see app/static/brands/README.md).
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import * as si from 'simple-icons';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'app', 'static', 'brands');
const py = readFileSync(join(ROOT, 'app', 'icons.py'), 'utf8');

const slugs = new Set();
for (const m of py.matchAll(/\(r"[^"]+",\s*"([a-z0-9._-]+)"\)/g)) slugs.add(m[1]);
for (const m of py.matchAll(/^\s*\d+:\s*"([a-z0-9._-]+)",\s*$/gm)) slugs.add(m[1]);

const bySlug = new Map();
for (const k of Object.keys(si)) {
  const ic = si[k];
  if (ic && typeof ic === 'object' && ic.slug && ic.svg) bySlug.set(ic.slug, ic);
}

mkdirSync(OUT, { recursive: true });
const written = new Set();
const missing = [];
for (const slug of [...slugs].sort()) {
  const ic = bySlug.get(slug);
  if (!ic) { missing.push(slug); continue; }
  writeFileSync(join(OUT, `${slug}.svg`), ic.svg.replace('<svg ', `<svg fill="#${ic.hex}" `), 'utf8');
  written.add(`${slug}.svg`);
}
for (const f of readdirSync(OUT)) {
  if (f.endsWith('.svg') && !written.has(f)) { unlinkSync(join(OUT, f)); console.log('removed stale', f); }
}

console.log(`vendored ${written.size} icons from simple-icons ${si.default?.version ?? ''}`.trim());
if (missing.length) {
  console.error(`\nNOT IN simple-icons — remove these from app/icons.py:\n  ${missing.join(' ')}`);
  process.exitCode = 1;
}
