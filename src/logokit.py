"""
logokit — a tiny, dependency-light vector toolkit used to build the
"theapostrophe" identity.

One geometry model -> SVG (master), PDF (print) and EPS (legacy print) output.
Only the standard library is used at build time, plus fontTools for turning
type into outlines (run `pip install fonttools` inside a venv).

Author: identity build script for theapostrophe (photography).
"""

from __future__ import annotations

import math
import re

# --------------------------------------------------------------------------
# path parsing / normalising
# --------------------------------------------------------------------------

_TOK = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


class SubPath:
    """A single closed/open contour stored as cubic + line segments."""

    __slots__ = ("start", "ops", "closed")

    def __init__(self, start, ops=None, closed=False):
        self.start = (float(start[0]), float(start[1]))
        self.ops = list(ops or [])          # ("L", (x, y)) | ("C", (c1), (c2), (p))
        self.closed = closed

    # -- helpers ---------------------------------------------------------
    def end_point(self):
        if not self.ops:
            return self.start
        return self.ops[-1][-1]

    def copy(self):
        return SubPath(self.start, list(self.ops), self.closed)

    def transform(self, fn):
        sp = SubPath(fn(*self.start), closed=self.closed)
        for op in self.ops:
            if op[0] == "L":
                sp.ops.append(("L", fn(*op[1])))
            else:
                sp.ops.append(("C", fn(*op[1]), fn(*op[2]), fn(*op[3])))
        return sp

    def translate(self, dx, dy):
        return self.transform(lambda x, y: (x + dx, y + dy))

    def scale(self, sx, sy=None):
        sy = sx if sy is None else sy
        return self.transform(lambda x, y: (x * sx, y * sy))

    def rotate(self, deg, cx=0.0, cy=0.0):
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)

        def fn(x, y):
            x, y = x - cx, y - cy
            return (cx + x * ca - y * sa, cy + x * sa + y * ca)

        return self.transform(fn)

    def reverse(self):
        """Same contour walked backwards (control points reordered)."""
        segs = list(self.ops)
        nodes = [self.start]
        for op in self.ops:
            nodes.append(op[-1])
        out = SubPath(nodes[-1], closed=self.closed)
        cur = nodes[-1]
        for i in range(len(segs) - 1, -1, -1):
            op = segs[i]
            if op[0] == "L":
                out.ops.append(("L", nodes[i]))
            else:
                out.ops.append(("C", op[2], op[1], nodes[i]))
        return out

    def sample(self, per_curve=16):
        """Polyline approximation (used for bounds / area / offsetting)."""
        pts = [self.start]
        cur = self.start
        for op in self.ops:
            if op[0] == "L":
                pts.append(op[1])
                cur = op[1]
            else:
                _, c1, c2, p = op
                for i in range(1, per_curve + 1):
                    t = i / per_curve
                    mt = 1 - t
                    x = (mt**3) * cur[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t**3 * p[0]
                    y = (mt**3) * cur[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t**3 * p[1]
                    pts.append((x, y))
                cur = p
        if abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
            pts.pop()
        return pts

    def bbox(self):
        xs = [self.start[0]]
        ys = [self.start[1]]
        for op in self.ops:
            for p in op[1:]:
                xs.append(p[0])
                ys.append(p[1])
        return min(xs), min(ys), max(xs), max(ys)

    def signed_area(self):
        pts = self.sample(per_curve=24)
        a = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            a += x1 * y2 - x2 * y1
        return a / 2.0

    def d(self, prec=3):
        """Serialise back to an SVG path string."""
        f = lambda v: _fmt(v, prec)
        parts = [f"M{f(self.start[0])} {f(self.start[1])}"]
        for op in self.ops:
            if op[0] == "L":
                parts.append(f"L{f(op[1][0])} {f(op[1][1])}")
            else:
                c1, c2, p = op[1], op[2], op[3]
                parts.append(
                    f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p[0])} {f(p[1])}"
                )
        if self.closed:
            parts.append("Z")
        return "".join(parts)


