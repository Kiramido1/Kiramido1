#!/usr/bin/env python3
"""
GitHub profile banner generator — dark.svg / light.svg (+ README.md).

Pipeline (per the Master Prompt):
  photo -> head+shoulders crop -> 300x340 -> autocontrast + 1.3x contrast + unsharp
        -> 1-bit Floyd-Steinberg (serpentine) -> dots
  dark : background segmented out, dots draw the LIT subject
  light: background kept, dots draw the DARK parts
  intro: ~60 interleaved random groups fade in (evenness metric checked)
  loop : portrait 3.0s -> logo1 2.0s -> logo2 2.0s -> logo3 2.0s, 1.3s transitions (14.2s)
  two layers: dense portrait (drift bands) + ~900 travellers (optimal-transport morph)

The generator + the .npy files in assets/ are the source of truth. Never hand-edit the SVG.
"""
import json, os, sys, random, math
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from scipy import ndimage
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
OUT = os.path.dirname(HERE)          # repo root: dark.svg / light.svg / README.md land here
CFG = json.load(open("profile.json"))
PAL = CFG["palette"]
random.seed(7); np.random.seed(7)

W, H = 1180, 610                # banner
GW, GH = 300, 340               # dither grid
TITLE_H = 36                    # terminal title bar
PAD = 22
LEFT_W = int(W * 0.38)          # portrait column

