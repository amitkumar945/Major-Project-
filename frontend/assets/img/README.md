# Site images

The logo is referenced by `assets/js/utils/constants.js` (`ASSETS.logo`), so no
other file needs editing — the header, footer and auth pages all pick it up at
once.

## Files

| File | Used by | Notes |
| ---- | ------- | ----- |
| `dsvv-logo.svg` | header, footer, login/register aside | A neutral placeholder emblem, **not** the official DSVV crest. Square, 128×128 viewBox, drawn at 44px. |
| `campus.svg` | decorative illustration | Simulated campus surface, not a photograph. |

## Using the official crest

Replace `dsvv-logo.svg` with the real artwork and every page updates at once.

If the official file is a PNG (or any other name/format), drop it in here and
update the path in `assets/js/utils/constants.js`:

```js
export const ASSETS = {
  logo: '/assets/img/dsvv-logo.png',
}
```

A transparent square image around 128×128 or larger looks best; it is drawn at
44px.

If the referenced file is ever missing, the `<img>` removes itself and a CSS
placeholder mark shows through — never a broken-image icon.