def _fmt(v, prec=3):
    s = f"{v:.{prec}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s if s not in ("-0", "") else "0"


def parse_d(d):
    """Parse an SVG path string into [SubPath]. Supports M L H V C S Q T Z."""
    toks = _TOK.findall(d or "")
    i = 0
    out = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    sp = None
    prev_cubic_c = None
    prev_quad_c = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    cmd = None
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
        elif cmd is None:
            raise ValueError("path data must start with a command")
        rel = cmd.islower()
        c = cmd.upper()

        if c == "M":
            x, y = num(), num()
            if rel:
                x, y = cur[0] + x, cur[1] + y
            cur = (x, y)
            start = cur
            sp = SubPath(cur)
            out.append(sp)
            cmd = "l" if rel else "L"
            prev_cubic_c = prev_quad_c = None
            continue
        if c == "L":
            x, y = num(), num()
            if rel:
                x, y = cur[0] + x, cur[1] + y
            sp.ops.append(("L", (x, y)))
            cur = (x, y)
            prev_cubic_c = prev_quad_c = None
            continue
        if c == "H":
            x = num()
            x = cur[0] + x if rel else x
            sp.ops.append(("L", (x, cur[1])))
            cur = (x, cur[1])
            prev_cubic_c = prev_quad_c = None
            continue
        if c == "V":
            y = num()
            y = cur[1] + y if rel else y
            sp.ops.append(("L", (cur[0], y)))
            cur = (cur[0], y)
            prev_cubic_c = prev_quad_c = None
            continue
        if c in ("C", "S"):
            if c == "C":
                x1, y1, x2, y2, x, y = (num() for _ in range(6))
                if rel:
                    x1, y1, x2, y2, x, y = (x1 + cur[0], y1 + cur[1], x2 + cur[0], y2 + cur[1], x + cur[0], y + cur[1])
            else:
                x2, y2, x, y = (num() for _ in range(4))
                if rel:
                    x2, y2, x, y = (x2 + cur[0], y2 + cur[1], x + cur[0], y + cur[1])
                if prev_cubic_c is None:
                    x1, y1 = cur
                else:
                    x1, y1 = (2 * cur[0] - prev_cubic_c[0], 2 * cur[1] - prev_cubic_c[1])
            sp.ops.append(("C", (x1, y1), (x2, y2), (x, y)))
            prev_cubic_c = (x2, y2)
            prev_quad_c = None
            cur = (x, y)
            continue
        if c in ("Q", "T"):
            if c == "Q":
                qx, qy, x, y = (num() for _ in range(4))
                if rel:
                    qx, qy, x, y = (qx + cur[0], qy + cur[1], x + cur[0], y + cur[1])
            else:
                x, y = num(), num()
                if rel:
                    x, y = (x + cur[0], y + cur[1])
                qx, qy = (cur if prev_quad_c is None else (2 * cur[0] - prev_quad_c[0], 2 * cur[1] - prev_quad_c[1]))
            c1 = (cur[0] + 2.0 / 3 * (qx - cur[0]), cur[1] + 2.0 / 3 * (qy - cur[1]))
            c2 = (x + 2.0 / 3 * (qx - x), y + 2.0 / 3 * (qy - y))
            sp.ops.append(("C", c1, c2, (x, y)))
            prev_quad_c = (qx, qy)
            prev_cubic_c = None
            cur = (x, y)
            continue
        if c == "Z":
            sp.closed = True
            cur = start
            prev_cubic_c = prev_quad_c = None
            continue
        raise ValueError(f"unsupported path command: {cmd}")
    return out


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------

_KAPPA = 0.5522847498307936


def circle(cx, cy, r):
    k = r * _KAPPA
    sp = SubPath((cx, cy - r))
    sp.ops = [
        ("C", (cx + k, cy - r), (cx + r, cy - k), (cx + r, cy)),
        ("C", (cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)),
        ("C", (cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)),
        ("C", (cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)),
    ]
    sp.closed = True
    return sp


