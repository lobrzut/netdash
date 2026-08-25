# Vendored brand icons

SVGs generated from the [simple-icons](https://github.com/simple-icons/simple-icons)
npm package and served from this directory. **NetDash makes no outbound request to
render a tile.**

Previously these were fetched from `https://cdn.simpleicons.org/{slug}` at render
time. That was wrong twice over: a self-hosted dashboard should not phone a
third-party CDN on every card, and an offline homelab saw blank squares. Worse,
21 of the slugs in the table no longer existed upstream, so the CDN answered 404
— and because the code believed it had an icon URL, the favicon fallback never
ran and those tiles stayed empty forever.

## Regenerating

```bash
npm install simple-icons
node scripts/vendor_brand_icons.mjs
```

Slugs are read out of `app/icons.py`. If the script reports a slug that is not in
simple-icons, remove it from `app/icons.py` rather than leaving it — a dead slug
suppresses the favicon fallback.

## Licence

Icon SVGs are **CC0-1.0** (public domain) per the simple-icons project. The brands
depicted are trademarks of their respective owners; they are used here to identify
the corresponding service and imply no affiliation or endorsement.

Escape hatch: set `NETDASH_BRAND_ICON_CDN=true` to restore the old CDN behaviour.
