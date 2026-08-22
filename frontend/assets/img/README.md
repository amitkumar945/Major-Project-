# Site images

Drop the two official DSVV assets here. Both are referenced by
`assets/js/utils/constants.js` (`ASSETS.logo` and `ASSETS.campus`), so no
other file needs editing — the header, footer, auth pages and the home-page
hero all pick them up at once.

Until a file exists, the page renders a clearly marked placeholder in its
place. Nothing breaks while the slot is empty.

## Expected files

| File | Used by | Notes |
| ---- | ------- | ----- |
| `dsvv-logo.png` | header, footer, login/register aside | Square-ish crest. A transparent PNG or SVG around 128×128 or larger looks best; it is drawn at 40px. |
| `campus.jpg` | home-page hero | The official campus photograph. Landscape, ideally 1600×1000 or larger. It is cropped to a 4:3-ish frame, so keep the building roughly centred. |

If you use different filenames or formats, update the two paths in
`assets/js/utils/constants.js`.