def annulus(cx, cy, r_out, r_in, hole_ccw=True):
    outer = circle(cx, cy, r_out)
    inner = circle(cx, cy, r_in)
    if (inner.signed_area() > 0) == hole_ccw:
        inner = inner.reverse()
    return [outer, inner]


def rounded_rect(x, y, w, h, r):
    k = r * _KAPPA
    sp = SubPath((x + r, y))
    sp.ops = [
        ("L", (x + w - r, y)),
        ("C", (x + w - r + k, y), (x + w, y + r - k), (x + w, y + r)),
        ("L", (x + w, y + h - r)),
        ("C", (x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h)),
        ("L", (x + r, y + h)),
        ("C", (x + r - k, y + h), (x, y + h - r + k), (x, y + h - r)),
        ("L", (x, y + r)),
        ("C", (x, y + r - k), (x + r - k, y), (x + r, y)),
    ]
    sp.closed = True
    return sp


def catmull_to_cubics(points, closed=False, tension=1.0):
    """Smooth a polyline into a chain of cubic segments (Catmull-Rom)."""
    pts = list(points)
    n = len(pts)
    if n < 2:
        return SubPath(pts[0] if pts else (0, 0))
    sp = SubPath(pts[0], closed=closed)
    seg_end = n if closed else n - 1
    for i in range(seg_end):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[0]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0 * tension, p1[1] + (p2[1] - p0[1]) / 6.0 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0 * tension, p2[1] - (p3[1] - p1[1]) / 6.0 * tension)
        sp.ops.append(("C", c1, c2, p2))
    if closed:
        sp.closed = True
        # last segment closes back onto the first point
        sp.ops[-1] = ("C", sp.ops[-1][1], sp.ops[-1][2], pts[0])
    return sp


def bezier_point(p0, p1, p2, p3, t):
    mt = 1 - t
    return (
        mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
        mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1],
    )


def bezier_tangent(p0, p1, p2, p3, t):
    mt = 1 - t
    x = 3 * mt * mt * (p1[0] - p0[0]) + 6 * mt * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0])
    y = 3 * mt * mt * (p1[1] - p0[1]) + 6 * mt * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1])
    return x, y


# --------------------------------------------------------------------------
# shape container document
# --------------------------------------------------------------------------


class Shape:
    """A filled path with a colour — the atom every exporter understands."""

    __slots__ = ("subpaths", "fill", "evenodd", "opacity", "id")

    def __init__(self, subpaths, fill="#000000", evenodd=False, opacity=1.0, id=None):
        if isinstance(subpaths, SubPath):
            subpaths = [subpaths]
        self.subpaths = list(subpaths)
        self.fill = fill
        self.evenodd = evenodd
        self.opacity = float(opacity)
        self.id = id

    def translated(self, dx, dy):
        return Shape([s.translate(dx, dy) for s in self.subpaths], self.fill, self.evenodd, self.opacity, self.id)

    def scaled(self, sx, sy=None):
        return Shape([s.scale(sx, sy) for s in self.subpaths], self.fill, self.evenodd, self.opacity, self.id)

    def rotated(self, deg, cx=0.0, cy=0.0):
        return Shape([s.rotate(deg, cx, cy) for s in self.subpaths], self.fill, self.evenodd, self.opacity, self.id)

    def bbox(self):
        boxes = [s.bbox() for s in self.subpaths]
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))

    def d(self, prec=3):
        return "".join(s.d(prec) for s in self.subpaths)

    def with_fill(self, fill):
        return Shape(self.subpaths, fill, self.evenodd, self.opacity, self.id)


class Doc:
    """A finished artwork: a canvas size, an optional background, shapes."""

    def __init__(self, width, height, shapes=None, bg=None, name="artwork"):
        self.width = float(width)
        self.height = float(height)
        self.shapes = list(shapes or [])
        self.bg = bg
        self.name = name

    def add(self, shape):
        self.shapes.append(shape)
        return shape


# --------------------------------------------------------------------------
# exporters
# --------------------------------------------------------------------------


