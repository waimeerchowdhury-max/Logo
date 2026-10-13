# Design notes — theapostrophe

Short record of *why* the identity looks the way it does, and which numbers are load-bearing.
Everything here is produced by `src/build_logo.py`; change the constants at the top of that file
and the whole package rebuilds.

## 1. The idea

A photography mark usually does one of two things: it shows a camera, or it shows a lens.
`theapostrophe` has a better card to play — the name already contains a **punctuation mark**
that looks like **a light aperture**. So the badge is built on that double reading:

```
        camera iris                     the apostrophe
   six blades, six-sided opening   →   stands inside the opening
```

Read at a distance it is a lens seen from the front. Read closely, the mark is an
**apostrophe in the light** — which is also what a photograph is.

## 2. Construction

The badge is designed inside a **1000-unit square** (`D = 1000`); every other file is this
square scaled to millimetres. All curves are exact circles and circular arcs — the file contains
no traced or approximated outline.

| Element | Rule | Value |
|---|---|---|
| Ring | outer circle `R = D/2`, thickness `0.072 × D`, drawn as a true donut (reversed inner contour) | 7.2 % |
| Blades | six discs of radius `R − ring`, each cut by the aperture disc | 6 |
| Aperture | apothem `0.27 × D` — a hexagon with corners, not a circle | 27 % |
| Rotation | `30°` so a corner (blade tip) sits exactly at 12 o'clock | 30° |
| Apostrophe | height `0.54 × D`, tapered wedge: 31 % → 11.5 % width, leaning left 5 %, softly bowed sides | see `APOS` |

The blades are the classic construction: **disc minus disc**. Blade *k* is a circle of radius
`R − ring` centred at the origin, with a circle of radius `ρ` centred at distance `e` along
direction `φ = 30° + 60k` subtracted from it. The six subtraction circles *are* the opening, so
every blade wall automatically faces the centre — that is why the opening reads as an iris
instead of a starburst. (`e = 0.25 D`, `ρ = e + apothem`.)

Two details worth keeping if you ever redraw this:

* the **blade spread is zero** — the blades are tangent at the corners. A gap turns the badge
  into a flower; an overlap fills the opening in.
* the apostrophe is **drawn, not typed**. Jost's own quote mark is a plain rectangle; a
  hand-built wedge with curved sides and a slight lean is what makes it rhyme with the blade
  corners and still read as a period-correct apostrophe.

## 3. Typography

**Jost** (SIL OFL) — geometric, quiet, and it holds up from favicon to billboard.
Lowercase for the wordmark; the name is one continuous word, so the lockups never break it.

| | |
|---|---|
| Wordmark | Jost **500**, tracking **+2.8 %** |
| Tagline | `PHOTOGRAPHY`, Jost **400**, tracking **+40 %** |
| Cap height / badge | badge `2.1 ×` cap height in the horizontal lockup |
| Alignment | badge centred on the wordmark's x-height band (not its ink box, which the descender of the `p` would drag down); tagline flush right with the wordmark |

All artwork ships with **type converted to outlines**, so nothing depends on a font being
installed. The `woff2` subsets in `assets/fonts/` exist only for the brand page.

## 4. Colour

| Name | Hex | CMYK | Use |
|---|---|---|---|
| Studio Ink | `#16130E` | 0 / 13 / 36 / 91 | marks, text |
| Paper | `#F7F3EC` | 0 / 2 / 5 / 3 | default background |
| Brass *accent* | `#C08F2C` | 0 / 25 / 77 / 25 | sparingly: stamp, foil, one link, a thin rule |

Warm neutrals rather than pure `#000`/`#FFF`: printed photographs and skin tones sit better on
Paper, and Studio Ink reads as a considered black rather than a default one.

## 5. Rules

* **Clear space** ≥ `0.35 ×` badge diameter (already baked into every trimmed master).
* **Minimum sizes** badge `8 mm` / `24 px`; wordmark cap height `1.5 mm`.
  Below 24 px use `favicon.svg` — same badge with the blades removed, so it survives pixel
  rounding.
* **Never**: stretch, rotate, outline, add shadows/gradients, swap the typeface, re-space the
  letters, place the ink version on a photo, or introduce a colour outside the palette.

## 6. Files, in order of authority

1. `build/master/*.svg` — masters, 1 unit = 1 mm, outlined. **Edit only via `src/build_logo.py`.**
2. `build/print/*.pdf`, `build/eps/*.eps` — same geometry at true physical size.
3. `assets/*.svg` — the everyday copies (also what the landing page and README use).
4. `build/png|jpg|icons|social/*` — rasters generated from (1).
5. `build/brand/theapostrophe-identity-sheet.*` — A4 summary for people who will never open a vector.
