# Site images

The logo is referenced by `assets/js/utils/constants.js` (`ASSETS.logo`), so no
other file needs editing — the header, footer and auth pages all pick it up at
once.

## Files

| File | Used by | Notes |
| ---- | ------- | ----- |
| `dsvv-logo.png` | header, footer, login/register aside | The official DSVV crest. Transparent square, 128×128 or larger; drawn at 44px. |
| `campus.jpg` | home page hero | Aerial photograph of the DSVV campus. Landscape, ~16:10, 1600px wide or larger. |
| `dsvv-logo.svg` | — | Superseded placeholder emblem, kept as the offline fallback reference. |
| `campus.svg` | — | Superseded illustration, kept as a reference. |

## Replacing the artwork

Drop a replacement in this folder under the same name and every page updates at
once. If you use a different name or format, update the path in
`assets/js/utils/constants.js`:

```js
export const ASSETS = {
  logo: '/assets/img/dsvv-logo.png',
  campus: '/assets/img/campus.jpg',
}
```

The hero photo path is also written literally in `index.html` (the `<img>`
inside `.hero-photo`), so change it there too if you rename the file.

If a referenced file is ever missing, nothing breaks: the logo `<img>` removes
itself and the CSS placeholder mark shows through, and the hero photo figure
collapses so the complaint card falls back to its previous layout — never a
broken-image icon.