def svg(doc: Doc, title=None, desc=None, extra_attrs=""):
    w, h = doc.width, doc.height
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(w)} {_fmt(h)}" '
        f'width="{_fmt(w)}" height="{_fmt(h)}"{extra_attrs}>'
    ]
    out.append(f"<title>{title or doc.name}</title>")
    if desc:
        out.append(f"<desc>{desc}</desc>")
    if doc.bg:
        out.append(f'<rect width="{_fmt(w)}" height="{_fmt(h)}" fill="{doc.bg}"/>')
    for s in doc.shapes:
        attrs = f'fill="{s.fill}"'
        if s.evenodd:
            attrs += ' fill-rule="evenodd"'
        if s.opacity < 1:
            attrs += f' opacity="{round(s.opacity, 4)}"'
        if s.id:
            attrs += f' id="{s.id}"'
        out.append(f"<path {attrs} d=\"{s.d(3)}\"/>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _rgb(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _pdf_string(text):
    """PDF literal string, escaped; non-ASCII becomes UTF-16BE with a BOM."""
    text = str(text)
    try:
        raw = text.encode("ascii")
        return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"
    except UnicodeEncodeError:
        return b"<" + (b"\xfe\xff" + text.encode("utf-16-be")).hex().encode("ascii") + b">"


def _pdf_ascii(text):
    """ASCII-safe version of a comment string (for EPS headers)."""
    repl = {"\u2014": "-", "\u2013": "-", "\u2019": "'", "\u2018": "'",
            "\u00d7": "x", "\u00b7": "-", "\u2265": ">=", "\u2264": "<=", "\u2022": "*"}
    for k, v in repl.items():
        text = text.replace(k, v)
    return text.encode("ascii", "replace").decode("ascii")


def _pdf_num(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def pdf(doc: Doc, path, title="theapostrophe", scale=1.0, creator="theapostrophe identity build",
        subject="", keywords=""):
    """Minimal, standards-clean vector PDF writer (pure path fills).

    `scale` converts document units to PostScript points (mm -> 2.834645669).
    """
    w, h = doc.width * scale, doc.height * scale
    U = lambda v: v * scale
    # content stream (PDF origin is bottom-left -> flip y)
    ops = []
    gstates = {}
    for s in doc.shapes:
        if s.opacity < 1:
            key = round(s.opacity, 3)
            if key not in gstates:
                gstates[key] = f"GS{len(gstates) + 1}"
            ops.append(f"/{gstates[key]} gs")
        r, g, b = _rgb(s.fill)
        ops.append(f"{_pdf_num(r)} {_pdf_num(g)} {_pdf_num(b)} rg")
        for sp in s.subpaths:
            ops.append(f"{_pdf_num(U(sp.start[0]))} {_pdf_num(h - U(sp.start[1]))} m")
            for op in sp.ops:
                if op[0] == "L":
                    ops.append(f"{_pdf_num(U(op[1][0]))} {_pdf_num(h - U(op[1][1]))} l")
                else:
                    _, c1, c2, p = op
                    ops.append(
                        f"{_pdf_num(U(c1[0]))} {_pdf_num(h - U(c1[1]))} {_pdf_num(U(c2[0]))} {_pdf_num(h - U(c2[1]))} "
                        f"{_pdf_num(U(p[0]))} {_pdf_num(h - U(p[1]))} c"
                    )
            ops.append("h")
        ops.append("f*" if s.evenodd else "f")
    content = "\n".join(ops).encode("ascii")

    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    if gstates:
        entries = " ".join(
            f"/{name} << /ca {_pdf_num(alpha)} /CA {_pdf_num(alpha)} /BM /Normal >>"
            for alpha, name in sorted(gstates.items())
        )
        res = "{ /ExtGState << " + entries + " >> }"
    else:
        res = "<< >>"
    objects.append(
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_pdf_num(w)} {_pdf_num(h)}] "
            f"/Resources {res} /Contents 4 0 R >>"
        ).encode("ascii")
    )
    objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    info = (b"<< /Title " + _pdf_string(title) + b" /Creator " + _pdf_string(creator)
            + (b" /Subject " + _pdf_string(subject) if subject else b"")
            + (b" /Keywords " + _pdf_string(keywords) if keywords else b"")
            + b" /Producer " + _pdf_string("logokit, pure-Python vector export") + b" >>")
    objects.append(info)

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {n} /Root 1 0 R /Info {len(objects)} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return path


