#!/usr/bin/env python3
"""
theapostrophe — identity build.

Turns the approved geometry + type into every deliverable:
  master/*.svg      editable vector masters (1 unit = 1 mm, outlined type)
  print/*.pdf|eps   1:1 physical-size vector files
  png/  jpg/        rasters (ink, white, on-paper, on-ink, watermark)
  icons/            favicon + app icons
  social/           OG card, avatar
  brand/            A4 identity sheet (SVG + PDF)

Run:  .venv/bin/python src/build_logo.py   &&   node tools/render.js build/jobs.json
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from logokit import (  # noqa: E402
    Doc, Font, Shape, annulus, circle, disc_minus_disc, eps, pdf, rounded_polygon,
    svg, wedge,
)

OUT = os.path.join(ROOT, "build")
MM2PT = 72.0 / 25.4

# ---------------------------------------------------------------- identity --
NAME = "theapostrophe"
TAGLINE = "PHOTOGRAPHY"

INK = "#16130E"          # "Studio Ink"  – warm near-black
PAPER = "#F7F3EC"        # "Paper"       – warm off-white
GOLD = "#C08F2C"         # "Brass"       – optional accent (foil, stamp, web)
MUTED = "#6B6355"        # secondary text tone used in the brand sheet

FONT_PATH = os.path.join(HERE, "fonts", "Jost[wght].ttf")
F_WORD, F_TAG = 500, 400

# ------------------------------------------------------------------- mark --
D = 1000.0               # mark is designed in a 1000-unit square
RING = 0.072             # badge ring thickness   (× D)
E_K = 0.25               # blade-disc offset      (× D)
APOTHEM = 0.27           # aperture apothem       (× D)
ROT0 = 30.0              # iris rotation: a corner sits at 12 o'clock
BLADES = 6
APOS_H = 0.54            # apostrophe height      (× D); 0 = omit
APOS = dict(w_top=0.31, w_bot=0.115, lean=-0.05, bow_l=-0.03, bow_r=0.012,
            r_top=0.035, r_bot=0.03)

# ---------------------------------------------------------------- artboards -
WORD_EM = 9.0            # wordmark em size (mm) → cap height 6.30 mm
WORD_TRACK = 0.028       # letter-spacing (em)
TAG_EM_K = 0.205         # tagline em as a fraction of the wordmark em
TAG_TRACK = 0.40
MARK_D_MM = 19.0         # badge diameter inside the primary lockup (mm) ≈ 2.1 × cap
GAP_K = 0.30             # badge → wordmark gap (× D)
PAD_K = 0.30             # outer clear space on trimmed masters (× D)

F = {w: Font(FONT_PATH, wght=w) for w in (300, 400, 500, 600, 700)}


# ============================================================ geometry ======
def aperture(d=D, ring=RING, e_k=E_K, apothem=APOTHEM, rot0=ROT0, blades=BLADES,
             apos_h=APOS_H, apos=True, fill=INK, apos_fill=None, **apos_over):
    """The badge: ring + six iris blades + the apostrophe wedge, centred on (0,0)."""
    R, th = d / 2.0, ring * d
    Ri = R - th
    e = e_k * d
    rho = e + apothem * d
    out = []
    if blades:
        for k in range(blades):
            out.append(Shape(disc_minus_disc(Ri, e, rho, rot0 + k * 360.0 / blades), fill))
    out.append(Shape(annulus(0, 0, R, Ri), fill))
    if apos and apos_h:
        kw = dict(APOS)
        kw.update(apos_over)
        h = apos_h * d
        w = wedge(h, kw["w_top"] * h, kw["w_bot"] * h, kw["lean"] * h,
                  kw["bow_l"] * h, kw["bow_r"] * h, kw["r_top"] * h, kw["r_bot"] * h)
        b = w.bbox()
        out.append(Shape([w.translate(-(b[0] + b[2]) / 2.0, -(b[1] + b[3]) / 2.0)],
                         apos_fill or fill))
    return out


def word(text=NAME, em=WORD_EM, tracking=WORD_TRACK, weight=F_WORD, fill=INK,
         x=0.0, y=0.0):
    shapes, adv = F[weight].glyph_shapes(text, em, tracking, x, y)
    return [Shape([sp for s in shapes for sp in s.subpaths], fill)], adv


def ink_bbox(shapes):
    boxes = [s.bbox() for s in shapes]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def trim(shapes, pad):
    x0, y0, x1, y1 = ink_bbox(shapes)
    return ([s.translated(pad - x0, pad - y0) for s in shapes],
            (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad))


def mark(d_mm, simple=False, fill=INK, apos_fill=None, **kw):
    return [s.scaled(d_mm / D) for s in aperture(blades=0 if simple else BLADES,
                                                  fill=fill, apos_fill=apos_fill, **kw)]


# ============================================================ compositions ===
def primary(cap_em=WORD_EM, mark_mm=MARK_D_MM, with_tag=True, fill=INK, simple=False):
    """Badge left · wordmark right · tagline tucked under the wordmark."""
    mk = mark(mark_mm, simple=simple, fill=fill)
    wm, _ = word(em=cap_em, fill=fill)
    wx0, wy0, wx1, wy1 = ink_bbox(wm)
    dx = mark_mm * (1.0 + GAP_K) - wx0
    # align the badge with the wordmark's optical centre (x-height band), not its
    # ink box — the descender of the "p" would otherwise drag the badge down
    dy = cap_em * 0.27
    shapes = mk + [s.translated(dx, dy) for s in wm]
    if with_tag:
        tg, _ = word(TAGLINE, em=cap_em * TAG_EM_K, tracking=TAG_TRACK, weight=F_TAG, fill=fill)
        tx0, ty0, tx1, ty1 = ink_bbox(tg)
        # tagline sits *below* the wordmark, flush right with the wordmark's ink
        tag_y = wy1 + dy + cap_em * 0.34 - ty0
        shapes += [s.translated(wx1 + dx - tx1, tag_y) for s in tg]
    return shapes


def stacked(cap_em=WORD_EM * 0.92, mark_mm=None, with_tag=True, fill=INK, simple=False):
    """Badge centred above the wordmark; tagline centred underneath."""
    mark_mm = mark_mm or cap_em * 1.62
    mk = mark(mark_mm, simple=simple, fill=fill)
    wm, _ = word(em=cap_em, fill=fill)
    wx0, wy0, wx1, wy1 = ink_bbox(wm)
    mx0, my0, mx1, my1 = ink_bbox(mk)
    cx = -(wx0 + wx1) / 2.0
    # wordmark baseline sits below the badge, clear of its outline
    base_y = (my1 - my0) / 2.0 + my1 - my0 - (my1 - my0) / 2.0 if False else 0.0
    base_y = my1 + mark_mm * 0.26 - wy0
    shapes = [s.translated(cx, 0) for s in mk] + [s.translated(cx, base_y) for s in wm]
    if with_tag:
        tg, _ = word(TAGLINE, em=cap_em * TAG_EM_K, tracking=TAG_TRACK, weight=F_TAG, fill=fill)
        tx0, ty0, tx1, ty1 = ink_bbox(tg)
        tag_y = base_y + wy1 + cap_em * 0.28 - ty0
        shapes += [s.translated(-(tx0 + tx1) / 2.0, tag_y) for s in tg]
    return shapes


# ============================================================ writers =======
def write_master(name, shapes, pad_mm, bg=None, note=""):
    doc_shapes, (w, h) = trim(shapes, pad_mm)
    doc = Doc(w, h, doc_shapes, bg=bg, name=name)
    path = os.path.join(OUT, "master", name + ".svg")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(svg(doc, title=name.replace("-", " "),
                     desc=(note or f"{NAME} identity — vector master. 1 unit = 1 mm. "
                                    f"Type converted to outlines; no fonts required.")))
    return path, (w, h)


def write_print(name, shapes, pad_mm, bg=None):
    doc_shapes, (w, h) = trim(shapes, pad_mm)
    doc = Doc(w, h, doc_shapes, bg=bg, name=name)
    os.makedirs(os.path.join(OUT, "print"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "eps"), exist_ok=True)
    p1 = os.path.join(OUT, "print", name + ".pdf")
    p2 = os.path.join(OUT, "eps", name + ".eps")
    pdf(doc, p1, title=f"{NAME} — {name}", scale=MM2PT, subject="identity artwork / print",
        keywords="logo, vector, outlined, " + NAME)
    eps(doc, p2, title=f"{NAME} — {name}", scale=MM2PT)
    return (p1, p2), (w, h)


# ============================================================ main ==========
def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for sub in ("master", "print", "eps", "png", "jpg", "icons", "social", "brand"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    prim = primary()
    prim_w = primary(fill="#FFFFFF")
    stk = stacked()
    stk_w = stacked(fill="#FFFFFF")
    mk = mark(40.0)
    mk_w = mark(40.0, fill="#FFFFFF")
    mks = mark(40.0, simple=True)
    wm = word(em=WORD_EM)[0]
    wm_w = word(em=WORD_EM, fill="#FFFFFF")[0]

    masters = [
        ("theapostrophe-primary", prim, MARK_D_MM * PAD_K, None),
        ("theapostrophe-primary-white", prim_w, MARK_D_MM * PAD_K, None),
        ("theapostrophe-stacked", stk, 3.2, None),
        ("theapostrophe-stacked-white", stk_w, 3.2, None),
        ("theapostrophe-mark", mk, 1.6, None),
        ("theapostrophe-mark-white", mk_w, 1.6, None),
        ("theapostrophe-mark-simple", mks, 1.6, None),
        ("theapostrophe-wordmark", wm, 1.6, None),
        ("theapostrophe-wordmark-white", wm_w, 1.6, None),
    ]
    sizes = {}
    for name, shapes, pad, bg in masters:
        _, sizes[name] = write_master(name, shapes, pad, bg)

    for name, shapes, pad, bg in masters[:6] + masters[7:8]:
        write_print(name, shapes, pad, bg)

    # ---------------------------------------------------------------- rasters
    jobs = []
    PNG = [
        ("theapostrophe-primary", (1024, 2048, 4096)),
        ("theapostrophe-primary-white", (2048,)),
        ("theapostrophe-stacked", (1024, 2048)),
        ("theapostrophe-stacked-white", (2048,)),
        ("theapostrophe-mark", (512, 1024, 2048)),
        ("theapostrophe-mark-white", (1024, 2048)),
        ("theapostrophe-mark-simple", (1024,)),
        ("theapostrophe-wordmark", (1024, 2048)),
        ("theapostrophe-wordmark-white", (2048,)),
    ]
    for name, px_list in PNG:
        for px in px_list:
            jobs.append({"svg": os.path.join(OUT, "master", name + ".svg"),
                         "png": os.path.join(OUT, "png", f"{name}-{px}.png"),
                         "width": px, "palette": True})

    # on-background versions (JPG for presentations/print, PNG for slides)
    for name, bg, label, px in (
        ("theapostrophe-primary", PAPER, "on-paper", 2048),
        ("theapostrophe-primary-white", INK, "on-ink", 2048),
        ("theapostrophe-stacked", PAPER, "stacked-on-paper", 2048),
        ("theapostrophe-mark-white", INK, "mark-on-ink", 1024),
    ):
        src = os.path.join(OUT, "master", name + ".svg")
        jobs.append({"svg": src, "png": os.path.join(OUT, "png", f"{label}-{px}.png"),
                     "width": px, "bg": bg})
        jobs.append({"svg": src, "png": os.path.join(OUT, "jpg", f"{label}-{px}.jpg"),
                     "width": px, "bg": bg, "jpeg": True})

    # watermark — white lockup at 42 % opacity, transparent PNG
    wl_shapes, (ww, wh) = trim(prim_w, 2.0)
    wl_doc = Doc(ww, wh, [Shape(s.subpaths, s.fill, opacity=0.42) for s in wl_shapes], name="watermark")
    wp = os.path.join(OUT, "master", "_watermark-white.svg")
    with open(wp, "w") as fh:
        fh.write(svg(wl_doc, title=f"{NAME} watermark", desc="White lockup, 42% opacity"))
    jobs.append({"svg": wp, "png": os.path.join(OUT, "png", "watermark-white-2048.png"), "width": 2048})

    # ---------------------------------------------------------------- icons
    fav_shapes, (fav_w, fav_h) = trim(mark(1000.0, simple=True), 92.0)
    fav_svg = os.path.join(OUT, "icons", "favicon.svg")
    with open(fav_svg, "w") as favf:
        favf.write(svg(Doc(fav_w, fav_h, fav_shapes, name="favicon"), title=f"{NAME} favicon",
                     desc="Simplified badge (ring + apostrophe) for small sizes"))
    for sz in (16, 24, 32, 48, 64, 128):
        jobs.append({"svg": fav_svg, "png": os.path.join(OUT, "icons", f"favicon-{sz}.png"),
                     "width": sz, "palette": True})

    side = 40.0
    icon_shapes = mark(side * 0.78)
    ib = ink_bbox(icon_shapes)
    icon_shapes = [s.translated(side / 2 - (ib[0] + ib[2]) / 2,
                               side / 2 - (ib[1] + ib[3]) / 2) for s in icon_shapes]
    icon_doc = Doc(side, side, icon_shapes, bg=PAPER, name="app-icon")
    icon_svg = os.path.join(OUT, "icons", "app-icon.svg")
    with open(icon_svg, "w") as fh:
        fh.write(svg(icon_doc, title=f"{NAME} app icon",
                     desc="Badge on paper; square, unrounded — let the OS mask it"))
    for nm, sz in (("icon-192", 192), ("icon-512", 512), ("apple-touch-icon-180", 180)):
        jobs.append({"svg": icon_svg, "png": os.path.join(OUT, "icons", nm + ".png"),
                     "width": sz, "bg": PAPER, "palette": True})
    jobs.append({"svg": icon_svg, "png": os.path.join(OUT, "social", "avatar-1024.png"),
                 "width": 1024, "bg": PAPER, "palette": True})

    # ---------------------------------------------------------------- social
    ogw, ogh = 200.0, 105.0                       # 1200 × 630 px @ 6 px/unit
    lock = primary(cap_em=17.0, mark_mm=29.0)
    lb = ink_bbox(lock)
    k = min((ogw - 40) / (lb[2] - lb[0]), (ogh - 40) / (lb[3] - lb[1]))
    lock = [s.scaled(k) for s in lock]
    lb = ink_bbox(lock)
    og_doc = Doc(ogw, ogh, [s.translated((ogw - (lb[2] - lb[0])) / 2 - lb[0],
                                        (ogh - (lb[3] - lb[1])) / 2 - lb[1]) for s in lock],
                 bg=PAPER, name="og-image")
    og_svg = os.path.join(OUT, "social", "og-1200x630.svg")
    with open(og_svg, "w") as fh:
        fh.write(svg(og_doc, title=f"{NAME} — social card", desc="Open Graph card 1200 × 630 px"))
    jobs.append({"svg": og_svg, "png": os.path.join(OUT, "social", "og-1200x630.png"),
                 "width": 1200, "bg": PAPER})
    jobs.append({"svg": og_svg, "png": os.path.join(OUT, "social", "og-1200x630.jpg"),
                 "width": 1200, "bg": PAPER, "jpeg": True})

    # ---------------------------------------------------------------- sheet
    sheet_doc = build_identity_sheet(prim, stk, mk)
    sheet_svg = os.path.join(OUT, "brand", "theapostrophe-identity-sheet.svg")
    with open(sheet_svg, "w") as fh:
        fh.write(svg(sheet_doc, title=f"{NAME} — identity sheet", desc="A4, 210 × 297 mm"))
    pdf(sheet_doc, os.path.join(OUT, "brand", "theapostrophe-identity-sheet.pdf"),
        title=f"{NAME} — identity sheet", scale=MM2PT, subject="brand sheet")

    jobs.append({"svg": sheet_svg, "png": os.path.join(OUT, "brand", "theapostrophe-identity-sheet.png"),
                 "width": 1654, "bg": PAPER})

    # README / landing-page previews (kept fresh on every build)
    assets = os.path.join(ROOT, "assets")
    for name, px, bg in (("theapostrophe-primary", 1200, None),
                         ("theapostrophe-mark", 600, None),
                         ("theapostrophe-stacked", 900, None)):
        jobs.append({"svg": os.path.join(OUT, "master", name + ".svg"),
                     "png": os.path.join(assets, "preview-" + name.replace("theapostrophe-", "") + ".png"),
                     "width": px, "bg": bg})
    jobs.append({"svg": sheet_svg, "png": os.path.join(assets, "preview-identity-sheet.png"),
                 "width": 1100, "bg": PAPER})

    with open(os.path.join(OUT, "jobs.json"), "w") as fh:
        json.dump(jobs, fh, indent=1)

    print(f"masters  : {len(masters)} svg  +  {len(masters[:6]) + 1} pdf/eps pairs")
    print(f"rasters  : {len(jobs)} jobs → build/jobs.json")
    return jobs


# ============================================================ brand sheet ===
def _place(shapes, x=None, y=None, cx=None, cy=None):
    """Move a group so its ink box sits at x / y (top-left) or cx / cy (centre)."""
    b = ink_bbox(shapes)
    dx = (x - b[0]) if x is not None else ((cx - (b[0] + b[2]) / 2.0) if cx is not None else 0.0)
    dy = (y - b[1]) if y is not None else ((cy - (b[1] + b[3]) / 2.0) if cy is not None else 0.0)
    return [s.translated(dx, dy) for s in shapes]


def build_identity_sheet(prim, stk, mk):
    """A4 portrait identity sheet: lockups, reversed marks, palette, type, rules."""
    W, H, MG = 210.0, 297.0, 16.0
    shapes = []

    def text(txt, em, weight=F_WORD, track=0.0, fill=INK):
        sh, _ = F[weight].glyph_shapes(txt, em, track, 0, 0)
        return [Shape([sp for s in sh for sp in s.subpaths], fill)]

    def label(txt, x, y, fill=MUTED):
        return _place(text(txt, 2.4, F_TAG, 0.30, fill), x=x, y=y)

    def rule(x1, y1, x2, y2, w=0.25, fill=INK):
        import math as _m
        ang = _m.atan2(y2 - y1, x2 - x1)
        dx, dy = -_m.sin(ang) * w / 2.0, _m.cos(ang) * w / 2.0
        return [Shape([rounded_polygon([(x1 + dx, y1 + dy), (x2 + dx, y2 + dy),
                                        (x2 - dx, y2 - dy), (x1 - dx, y1 - dy)], 0.0)], fill)]

    def swatch(x, y, w, h, fill, border=None, r=1.2):
        """Colour chip; `border` draws a 0.4 mm outline (outer + reversed inner path)."""
        out = [Shape(rounded_polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], r), fill)]
        if border:
            t = 0.4
            inner = rounded_polygon([(x + t, y + t), (x + w - t, y + t),
                                     (x + w - t, y + h - t), (x + t, y + h - t)], max(r - t, 0.0))
            outline = rounded_polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], r)
            out.append(Shape([outline, inner.reverse()], border))
        return out

    # ---- header -----------------------------------------------------------
    shapes += _place(text("IDENTITY SHEET", 3.6, F_TAG, 0.40), x=MG, y=14)
    shapes += _place(text(NAME, 13.4, F_WORD, -0.012), x=MG, y=21)
    shapes += rule(MG, 39.5, W - MG, 39.5, 0.5)

    # ---- primary lockup ---------------------------------------------------
    big = primary(cap_em=13.0, mark_mm=23.0)
    shapes += label("PRIMARY LOCKUP  ·  horizontal", MG, 46)
    shapes += _place(big, cx=W / 2, y=52)

    # ---- badge + stacked --------------------------------------------------
    shapes += label("BADGE", MG, 96)
    shapes += label("STACKED LOCKUP", MG + 78, 96)
    badge_big = [s.scaled(42.0 / 40.0) for s in mk]           # 42 mm badge
    shapes += _place(badge_big, x=MG, y=101)
    st = [s.scaled(0.80) for s in stk]
    shapes += _place(st, x=MG + 78, y=101)

    # ---- reversed applications -------------------------------------------
    shapes += label("REVERSED USAGE", MG, 152)
    chip_y, chip_w, chip_h = 157.0, 84.0, 26.0
    shapes += swatch(MG, chip_y, chip_w, chip_h, INK)
    rmk = [Shape(s.subpaths, PAPER) for s in mark(14.0)]
    shapes += _place(rmk, x=MG + 8, cy=chip_y + chip_h / 2)
    rwm = word(em=4.6, fill=PAPER)[0]
    shapes += _place(rwm, x=MG + 27, cy=chip_y + chip_h / 2)
    shapes += swatch(MG + 94, chip_y, chip_w, chip_h, PAPER)
    shapes += _place(mark(14.0), x=MG + 102, cy=chip_y + chip_h / 2)
    shapes += _place(word(em=4.6)[0], x=MG + 121, cy=chip_y + chip_h / 2)

    # ---- palette ----------------------------------------------------------
    py = 196.0
    shapes += _place(text("PALETTE", 3.0, F_WORD, 0.30), x=MG, y=py)
    for i, (col, nm, hexv, cmyk, border) in enumerate(
            [(INK, "STUDIO INK", "#16130E", "C 0 / M 13 / Y 36 / K 91", None),
             (PAPER, "PAPER", "#F7F3EC", "C 0 / M 2 / Y 5 / K 3", "#C9C2B4"),
             (GOLD, "BRASS · ACCENT", "#C08F2C", "C 0 / M 25 / Y 77 / K 25", None)]):
        x = MG + i * 60.0
        shapes += swatch(x, py + 6, 36, 16, col, border)
        shapes += _place(text(nm, 2.6, F_WORD, 0.18), x=x, y=py + 26)
        shapes += _place(text(hexv, 2.4, F_TAG, 0.06, MUTED), x=x, y=py + 31)
        shapes += _place(text(cmyk, 2.2, F_TAG, 0.02, MUTED), x=x, y=py + 35.5)

    # ---- type -------------------------------------------------------------
    ty = 246.0
    shapes += _place(text("TYPEFACE  ·  JOST", 3.0, F_WORD, 0.30), x=MG, y=ty)
    shapes += _place(text("Jost 400 / 500 for lockups  ·  tracking -1 % to +3 %  ·  type is outlined in all artwork",
                          2.4, F_TAG, 0.06, MUTED), x=MG, y=ty + 6)
    shapes += _place(text("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 4.6, F_WORD, 0.02), x=MG, y=ty + 12)
    shapes += _place(text("abcdefghijklmnopqrstuvwxyz   0123456789   \u2019", 4.6, F_TAG, 0.02), x=MG, y=ty + 19)

    # ---- footer -----------------------------------------------------------
    shapes += rule(MG, H - 18, W - MG, H - 18, 0.3)
    shapes += _place(text("Clear space \u2265 0.35 \u00d7 badge diameter  \u00b7  badge min. 8 mm / 24 px  "
                          "\u00b7  wordmark cap height min. 1.5 mm", 2.3, F_TAG, 0.06, MUTED),
                     x=MG, y=H - 14)
    shapes += _place(text(f"{NAME} \u2014 photography  \u00b7  vector identity v1.0  \u00b7  "
                          f"type set in Jost (SIL OFL)", 2.3, F_TAG, 0.08, MUTED), x=MG, y=H - 9)

    return Doc(W, H, shapes, bg=PAPER, name="identity-sheet")


if __name__ == "__main__":
    main()
