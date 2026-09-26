# Site images

The logo is referenced by `assets/js/utils/constants.js` (`ASSETS.logo`), so no
other file needs editing — the header, footer and auth pages all pick it up at
once.

## Files

| File | Used by | Notes |
| ---- | ------- | ----- |
| `dsvv-logo.svg` | header, footer, login/register aside | The DSVV crest used by the shared frontend shell. |
| `campus.svg` | home page hero | The campus illustration used by the landing page. |

## Replacing the artwork

Drop a replacement in this folder under the same name and every page updates at
once. If you use a different name or format, update the path in
`assets/js/utils/constants.js`:

```js
export const ASSETS = {
  logo: '/assets/img/dsvv-logo.svg',
  campus: '/assets/img/campus.svg',
}
```

The hero photo path is also written literally in `index.html` (the `<img>`
inside `.hero-photo`), so change it there too if you rename the file.

If a referenced file is ever missing, nothing breaks: the logo `<img>` removes
itself and the CSS placeholder mark shows through, and the hero photo figure
collapses so the complaint card falls back to its previous layout — never a
broken-image icon.