def eps(doc: Doc, path, title="theapostrophe", scale=1.0, creator="theapostrophe identity build (logokit)"):
    """Encapsulated PostScript (Level 2) — vector, for legacy print / signage."""
    w, h = doc.width * scale, doc.height * scale
    U = lambda v: v * scale
    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: theapostrophe identity build (logokit)",
        "%%Title: " + _pdf_ascii(title),
        f"%%BoundingBox: 0 0 {int(math.ceil(w))} {int(math.ceil(h))}",
        f"%%HiResBoundingBox: 0 0 {w:.3f} {h:.3f}",
        "%%LanguageLevel: 2",
        "%%Pages: 1",
        "%%EndComments",
        "%%BeginProlog",
        "%%EndProlog",
        "%%Page: 1 1",
        "gsave",
    ]
    for s in doc.shapes:
        r, g, b = _rgb(s.fill)
        lines.append(f"{_pdf_num(r)} {_pdf_num(g)} {_pdf_num(b)} setrgbcolor")
        lines.append("newpath")
        for sp in s.subpaths:
            lines.append(f"{_pdf_num(U(sp.start[0]))} {_pdf_num(h - U(sp.start[1]))} moveto")
            for op in sp.ops:
                if op[0] == "L":
                    lines.append(f"{_pdf_num(U(op[1][0]))} {_pdf_num(h - U(op[1][1]))} lineto")
                else:
                    _, c1, c2, p = op
                    lines.append(
                        f"{_pdf_num(U(c1[0]))} {_pdf_num(h - U(c1[1]))} {_pdf_num(U(c2[0]))} {_pdf_num(h - U(c2[1]))} "
                        f"{_pdf_num(U(p[0]))} {_pdf_num(h - U(p[1]))} curveto"
                    )
            lines.append("closepath")
        lines.append("eofill" if s.evenodd else "fill")
    lines += ["grestore", "showpage", "%%EOF"]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# --------------------------------------------------------------------------
# type -> outlines
# --------------------------------------------------------------------------

try:  # pragma: no cover - optional at import time
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.misc.transform import Transform

    HAVE_FONTTOOLS = True
except Exception:  # pragma: no cover
    HAVE_FONTTOOLS = False