# ------------------------------------------------------------------ portrait
def load_portrait():
    im = Image.open(CFG["photo"]).convert("RGB")
    c = CFG["crop"]
    im = im.crop((c["left"], c["top"], c["right"], c["bottom"]))
    # fit to 300:340 aspect (center crop)
    tw, th = im.size
    target = GW / GH
    if tw / th > target:
        nw = int(th * target); im = im.crop(((tw - nw) // 2, 0, (tw - nw) // 2 + nw, th))
    else:
        nh = int(tw / target); im = im.crop((0, (th - nh) // 2, tw, (th - nh) // 2 + nh))
    return im.resize((GW, GH), Image.LANCZOS)

def background_mask(rgb):
    """True = subject. Threshold on colour distance to the background colour
    (sampled from the top corners), binary closing, fill holes, largest component."""
    a = np.asarray(rgb).astype(np.float32)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    # This backdrop is a saturated red vignette: G/R ~0.14, B ~0. Skin (even in shadow) has
    # G/R >= 0.24 and hair/shirt/scarf are dark or neutral, so the chroma ratio separates them.
    is_bg = (G / (R + 1.0) < 0.19) & (B / (R + 1.0) < 0.12) & (R > 18)
    m = ~is_bg
    m = ndimage.binary_opening(m, iterations=2)
    m = ndimage.binary_closing(m, iterations=3)
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    if n > 1:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == (1 + int(np.argmax(sizes)))
    return m

def tone(gray_im):
    im = ImageOps.autocontrast(gray_im, cutoff=1)
    im = ImageEnhance.Contrast(im).enhance(1.3)
    im = im.filter(ImageFilter.UnsharpMask(radius=3, percent=140))
    return np.asarray(im).astype(np.float32) / 255.0

def fs_dither(v):
    """1-bit Floyd-Steinberg, serpentine. v in [0,1] = target ink density. Returns bool dots."""
    v = v.copy(); h, w = v.shape; out = np.zeros((h, w), bool)
    for y in range(h):
        rng = range(w) if y % 2 == 0 else range(w - 1, -1, -1)
        d = 1 if y % 2 == 0 else -1
        for x in rng:
            old = v[y, x]; new = 1.0 if old >= 0.5 else 0.0
            out[y, x] = new > 0.5; err = old - new
            if 0 <= x + d < w: v[y, x + d] += err * 7 / 16
            if y + 1 < h:
                if 0 <= x - d < w: v[y + 1, x - d] += err * 3 / 16
                v[y + 1, x] += err * 5 / 16
                if 0 <= x + d < w: v[y + 1, x + d] += err * 1 / 16
    return out

def build_dots():
    rgb = load_portrait()
    mask = background_mask(rgb)
    g = tone(rgb.convert("L"))
    # DARK: dots = brightness of the lit subject, only inside the mask
    lit = np.maximum(g, 0.07); lit[~mask] = 0.0     # floor keeps the dark shirt as a faint silhouette
    dark = fs_dither(lit)
    inner = ndimage.binary_erosion(mask, iterations=1)
    dark &= inner                                  # hard-clear diffusion bleed at the edge
    # LIGHT: keep background, dots = darkness
    # light mode: dots draw the dark parts. This photo's backdrop is dark red, so left as-is it
    # dithers into a solid slab — flatten the backdrop to a light density so it reads as a backdrop.
    ink = 1.0 - g; ink[~mask] = 0.03
    light = fs_dither(ink)
    np.save("assets/dots_dark.npy", dark); np.save("assets/dots_light.npy", light)
    np.save("assets/mask.npy", mask)
    Image.fromarray((~dark * 255).astype(np.uint8)).resize((GW * 2, GH * 2), Image.NEAREST).save("assets/preview_dark.png")
    Image.fromarray((~light * 255).astype(np.uint8)).resize((GW * 2, GH * 2), Image.NEAREST).save("assets/preview_light.png")
    print(f"mask coverage {mask.mean():.2f} | dark dots {dark.sum()} | light dots {light.sum()}")
    return dark, light, mask

# ------------------------------------------------------------------ logos
def logo_points(spec, n, cx, cy, size):
    """Return n (x,y) points in banner coords sampling the logo's ink."""
    if spec.get("image"):
        im = Image.open(spec["image"]).convert("LA")
        a = np.asarray(im).astype(np.float32)
        ink = (255 - a[..., 0]) / 255.0 * (a[..., 1] / 255.0)
    else:
        S = 400; im = Image.new("L", (S, S), 0); d = ImageDraw.Draw(im)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 300)
        txt = spec["label"]; bb = d.textbbox((0, 0), txt, font=font)
        d.text(((S - (bb[2] - bb[0])) / 2 - bb[0], (S - (bb[3] - bb[1])) / 2 - bb[1]), txt, 255, font=font)
        ink = np.asarray(im).astype(np.float32) / 255.0
    ys, xs = np.nonzero(ink > 0.5)
    if len(xs) < n:
        raise SystemExit(f"logo {spec['label']} has too little ink ({len(xs)} px)")
    idx = np.random.choice(len(xs), n, replace=False)
    px, py = xs[idx].astype(float), ys[idx].astype(float)
    # normalise to a box of `size`
    x0, x1, y0, y1 = px.min(), px.max(), py.min(), py.max()
    sc = size / max(x1 - x0, y1 - y0, 1)
    px = (px - (x0 + x1) / 2) * sc + cx; py = (py - (y0 + y1) / 2) * sc + cy
    return np.stack([px, py], 1)

def ot_match(a, b):
    """Optimal transport (assignment) so each traveller takes the shortest total path."""
    d = ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)
    r, c = linear_sum_assignment(d)
    out = np.empty_like(b); out[r] = b[c]; return out

# ------------------------------------------------------------------ metrics
def evenness(groups, ys, xs, ng, cells=6):
    """Patchiness of the intro: 1 - mean fraction of occupied 6x6 cells each group touches.
    ~0.05 = every group is scattered over the whole portrait (good); ~0.7 = spatial patches."""
    cy = (ys * cells // GH).astype(int); cx = (xs * cells // GW).astype(int)
    cell = cy * cells + cx
    occupied = np.unique(cell)
    cov = [len(np.intersect1d(np.unique(cell[groups == g]), occupied)) / len(occupied)
           for g in range(ng) if (groups == g).any()]
    return float(1 - np.mean(cov))

def straight_boundary(band, ys, xs):
    """Fraction of band-boundary pixels lying on straight runs >= 6px (~0.01 organic, ~0.17 grid)."""
    grid = -np.ones((GH, GW), int); grid[ys, xs] = band
    bx = (grid[:, 1:] != grid[:, :-1]) & (grid[:, 1:] >= 0) & (grid[:, :-1] >= 0)   # vertical boundaries
    by = (grid[1:, :] != grid[:-1, :]) & (grid[1:, :] >= 0) & (grid[:-1, :] >= 0)   # horizontal boundaries
    def runs(b, axis):
        b = b if axis == 0 else b.T
        tot = 0
        for col in b.T:
            n = 0
            for v in col:
                if v: n += 1
                else:
                    if n >= 6: tot += n
                    n = 0
            if n >= 6: tot += n
        return tot
    tot = bx.sum() + by.sum()
    return float((runs(bx, 0) + runs(by, 1)) / max(tot, 1))

# ------------------------------------------------------------------ svg
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def runs_path(ys, xs, ox=0, oy=0, s=1):
    """Dots as <path> runs in integer grid units; for each row, consecutive dots become one bar."""
    parts = []
    order = np.lexsort((xs, ys)); ys, xs = ys[order], xs[order]
    i = 0; n = len(xs)
    while i < n:
        j = i
        while j + 1 < n and ys[j + 1] == ys[i] and xs[j + 1] == xs[j] + 1: j += 1
        parts.append(f"M{xs[i]} {ys[i]}h{j - i + 1}v1h-{j - i + 1}z")
        i = j + 1
    return "".join(parts)

def build_svg(dark_mode, dots, logos_cfg):
    colour = PAL["portrait_dark"] if dark_mode else PAL["portrait_light"]
    chrome = PAL["chrome_dark"] if dark_mode else PAL["chrome_light"]
    bg = PAL["bg"] if dark_mode else PAL["bg_light"]
    panel = "#0D1528" if dark_mode else "#FFFFFF"
    text = PAL["text"] if dark_mode else PAL["text_light"]
    dim = PAL["text_dim"] if dark_mode else PAL["text_dim_light"]
    accent = PAL["accent"]; live = PAL["live"]
    border = "#1E293B" if dark_mode else "#CBD5E1"

    # ---- geometry of the portrait frame
    fx, fy = PAD, TITLE_H + PAD
    fw, fh = LEFT_W - PAD, H - TITLE_H - 2 * PAD
    s = min((fw - 24) / GW, (fh - 44) / GH)          # dot size in px
    pw, ph = GW * s, GH * s
    ox = fx + (fw - pw) / 2; oy = fy + 30 + (fh - 30 - ph) / 2
    ys, xs = np.nonzero(dots); nd = len(xs)
    px = ox + xs * s + s / 2; py = oy + ys * s + s / 2

    # ---- logos (travellers) — positioned inside the frame
    N_TRAV = 900
    lcx, lcy, lsize = ox + pw / 2, oy + ph / 2, min(pw, ph) * 0.62
    L = [logo_points(spec, N_TRAV, lcx, lcy, lsize) for spec in logos_cfg]
    L[1] = ot_match(L[0], L[1]); L[2] = ot_match(L[1], L[2])
    first_centroid = L[0].mean(0)

    # ---- timing
    INTRO = 3.2
    T_P, T_L, T_T = 3.0, 2.0, 1.3
    LOOP = T_P + 3 * T_L + 4 * T_T                   # 14.2
    def kt(*ts): return ";".join(f"{t / LOOP:.4f}" for t in ts)
    t0 = 0; t1 = T_P; t2 = t1 + T_T; t3 = t2 + T_L; t4 = t3 + T_T; t5 = t4 + T_L
    t6 = t5 + T_T; t7 = t6 + T_L; t8 = t7 + T_T      # == LOOP
    KT_ALL = kt(t0, t1, t2, t3, t4, t5, t6, t7, t8)

    # ---- intro layer: ~60 interleaved random groups
    NG = 60
    grp = np.random.randint(0, NG, nd)
    ev = evenness(grp, ys, xs, NG)
    # ---- loop layer: ~94 drift bands. key = distance to logo centroid + noise (sigma 4)
    NB = 94
    d2c = np.sqrt((px - first_centroid[0]) ** 2 + (py - first_centroid[1]) ** 2) / s
    ang = np.arctan2(py - first_centroid[1], px - first_centroid[0])
    key = d2c + np.random.normal(0, 1.2, nd) + 4 * np.sin(ang * 6)   # per-dot noise breaks the ring lattice
    band = np.clip((np.argsort(np.argsort(key)) * NB // nd), 0, NB - 1)
    sb = straight_boundary(band, ys, xs)
    print(f"[{'dark' if dark_mode else 'light'}] dots={nd} dot={s:.2f}px evenness={ev:.3f} (≈0.05 good) straight-boundary={sb:.3f} (≈0.01 organic)")

    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,\'Liberation Mono\',monospace">')
    o.append(f'<rect width="{W}" height="{H}" rx="12" fill="{bg}"/>')
    # title bar
    o.append(f'<rect width="{W}" height="{TITLE_H}" rx="12" fill="{panel}"/><rect y="{TITLE_H - 12}" width="{W}" height="12" fill="{panel}"/>')
    o.append(f'<line x1="0" y1="{TITLE_H}" x2="{W}" y2="{TITLE_H}" stroke="{border}"/>')
    for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        o.append(f'<circle cx="{20 + i * 20}" cy="{TITLE_H / 2}" r="6" fill="{c}"/>')
    o.append(f'<text x="{W / 2}" y="{TITLE_H / 2 + 5}" text-anchor="middle" font-size="13" fill="{dim}">profile.sh --live</text>')
    # portrait frame
    o.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="8" fill="{panel}" stroke="{border}"/>')
    o.append(f'<text x="{fx + 14}" y="{fy + 20}" font-size="13" fill="{chrome}" letter-spacing="1">VISUAL.MAP</text>')
    o.append(f'<line x1="{fx}" y1="{fy + 30}" x2="{fx + fw}" y2="{fy + 30}" stroke="{border}"/>')
    o.append(f'<clipPath id="pc"><rect x="{fx + 1}" y="{fy + 31}" width="{fw - 2}" height="{fh - 32}"/></clipPath>')
    o.append('<g clip-path="url(#pc)">')
    o.append(f'<g transform="translate({ox:.2f} {oy:.2f}) scale({s:.4f})">')   # portrait layers in grid units

    # -- intro layer (plays once, then hides)
    o.append(f'<g fill="{colour}" shape-rendering="crispEdges">')
    o.append(f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.999;1" dur="{INTRO}s" fill="freeze"/>')
    for g in range(NG):
        sel = grp == g
        if not sel.any(): continue
        begin = 2.0 * g / NG
        o.append(f'<path opacity="0" d="{runs_path(ys[sel], xs[sel])}">'
                 f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/></path>')
    o.append('</g>')

    # -- loop layer: portrait drift bands
    o.append(f'<g fill="{colour}" shape-rendering="crispEdges" opacity="0">')
    o.append(f'<animate attributeName="opacity" from="0" to="1" begin="{INTRO}s" dur="0.01s" fill="freeze"/>')
    for b in range(NB):
        sel = band == b
        if not sel.any(): continue
        mx, my = px[sel].mean(), py[sel].mean()
        dx = 0.42 * (first_centroid[0] - mx) / s; dy = 0.42 * (first_centroid[1] - my) / s   # grid units
        o.append(f'<g><path d="{runs_path(ys[sel], xs[sel])}">'
                 f'<animate attributeName="opacity" values="1;1;0;0;0;0;0;0;1" keyTimes="{KT_ALL}" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite"/></path>'
                 f'<animateTransform attributeName="transform" type="translate" values="0 0;0 0;{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f};0 0" keyTimes="{KT_ALL}" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite"/></g>')
    o.append('</g>')
    o.append('</g>')  # end grid transform

    # -- travellers: morph logo1 -> logo2 -> logo3, hidden during portrait
    ts = max(s * 2.2, 3.0)
    # start: scattered at the portrait's own dots (so they emerge from the face), end: back to the same
    start_idx = np.random.choice(nd, N_TRAV, replace=False)
    S0 = np.stack([px[start_idx], py[start_idx]], 1)
    o.append(f'<g fill="{chrome}" opacity="0">')
    o.append(f'<animate attributeName="opacity" from="0" to="1" begin="{INTRO}s" dur="0.01s" fill="freeze"/>')
    for i in range(N_TRAV):
        P = [S0[i], S0[i], L[0][i], L[0][i], L[1][i], L[1][i], L[2][i], L[2][i], S0[i]]
        xv = ";".join(f"{p[0] - ts / 2:.1f}" for p in P); yv = ";".join(f"{p[1] - ts / 2:.1f}" for p in P)
        o.append(f'<rect width="{ts:.1f}" height="{ts:.1f}" rx="{ts / 2:.1f}">'
                 f'<animate attributeName="x" values="{xv}" keyTimes="{KT_ALL}" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="y" values="{yv}" keyTimes="{KT_ALL}" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="0;0;1;1;1;1;1;1;0" keyTimes="{KT_ALL}" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite"/></rect>')
    o.append('</g>')
    o.append('</g>')  # clip

    # ---- SYSTEM.INFO panel
    ix = LEFT_W + PAD; iy = TITLE_H + PAD; iw = W - ix - PAD; ih = fh
    o.append(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="8" fill="{panel}" stroke="{border}"/>')
    o.append(f'<text x="{ix + 14}" y="{iy + 20}" font-size="13" fill="{chrome}" letter-spacing="1">SYSTEM.INFO</text>')
    # LIVE badge (pulsing)
    lx = ix + iw - 74
    o.append(f'<rect x="{lx}" y="{iy + 7}" width="60" height="18" rx="9" fill="{live}" fill-opacity="0.15" stroke="{live}"/>')
    o.append(f'<circle cx="{lx + 12}" cy="{iy + 16}" r="3.5" fill="{live}"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="{lx + 21}" y="{iy + 20.5}" font-size="12" fill="{live}" font-weight="bold">LIVE</text>')
    o.append(f'<line x1="{ix}" y1="{iy + 30}" x2="{ix + iw}" y2="{iy + 30}" stroke="{border}"/>')
    # handle pill
    handle = "@" + CFG["username"]
    pw_ = 14 + len(handle) * 8.6
    o.append(f'<rect x="{ix + 14}" y="{iy + 42}" width="{pw_:.0f}" height="24" rx="12" fill="{chrome}" fill-opacity="0.15" stroke="{chrome}"/>')
    o.append(f'<text x="{ix + 14 + pw_ / 2:.1f}" y="{iy + 59}" text-anchor="middle" font-size="14" fill="{chrome}" font-weight="bold">{esc(handle)}</text>')

    rows = [
        ("Subject", CFG["name"]), ("Role", CFG["role"]), ("Origin", CFG["location"]),
        ("Education", CFG["education"]), ("Status", CFG["status"]), ("ToolChain", CFG["toolchain"]),
        None,
        ("Core.Lang", CFG["languages"]), ("Core.Frontend", CFG["frontend"]), ("Core.Backend", CFG["backend"]),
        ("Core.Database", CFG["database"]), ("Core.Infra", CFG["infra"]),
        None,
        ("Grid.Mail", CFG["email"]), ("Grid.Portfolio", CFG["portfolio"]),
        ("Grid.LinkedIn", CFG["linkedin"].replace("https://www.", "").rstrip("/")),
        ("Grid.GitHub", f"github.com/{CFG['username']}"),
        ("Grid.Facebook", CFG["facebook"].replace("https://www.", "").rstrip("/")),
    ]
    rows = [r for r in rows if r is None or "YOUR-" not in str(r[1])]   # skip unfilled placeholders
    FS = 14; CW = FS * 0.602            # monospace advance at 14px
    COLS = int((iw - 28) / CW)          # characters per row
    y = iy + 92; SP = 23
    for r in rows:
        if r is None: y += SP * 0.45; continue
        label, val = r
        val = str(val)
        maxv = COLS - len(label) - 3
        if len(val) > maxv: val = val[:maxv - 1] + "…"
        dots_n = COLS - len(label) - len(val) - 2
        line = f"{label} {'.' * dots_n} {val}"
        tl = COLS * CW
        o.append(f'<text x="{ix + 14}" y="{y:.1f}" font-size="{FS}" textLength="{tl:.1f}" lengthAdjust="spacingAndGlyphs" fill="{dim}" xml:space="preserve">'
                 f'<tspan fill="{text}">{esc(label)}</tspan> {"." * dots_n} <tspan fill="{accent if label.startswith("Grid") else chrome}">{esc(val)}</tspan></text>')
        y += SP
    # blinking cursor
    o.append(f'<text x="{ix + 14}" y="{y + 4:.1f}" font-size="{FS}" fill="{chrome}">$ <tspan fill="{text}">_<animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/></tspan></text>')
    o.append('</svg>')
    return "\n".join(o)

# ------------------------------------------------------------------ README
def build_readme():
    u = CFG["username"]; inst = CFG["stats_instance"].rstrip("/")
    P = {k: v.lstrip("#") for k, v in PAL.items()}
    li = CFG["linkedin"]; ig = CFG["instagram"]; fb = CFG["facebook"]; em = CFG["email"]; pf = CFG["portfolio"]
    B = []
    # LinkedIn only renders its logo on brand blue #0A66C2 (shields.io bug) — keep brand blue.
    B.append(f'<a href="{li}"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>')
    if pf and "coming soon" not in pf:
        url = pf if pf.startswith("http") else "https://" + pf
        B.append(f'<a href="{url}"><img src="https://img.shields.io/badge/Portfolio-{P["bg"]}?style=for-the-badge&logo=vercel&logoColor={P["chrome_dark"]}&labelColor={P["bg"]}" alt="Portfolio" /></a>')
    if "YOUR-" not in ig:
        B.append(f'<a href="{ig}"><img src="https://img.shields.io/badge/Instagram-{P["bg"]}?style=for-the-badge&logo=instagram&logoColor={P["portrait_dark"]}&labelColor={P["bg"]}" alt="Instagram" /></a>')
    if "YOUR-" not in fb:
        B.append(f'<a href="{fb}"><img src="https://img.shields.io/badge/Facebook-{P["bg"]}?style=for-the-badge&logo=facebook&logoColor={P["chrome_dark"]}&labelColor={P["bg"]}" alt="Facebook" /></a>')
    B.append(f'<a href="mailto:{em}"><img src="https://img.shields.io/badge/Email-{P["bg"]}?style=for-the-badge&logo=gmail&logoColor={P["accent"]}&labelColor={P["bg"]}" alt="Email" /></a>')
    badges = "\n&nbsp;&nbsp;\n".join(B)
    return f"""<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/{u}/{u}/main/dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/{u}/{u}/main/light.svg">
  <img alt="{CFG['name']}" src="https://raw.githubusercontent.com/{u}/{u}/main/light.svg">
</picture>

<div align="center">
<img width="100%" src="https://streak-stats.demolab.com/?user={u}&hide_border=true&background={P['bg']}&stroke={P['chrome_dark']}&ring={P['portrait_dark']}&fire={P['accent']}&currStreakLabel={P['chrome_dark']}&sideLabels={P['text_dim']}&currStreakNum={P['text']}&sideNums={P['text']}&dates=64748B&titleColor={P['chrome_dark']}&card_width=1180" alt="streak" />
<br/>
<img width="49%" src="{inst}/api?username={u}&show_icons=true&count_private=true&include_all_commits=true&hide_rank=true&hide_border=true&title_color={P['chrome_dark']}&icon_color={P['portrait_dark']}&text_color={P['text_dim']}&bg_color={P['bg']}&card_width=500" alt="stats" />
<img width="49%" src="{inst}/api/top-langs/?username={u}&layout=compact&langs_count=8&hide_border=true&title_color={P['chrome_dark']}&text_color={P['text_dim']}&bg_color={P['bg']}&card_width=500" alt="top langs" />
</div>

<!-- SNAKE: uncomment this block ONLY after the "Generate Snake Animation" action has run green once (the `output` branch must exist).
<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/{u}/{u}/output/github-snake-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/{u}/{u}/output/github-snake.svg" />
  <img alt="Snake eating my contributions" src="https://raw.githubusercontent.com/{u}/{u}/output/github-snake.svg" />
</picture>
</div>
-->

<div align="center">
{badges}
</div>
"""

if __name__ == "__main__":
    dark, light, mask = build_dots()
    for mode, dots, fn in [(True, dark, "dark.svg"), (False, light, "light.svg")]:
        svg = build_svg(mode, dots, CFG["logos"])
        open(os.path.join(OUT, fn), "w").write(svg)
        print(f"wrote {fn}  {os.path.getsize(os.path.join(OUT, fn)) / 1024:.0f} KB")
    open(os.path.join(OUT, "README.md"), "w").write(build_readme())
    print("wrote README.md")