class Font:
    """A typeface instance, exposed as outlined vector geometry."""

    def __init__(self, path, wght=None):
        if not HAVE_FONTTOOLS:
            raise RuntimeError("fontTools is required to convert text into outlines")
        font = TTFont(path)
        if wght is not None and "fvar" in font:
            axes = {a.axisTag: a for a in font["fvar"].axes}
            loc = {}
            if "wght" in axes:
                loc["wght"] = max(axes["wght"].minValue, min(axes["wght"].maxValue, wght))
            font = instantiateVariableFont(font, loc, inplace=False, updateFontNames=False)
        self.font = font
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.glyphset = font.getGlyphSet()
        self.hmtx = font["hmtx"]
        self.ascent = font["hhea"].ascent
        self.descent = font["hhea"].descent
        os2 = font["OS/2"]
        self.cap = getattr(os2, "sCapHeight", None) or int(self.upm * 0.7)
        self.xheight = getattr(os2, "sxHeight", None) or int(self.upm * 0.5)

    def glyph_shapes(self, text, size, tracking=0.0, x=0.0, y=0.0, kerning=None):
        """Lay out `text`, returning (list[Shape], advance_width).

        `size`     – em size in user units
        `tracking` – extra letter-spacing in em units (0.02 = 2%)
        `x`, `y`   – pen origin (glyph baseline start)
        """
        scale = size / self.upm
        kerning = kerning or {}
        shapes = []
        pen_x = 0.0
        prev = None
        n = len(text)
        for idx, ch in enumerate(text):
            gname = self.cmap.get(ord(ch))
            if gname is None:
                raise ValueError(f"glyph for {ch!r} not found")
            if prev is not None:
                pen_x += kerning.get(prev + ch, 0.0) * scale
            pen = SVGPathPen(self.glyphset)
            self.glyphset[gname].draw(pen)
            d = pen.getCommands()
            if d.strip():
                sps = parse_d(d)
                # pen_x is already in user units; only the glyph outline is scaled
                sps = [sp.transform(lambda gx, gy: (x + pen_x + gx * scale, y - gy * scale)) for sp in sps]
                shapes.append(Shape(sps))
            pen_x += self.hmtx[gname][0] * scale
            if idx < n - 1:
                pen_x += tracking * size
            prev = gname
        return shapes, pen_x

    def text_shape(self, text, size, tracking=0.0, x=0.0, y=0.0, fill="#000", kerning=None):
        shapes, adv = self.glyph_shapes(text, size, tracking, x, y, kerning)
        sps = [sp for s in shapes for sp in s.subpaths]
        return Shape(sps, fill), adv

    def measure(self, text, size, tracking=0.0):
        """Total advance width of `text` (glyph advances + tracking)."""
        scale = size / self.upm
        w = sum(self.hmtx[self.cmap[ord(c)]][0] for c in text) * scale
        w += tracking * size * max(0, len(text) - 1)
        return w

    def ink_bbox(self, text, size, tracking=0.0, x=0.0, y=0.0, kerning=None):
        shapes, _ = self.glyph_shapes(text, size, tracking, x, y, kerning)
        sub = [sp for s in shapes for sp in s.subpaths]
        if not sub:
            return None
        boxes = [sp.bbox() for sp in sub]
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))


def arc(cx, cy, r, a0_deg, a1_deg):
    """Cubic approximation of a circular arc; returns (start_point, ops)."""
    a0 = math.radians(a0_deg)
    a1 = math.radians(a1_deg)
    delta = a1 - a0
    n = max(1, int(math.ceil(abs(delta) / (math.pi / 2) - 1e-9)))
    step = delta / n
    k = 4.0 / 3.0 * math.tan(step / 4.0)
    start = (cx + r * math.cos(a0), cy + r * math.sin(a0))
    ops = []
    for i in range(n):
        t0 = a0 + i * step
        t1 = t0 + step
        p0 = (cx + r * math.cos(t0), cy + r * math.sin(t0))
        p1 = (cx + r * math.cos(t1), cy + r * math.sin(t1))
        d0 = (-math.sin(t0), math.cos(t0))
        d1 = (-math.sin(t1), math.cos(t1))
        c1 = (p0[0] + k * r * d0[0], p0[1] + k * r * d0[1])
        c2 = (p1[0] - k * r * d1[0], p1[1] - k * r * d1[1])
        ops.append(("C", c1, c2, p1))
    return start, ops


# --------------------------------------------------------------------------
# path builder  (exact lines + arcs, no polyline approximation)
# --------------------------------------------------------------------------


class PathBuilder:
    """Small explicit path builder: move/line/curve/corner-arc."""

    def __init__(self, x=0.0, y=0.0):
        self.sp = SubPath((x, y))

    def line_to(self, p):
        self.sp.ops.append(("L", (float(p[0]), float(p[1]))))
        return self

    def curve_to(self, c1, c2, p):
        self.sp.ops.append(("C", tuple(map(float, c1)), tuple(map(float, c2)), (float(p[0]), float(p[1]))))
        return self

    def quad_to(self, c, p, steps=10):
        """Quadratic approximated by `steps` cubics (exact enough at any size)."""
        x0, y0 = self.sp.ops[-1][-1] if self.sp.ops else self.sp.start
        px, py = p
        cx, cy = c
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            def q(t):
                mt = 1 - t
                return (mt * mt * x0 + 2 * mt * t * cx + t * t * px,
                        mt * mt * y0 + 2 * mt * t * cy + t * t * py)
            def d(t):
                mt = 1 - t
                return (2 * mt * (cx - x0) + 2 * t * (px - cx), 2 * mt * (cy - y0) + 2 * t * (py - cy))
            p0, p1 = q(t0), q(t1)
            d0, d1 = d(t0), d(t1)
            k = (t1 - t0) / 3.0
            self.curve_to((p0[0] + k * d0[0], p0[1] + k * d0[1]), (p1[0] - k * d1[0], p1[1] - k * d1[1]), p1)
        return self

    def arc_corner(self, corner, p_from, p_to):
        """Rounded corner at `corner` between tangents p_from->corner->p_to."""
        self.quad_to(corner, p_to, steps=8)
        return self

    def close(self):
        self.sp.closed = True
        return self

    @property
    def shape(self):
        return self.sp


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return (dx / n, dy / n)


def rounded_polygon(points, radius):
    """Closed polygon with every corner rounded by a single radius (or list)."""
    n = len(points)
    radii = radius if isinstance(radius, (list, tuple)) else [radius] * n
    starts = []
    for i in range(n):
        p_prev, p, p_next = points[(i - 1) % n], points[i], points[(i + 1) % n]
        r = radii[i]
        d_in = _unit(p, p_prev)
        d_out = _unit(p, p_next)
        len_in = math.hypot(p[0] - p_prev[0], p[1] - p_prev[1])
        len_out = math.hypot(p_next[0] - p[0], p_next[1] - p[1])
        r = min(r, len_in / 2.0, len_out / 2.0)
        starts.append(((p[0] + d_in[0] * r, p[1] + d_in[1] * r),
                       (p[0] + d_out[0] * r, p[1] + d_out[1] * r)))
    pb = PathBuilder(*starts[0][0])
    for i in range(n):
        _, t_out = starts[i]
        t_in_next, _ = starts[(i + 1) % n]
        pb.line_to(t_in_next)
        pb.arc_corner(points[(i + 1) % n], t_in_next, _)
    pb.close()
    return pb.shape


def aperture_blades(R_in, count=6, spread=1.6, sweep=360.0, blade_radius=None, rot0=0.0):
    """Camera-iris blades: circular arcs closed by a chord, then rotated."""
    blade_radius = blade_radius if blade_radius is not None else R_in
    out = []
    seg = sweep / count
    for k in range(count):
        a0 = rot0 + k * seg
        a1 = a0 + seg
        st, ops = arc(0, 0, blade_radius, a0, a1)
        sp = SubPath(st, ops, closed=True)
        v0 = (blade_radius * math.cos(math.radians(a0)), blade_radius * math.sin(math.radians(a0)))
        v1 = (blade_radius * math.cos(math.radians(a1)), blade_radius * math.sin(math.radians(a1)))
        m = ((v0[0] + v1[0]) / 2.0, (v0[1] + v1[1]) / 2.0)
        out.append(sp.rotate(spread, m[0], m[1]))
    return out


def wedge(h, w_top, w_bot, lean=0.0, bow_left=0.0, bow_right=0.0,
          r_top=0.0, r_bot=0.0, samples=12):
    """A tapered apostrophe/quotation wedge drawn from explicit curves.

    Origin = top-centre of the shape, +y downwards.  `lean` shifts the bottom
    to the right (positive) so the mark reads as a slanted apostrophe.
    """
    tl = (-w_top / 2.0, 0.0)
    tr = (w_top / 2.0, 0.0)
    br = (w_bot / 2.0 + lean, h)
    bl = (-w_bot / 2.0 + lean, h)

    rt = min(r_top, w_top / 2.0 * 0.95, h / 3.0)
    rb = min(r_bot, w_bot / 2.0 * 0.95, h / 3.0)

    pb = PathBuilder(tl[0] + rt, tl[1])
    # top edge -> top-right corner (quadratic corner)
    pb.line_to((tr[0] - rt, 0.0))
    pb.quad_to(tr, (tr[0] - rt * 0.2, rt), steps=6)
    # right edge, optional outward bow
    end_r = (br[0], br[1] - rb)
    if abs(bow_right) > 1e-6:
        mid = _lerp(tr, end_r, 0.5)
        ctrl = (mid[0] + bow_right, mid[1])
        pb.quad_to(ctrl, end_r, steps=samples)
    else:
        pb.line_to(end_r)
    # bottom-right corner
    pb.quad_to(br, (br[0] - rb * 0.2, br[1] - rb), steps=6)
    # bottom edge
    pb.line_to((bl[0] + rb, bl[1]))
    # bottom-left corner
    pb.quad_to(bl, (bl[0] + rb * 0.2, bl[1] - rb), steps=6)
    # left edge, optional inward (negative) bow
    start_l = (tl[0], tl[1] + rt)
    if abs(bow_left) > 1e-6:
        mid = _lerp(bl, start_l, 0.5)
        ctrl = (mid[0] + bow_left, mid[1])
        pb.quad_to(ctrl, start_l, steps=samples)
    else:
        pb.line_to(start_l)
    # top-left corner
    pb.quad_to(tl, (tl[0] + rt * 0.2, tl[1] + rt), steps=6)
    pb.close()
    return pb.shape


def arc_between(cx, cy, r, p0, p1, through=None):
    """Arc ops on the circle (cx,cy,r) from p0 to p1, passing near `through`.

    `through` is a point (any radius) the chosen arc should head towards; if
    omitted the shorter arc is used.
    """
    a0 = math.degrees(math.atan2(p0[1] - cy, p0[0] - cx))
    a1 = math.degrees(math.atan2(p1[1] - cy, p1[0] - cx))
    if through is None:
        at = None
    else:
        at = math.degrees(math.atan2(through[1] - cy, through[0] - cx))

    def ang_diff(a, b):
        return abs(((a - b) + 180.0) % 360.0 - 180.0)

    # the two arcs that join the points: one <= 180 deg, one > 180 deg
    delta_short = ((a1 - a0 + 180.0) % 360.0) - 180.0
    delta_long = delta_short - 360.0 if delta_short > 0 else delta_short + 360.0
    if at is None or ang_diff(a0 + delta_short / 2.0, at) <= ang_diff(a0 + delta_long / 2.0, at):
        delta = delta_short
    else:
        delta = delta_long
    _, ops = arc(cx, cy, r, a0, a0 + delta)
    return p0, ops


def disc_minus_disc(R, e, rho, phi_deg, samples_note=None):
    """Disc of radius R centred at the origin with a second disc of radius rho,
    centred at distance e in direction phi, removed — i.e. one iris blade when
    the removed disc is the aperture opening.

    The material of the blade is the crescent on the side *opposite* phi.
    """
    phi = math.radians(phi_deg)
    ux, uy = math.cos(phi), math.sin(phi)
    C = (e * ux, e * uy)                     # centre of the removed disc
    a = (e * e - rho * rho + R * R) / (2.0 * e)
    h = math.sqrt(max(R * R - a * a, 0.0))
    m = (a * ux, a * uy)
    px, py = -uy, ux
    P1 = (m[0] + h * px, m[1] + h * py)
    P2 = (m[0] - h * px, m[1] - h * py)

    # outer arc runs from P1 to P2 the long way round, passing opposite phi
    far = (-R * ux, -R * uy)
    st, ops = arc_between(0.0, 0.0, R, P1, P2, through=far)
    sp = SubPath(st, ops, closed=True)
    # inner arc back from P2 to P1 hugging the aperture (through the near gap)
    near = (C[0] - rho * ux, C[1] - rho * uy)
    _, ops2 = arc_between(C[0], C[1], rho, P2, P1, through=near)
    sp.ops.extend(ops2)
    return sp
