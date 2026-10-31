#!/usr/bin/env python3
"""
Space Invaders banner generator -> invaders-dark.svg / invaders-light.svg (repo root).

A scripted, looping game rendered with SVG SMIL animations (works inside <img>/<picture> on GitHub).
Targets are programming languages + security tools (icons vendored from simple-icons in assets/icons/).

Layout: terminal window with two panels
  left  ARCADE.SIM : formation of neon icon cards, ship, bullets, explosions, UFO, starfield
  right KILL.LOG   : score, progress, per-category bars, live kill feed

Run:  cd generator && python3 gen_invaders.py
"""
import json, math, os, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
PAL = json.load(open(os.path.join(HERE, "profile.json")))["palette"]
random.seed(42)

# ------------------------------------------------------------------ geometry & timing
W, H = 1180, 580
TITLE_H, PAD, GAP = 36, 22, 16
SIDE_W = 300
GX, GY = PAD, TITLE_H + PAD                       # game panel
GW, GH = W - 2 * PAD - GAP - SIDE_W, H - TITLE_H - 2 * PAD
SX, SY, SWD, SH = GX + GW + GAP, GY, SIDE_W, GH   # side panel
HDR = 32                                          # panel header strip
LOOP = 18.0
STEP = 0.45
ROWS, COLS = 5, 9
TILE, ICON = 40, 36
CELL_W, CELL_H = 70, 54
DX, DY = 12, 12
form_w = (COLS - 1) * CELL_W + TILE
FORM_Y0 = GY + HDR + 64
PLAYER_Y = GY + GH - 84
GROUND_Y = GY + GH - 40
BULLET_V = 820.0
PLAYER_V = 540.0
PX = 4

ICON_ROWS = [
    ["burpsuite", "metasploit", "kalilinux", "owasp", "wireshark", "hackthebox", "tryhackme", "parrotsecurity", "virustotal"],
    ["torproject", "snyk", "openvpn", "wireguard", "letsencrypt", "hashicorp", "sonarqube", "nginx", "linux"],
    ["python", "javascript", "typescript", "cplusplus", "gnubash", "php", "go", "rust", "c"],
    ["postgresql", "mysql", "openjdk", "ruby", "lua", "html5", "css3", "django", "laravel"],
    ["docker", "kubernetes", "git", "githubactions", "jenkins", "postman", "selenium", "n8n", "vuedotjs"],
]
ROW_CAT = [0, 0, 1, 1, 2]                         # 0 security, 1 languages, 2 devops/testing
CATS = ["SECURITY", "LANGUAGES", "DEVOPS & QA"]
CAT_PTS = [30, 20, 10]
NAME_FIX = {"openjdk": "Java", "gnubash": "Bash", "cplusplus": "C++", "githubactions": "GH Actions", "css3": "CSS",
            "html5": "HTML", "parrotsecurity": "Parrot OS", "hashicorp": "HashiCorp", "letsencrypt": "Let's Encrypt",
            "torproject": "Tor", "kalilinux": "Kali Linux", "burpsuite": "Burp Suite", "hackthebox": "Hack The Box",
            "vuedotjs": "Vue.js", "sonarqube": "SonarQube", "virustotal": "VirusTotal", "tryhackme": "TryHackMe"}


def load_icon(slug):
    raw = open(os.path.join(HERE, "assets", "icons", slug + ".svg")).read()
    d = re.search(r'<path d="([^"]+)"', raw).group(1)
    title = re.search(r"<title>(.*?)</title>", raw).group(1).replace("&amp;", "&")
    return d, NAME_FIX.get(slug, title)


ICONS = {slug: load_icon(slug) for row in ICON_ROWS for slug in row}

SHIP = ["......#......", ".....###.....", ".....#.#.....", "....#####....", ".#..#####..#.",
        ".##.#####.##.", "#############", "###.##.##.###"]
UFO = [".....######.....", "...##########...", "..############..", ".##.##.##.##.##.",
       "################", "..###..##..###..", "...#........#..."]


def sprite_path(rows, s=PX):
    d = []
    for y, r in enumerate(rows):
        x = 0
        while x < len(r):
            if r[x] == "#":
                x2 = x
                while x2 < len(r) and r[x2] == "#":
                    x2 += 1
                d.append(f"M{x * s} {y * s}h{(x2 - x) * s}v{s}h-{(x2 - x) * s}z")
                x = x2
            else:
                x += 1
    return "".join(d)


def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace("'", "&#39;")
def kt(t): return f"{min(max(t / LOOP, 0), 1):.4f}"
def AN(): return f'dur="{LOOP}s" repeatCount="indefinite"'


def anim(attr, vals, times, discrete=True):
    """vals[i] holds from times[i]; times[0] must be 0."""
    return (f'<animate attributeName="{attr}" values="{";".join(map(str, vals))}" '
            f'keyTimes="{";".join(kt(t) for t in times)}" {AN()}{" calcMode=\"discrete\"" if discrete else ""}/>')


def window(t0, t1):
    """opacity: visible only in [t0, t1)."""
    vals, times = ([1], [0]) if t0 <= 0 else ([0, 1], [0, t0])
    if t1 < LOOP:
        vals.append(0); times.append(t1)
    return anim("opacity", vals, times)


def pulse(attr, t0, t1, a, b):
    """attr jumps to a at t0, eases linearly to b at t1, then rests at b (hidden by caller)."""
    return (f'<animate attributeName="{attr}" values="{a};{a};{b};{b}" keyTimes="0;{kt(t0)};{kt(t1)};1" {AN()}/>')


def move(t0, t1, x0, y0, x1, y1):
    return (f'<animateTransform attributeName="transform" type="translate" '
            f'values="{x0:.1f} {y0:.1f};{x0:.1f} {y0:.1f};{x1:.1f} {y1:.1f};{x1:.1f} {y1:.1f}" '
            f'keyTimes="0;{kt(t0)};{kt(t1)};1" {AN()}/>')


# ------------------------------------------------------------------ formation path (one offset per step)
NSTEP = int(round(LOOP / STEP))
MARGIN = 28
FORM_X0 = GX + MARGIN
max_dx = GW - 2 * MARGIN - form_w
offs, ox, oy, dirn = [], max_dx // 2 // DX * DX, 0, 1      # start centred
for k in range(NSTEP):
    offs.append((ox, oy))
    if 0 <= ox + dirn * DX <= max_dx:
        ox += dirn * DX
    else:
        oy += DY; dirn = -dirn


def form_off(t): return offs[min(int(t / STEP), NSTEP - 1)]
def alien_local(r, c): return c * CELL_W, r * CELL_H


def alien_world(r, c, t):
    """bottom-centre of the tile at time t"""
    x, y = alien_local(r, c); o = form_off(t)
    return FORM_X0 + o[0] + x + TILE / 2, FORM_Y0 + o[1] + y + TILE


# ------------------------------------------------------------------ kill schedule
alive_low = {c: ROWS - 1 for c in range(COLS)}
SHIP_W = len(SHIP[0]) * PX
CENTER_X = GX + GW / 2
player_x, t = CENTER_X, 1.35
kills, moves = [], [(0.0, CENTER_X)]
while any(v >= 0 for v in alive_low.values()):
    cands = [c for c, r in alive_low.items() if r >= 0]
    cands.sort(key=lambda c: abs(alien_world(alive_low[c], c, t)[0] - player_x) + random.uniform(0, 110))
    c = cands[0]; r = alive_low[c]
    tx = alien_world(r, c, t + 0.4)[0]
    tf = t + 0.1 + abs(tx - player_x) / PLAYER_V
    for _ in range(6):                      # land the hit well inside a single formation step
        ax, ay = alien_world(r, c, tf + 0.3)
        th = tf + (PLAYER_Y - ay) / BULLET_V
        if 0.12 < (th % STEP) / STEP < 0.88:
            ax2, ay = alien_world(r, c, th)
            if abs(ax2 - tx) < 1:
                break
            tx = ax2; tf = t + 0.1 + abs(tx - player_x) / PLAYER_V
        else:
            tf += STEP * 0.3
    ax, ay = alien_world(r, c, th)
    moves += [(tf - 0.06, ax), (tf + 0.04, ax)]
    kills.append(dict(r=r, c=c, tf=tf, th=th, x=ax, y=ay, slug=ICON_ROWS[r][c], cat=ROW_CAT[r]))
    player_x = ax; alive_low[c] -= 1; t = tf + 0.08
kills.sort(key=lambda k: k["th"])
T_CLEAR = kills[-1]["th"] + 0.7
assert T_CLEAR < LOOP - 2.0, f"wave too slow: {T_CLEAR:.2f}s"
moves += [(LOOP - 0.7, player_x), (LOOP, CENTER_X)]
moves.sort()
kill_t = {(k["r"], k["c"]): k["th"] for k in kills}
TOTAL = len(kills)
FINAL = sum(CAT_PTS[k["cat"]] for k in kills)


def player_at(tt):
    for (a, xa), (b, xb) in zip(moves, moves[1:]):
        if a <= tt <= b:
            return xa + (xb - xa) * (tt - a) / max(b - a, 1e-6)
    return moves[-1][1]


def appear_t(r, c): return 0.15 + (r * COLS + c) * 0.014


# ------------------------------------------------------------------ render
def build(dark):
    bg = PAL["bg"] if dark else PAL["bg_light"]
    panel = "#0B1222" if dark else "#FFFFFF"
    panel2 = "#0D1528" if dark else "#F1F5F9"
    border = "#1E293B" if dark else "#CBD5E1"
    text = PAL["text"] if dark else PAL["text_light"]
    dim = PAL["text_dim"] if dark else PAL["text_dim_light"]
    faint = "#334155" if dark else "#CBD5E1"
    live = PAL["live"]
    cyan = PAL["chrome_dark"] if dark else PAL["chrome_light"]
    purple = PAL["portrait_dark"] if dark else PAL["portrait_light"]
    green = PAL["accent"] if dark else "#059669"
    cat_col = [cyan, purple, green]
    glow = 'filter="url(#glow)"' if dark else ''
    o = []
    A = o.append

    A(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,\'Liberation Mono\',monospace">')
    A(f'<title>Space Invaders: shooting down languages and security tools</title>')
    # ---------------- defs
    A("<defs>")
    for slug, (d, _) in ICONS.items():
        A(f'<symbol id="i_{slug}" viewBox="0 0 24 24"><path d="{d}"/></symbol>')
    A(f'<path id="ship" d="{sprite_path(SHIP)}"/>')
    A(f'<path id="ship_s" d="{sprite_path(SHIP, 2)}"/>')
    A(f'<path id="ufo" d="{sprite_path(UFO, 3)}"/>')
    A('<filter id="glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="3.2" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    A(f'<linearGradient id="shipg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{"#6EE7B7" if dark else "#10B981"}"/>'
      f'<stop offset="1" stop-color="{green}"/></linearGradient>')
    A(f'<linearGradient id="flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FDE68A"/>'
      f'<stop offset="0.5" stop-color="#F97316"/><stop offset="1" stop-color="#F97316" stop-opacity="0"/></linearGradient>')
    A(f'<radialGradient id="vig" cx="50%" cy="45%" r="75%"><stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
      f'<stop offset="1" stop-color="#000" stop-opacity="{0.55 if dark else 0.06}"/></radialGradient>')
    A(f'<radialGradient id="neb1" cx="22%" cy="30%" r="45%"><stop offset="0" stop-color="{purple}" stop-opacity="{0.16 if dark else 0.07}"/>'
      f'<stop offset="1" stop-color="{purple}" stop-opacity="0"/></radialGradient>')
    A(f'<radialGradient id="neb2" cx="80%" cy="70%" r="45%"><stop offset="0" stop-color="{cyan}" stop-opacity="{0.12 if dark else 0.06}"/>'
      f'<stop offset="1" stop-color="{cyan}" stop-opacity="0"/></radialGradient>')
    A(f'<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" fill-opacity="{0.22 if dark else 0.03}"/></pattern>')
    A(f'<clipPath id="gc"><rect x="{GX + 1}" y="{GY + HDR + 1}" width="{GW - 2}" height="{GH - HDR - 2}" rx="7"/></clipPath>')
    A("</defs>")

    # ---------------- window chrome
    A(f'<rect width="{W}" height="{H}" rx="12" fill="{bg}"/>')
    A(f'<rect width="{W}" height="{TITLE_H}" rx="12" fill="{panel2}"/><rect y="{TITLE_H - 12}" width="{W}" height="12" fill="{panel2}"/>')
    A(f'<line x1="0" y1="{TITLE_H}" x2="{W}" y2="{TITLE_H}" stroke="{border}"/>')
    for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        A(f'<circle cx="{20 + 20 * i}" cy="18" r="6" fill="{c}"/>')
    A(f'<text x="{W / 2}" y="23" text-anchor="middle" font-size="13" fill="{dim}">~/kiramido1 — invaders.sh --target=stack --live</text>')

    def panel_frame(x, y, w, h, label, right=None):
        A(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{panel}" stroke="{border}"/>')
        A(f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{HDR}" rx="8" fill="{panel2}"/>'
          f'<rect x="{x + 0.5}" y="{y + HDR - 8}" width="{w - 1}" height="8" fill="{panel2}"/>')
        A(f'<line x1="{x}" y1="{y + HDR}" x2="{x + w}" y2="{y + HDR}" stroke="{border}"/>')
        A(f'<text x="{x + 14}" y="{y + 21}" font-size="13" font-weight="700" fill="{cyan}" letter-spacing="1.5">{label}</text>')
        if right:
            A(right)

    lx = GX + GW - 74
    live_pill = (f'<rect x="{lx}" y="{GY + 7}" width="60" height="18" rx="9" fill="{live}" fill-opacity="0.15" stroke="{live}"/>'
                 f'<circle cx="{lx + 13}" cy="{GY + 16}" r="3" fill="{live}"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>'
                 f'<text x="{lx + 22}" y="{GY + 20}" font-size="11" font-weight="700" fill="{live}" letter-spacing="1">LIVE</text>'
                 f'<text x="{lx - 14}" y="{GY + 21}" text-anchor="end" font-size="12" fill="{dim}" letter-spacing="1.5">WAVE 01 · CREDIT 01</text>')
    panel_frame(GX, GY, GW, GH, "ARCADE.SIM", live_pill)

    # ---------------- game area
    A('<g clip-path="url(#gc)">')
    A(f'<rect x="{GX}" y="{GY}" width="{GW}" height="{GH}" fill="url(#neb1)"/><rect x="{GX}" y="{GY}" width="{GW}" height="{GH}" fill="url(#neb2)"/>')
    # parallax starfield: each layer is a tile drawn twice and scrolled down by its own height
    top, hgt = GY + HDR, GH - HDR
    for n, size, op, dur in [(60, 1.5, 0.35, 40), (32, 2, 0.55, 24), (14, 2.5, 0.85, 14)]:
        stars = [(random.uniform(GX + 6, GX + GW - 6), random.uniform(0, hgt)) for _ in range(n)]
        dots = "".join(f'<rect x="{x:.0f}" y="{y + dy:.0f}" width="{size}" height="{size}"/>' for x, y in stars for dy in (top - hgt, top))
        A(f'<g fill="{text if dark else dim}" opacity="{op if dark else op * 0.5}">{dots}'
          f'<animateTransform attributeName="transform" type="translate" values="0 0;0 {hgt}" dur="{dur}s" repeatCount="indefinite"/></g>')

    # UFO (mystery ship) — crosses with blinking lights
    uy = GY + HDR + 16
    A(f'<g opacity="0" {glow}>{window(6.0, 10.6)}{move(6.0, 10.6, GX + GW + 10, uy, GX - 60, uy)}'
      f'<use href="#ufo" xlink:href="#ufo" fill="{live}"/>'
      f'<rect x="12" y="9" width="3" height="3" fill="#FDE68A"><animate attributeName="opacity" values="1;0" dur="0.3s" repeatCount="indefinite" calcMode="discrete"/></rect>'
      f'<rect x="33" y="9" width="3" height="3" fill="#FDE68A"><animate attributeName="opacity" values="0;1" dur="0.3s" repeatCount="indefinite" calcMode="discrete"/></rect>'
      f'</g>')

    # formation
    tv = [form_off(i * STEP) for i in range(NSTEP)]
    A(f'<g transform="translate({FORM_X0} {FORM_Y0})"><g>')
    A(f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" {AN()} '
      f'values="{";".join(f"{a} {b}" for a, b in tv)}" keyTimes="{";".join(kt(i * STEP) for i in range(NSTEP))}"/>')
    A(f'<g {glow}><animateTransform attributeName="transform" type="translate" values="0 0;0 -3" dur="{2 * STEP}s" '
      f'repeatCount="indefinite" calcMode="discrete"/>')
    for r in range(ROWS):
        col = cat_col[ROW_CAT[r]]
        for c in range(COLS):
            x, y = alien_local(r, c); th = kill_t[(r, c)]; slug = ICON_ROWS[r][c]
            io = (TILE - ICON) / 2
            A(f'<g opacity="0">{anim("opacity", [0, 1, 0], [0, appear_t(r, c), th])}<title>{esc(ICONS[slug][1])}</title>'
              f'<use href="#i_{slug}" xlink:href="#i_{slug}" x="{x + io}" y="{y + io}" width="{ICON}" height="{ICON}" fill="{col}"/></g>')
    A("</g>")
    # hit effects (ride with the formation, no bob)
    for r in range(ROWS):
        col = cat_col[ROW_CAT[r]]
        for c in range(COLS):
            x, y = alien_local(r, c); th = kill_t[(r, c)]
            cx, cy = x + TILE / 2, y + TILE / 2
            A(f'<circle cx="{cx}" cy="{cy}" r="16" fill="{"#FFFFFF" if dark else col}" opacity="0">{window(th, th + 0.07)}</circle>')
            A(f'<circle cx="{cx}" cy="{cy}" r="6" fill="none" stroke="{col}" stroke-width="3" opacity="0">'
              f'{window(th, th + 0.4)}{pulse("r", th, th + 0.4, 6, 34)}{pulse("stroke-width", th, th + 0.4, 4, 0.5)}</circle>')
            parts = []
            for i in range(7):
                ang = 2 * math.pi * i / 7 + random.uniform(-0.3, 0.3); dist = random.uniform(26, 44)
                s = random.choice([3, 4, 5])
                parts.append(f'<rect width="{s}" height="{s}" x="{-s / 2}" y="{-s / 2}" fill="{col if i % 2 else text}">'
                             f'{move(th, th + 0.5, cx, cy, cx + dist * math.cos(ang), cy + dist * math.sin(ang))}</rect>')
            A(f'<g opacity="0" {glow}>{window(th, th + 0.5)}{"".join(parts)}</g>')
    A("</g></g>")

    # bullets (core + halo)
    for k in kills:
        y0, y1 = PLAYER_Y - 16, k["y"] - 6
        A(f'<g opacity="0">{window(k["tf"], k["th"])}{move(k["tf"], k["th"], k["x"], y0, k["x"], y1)}'
          f'<rect x="-4" y="-3" width="8" height="22" rx="4" fill="{cyan}" opacity="0.35"/>'
          f'<rect x="-1.5" y="0" width="3" height="16" rx="1.5" fill="{"#E0FDFF" if dark else cyan}"/></g>')
        # muzzle flash
        A(f'<circle cx="{k["x"]}" cy="{PLAYER_Y - 4}" r="7" fill="{cyan}" opacity="0" {glow}>{window(k["tf"], k["tf"] + 0.07)}</circle>')

    # alien bombs that miss
    bombs, tb = 0, 2.0
    while tb < T_CLEAR - 1.6 and bombs < 12:
        live_cols = [c for c in range(COLS) if any(kill_t[(r, c)] > tb + 0.1 for r in range(ROWS))]
        c = random.choice(live_cols)
        r = max(r for r in range(ROWS) if kill_t[(r, c)] > tb + 0.1)
        bx, by = alien_world(r, c, tb)
        fall = (GROUND_Y - by) / 260.0
        if abs(player_at(tb + fall * (PLAYER_Y - by) / (GROUND_Y - by)) - bx) > 50:
            A(f'<g opacity="0" {glow}>{window(tb, tb + fall)}{move(tb, tb + fall, bx, by, bx, GROUND_Y - 14)}'
              f'<path d="M0 0l4 4l-4 4l4 4" stroke="{live}" stroke-width="2.2" fill="none" stroke-linecap="round"/></g>')
            # impact puff on the ground
            A(f'<circle cx="{bx + 2:.0f}" cy="{GROUND_Y}" r="3" fill="none" stroke="{live}" stroke-width="2" opacity="0">'
              f'{window(tb + fall, tb + fall + 0.3)}{pulse("r", tb + fall, tb + fall + 0.3, 3, 14)}</circle>')
            bombs += 1
        tb += random.uniform(0.8, 1.5)

    # ship (+ engine flame)
    mt = [m[0] for m in moves]; mx = [m[1] for m in moves]
    A(f'<g {glow}><animateTransform attributeName="transform" type="translate" '
      f'values="{";".join(f"{v:.1f} {PLAYER_Y}" for v in mx)}" keyTimes="{";".join(kt(v) for v in mt)}" {AN()}/>'
      f'<rect x="-4" y="{len(SHIP) * PX}" width="8" height="10" fill="url(#flame)">'
      f'<animate attributeName="height" values="10;5;12;7;10" dur="0.25s" repeatCount="indefinite"/></rect>'
      f'<use href="#ship" xlink:href="#ship" x="{-SHIP_W / 2}" fill="url(#shipg)"/></g>')
    # overlays: scanlines + vignette
    A(f'<rect x="{GX}" y="{GY + HDR}" width="{GW}" height="{GH - HDR}" fill="url(#scan)"/>')
    A(f'<rect x="{GX}" y="{GY + HDR}" width="{GW}" height="{GH - HDR}" fill="url(#vig)"/>')

    # ground
    A(f'<rect x="{GX + 16}" y="{GROUND_Y - 1}" width="{GW - 32}" height="2" fill="{green}" opacity="0.8" {glow}/>')
    # bottom HUD
    hb = GY + GH - 14
    A(f'<text x="{GX + 18}" y="{hb}" font-size="13" fill="{dim}" letter-spacing="2">LIVES</text>')
    for i in range(3):
        A(f'<use href="#ship_s" xlink:href="#ship_s" x="{GX + 76 + i * 34}" y="{hb - 13}" fill="{green}"/>')
    A(f'<text x="{GX + GW - 18}" y="{hb}" text-anchor="end" font-size="13" fill="{dim}" letter-spacing="2">'
      f'ACCURACY <tspan fill="{text}">100%</tspan></text>')

    # READY / WAVE CLEARED cards
    cx, cy = GX + GW / 2, GY + HDR + (GH - HDR) / 2 - 10
    def card(w, h, inner, t0, t1, accent):
        A(f'<g opacity="0">{window(t0, t1)}'
          f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="12" fill="{panel}" fill-opacity="0.92" stroke="{accent}" stroke-width="1.5"/>'
          f'{inner}</g>')
    card(360, 92,
         f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" font-size="26" font-weight="700" fill="{text}" letter-spacing="6" {glow}>WAVE 01</text>'
         f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="14" fill="{cyan}" letter-spacing="4">READY<tspan>'
         f'<animate attributeName="opacity" values="1;0" dur="0.5s" repeatCount="indefinite" calcMode="discrete"/>_</tspan></text>',
         0, 1.25, cyan)
    card(460, 150,
         f'<text x="{cx}" y="{cy - 28}" text-anchor="middle" font-size="30" font-weight="700" fill="{cyan}" letter-spacing="7" {glow}>WAVE CLEARED</text>'
         f'<text x="{cx}" y="{cy + 6}" text-anchor="middle" font-size="15" fill="{text}" letter-spacing="2">{TOTAL}/{TOTAL} TARGETS PWNED · {FINAL} PTS</text>'
         f'<text x="{cx}" y="{cy + 42}" text-anchor="middle" font-size="13" fill="{dim}" letter-spacing="2">$ ./next_wave --harder<tspan fill="{cyan}">'
         f'<animate attributeName="opacity" values="1;0" dur="0.6s" repeatCount="indefinite" calcMode="discrete"/>█</tspan></text>',
         T_CLEAR, LOOP - 0.15, cyan)
    A("</g>")   # end game clip

    # ---------------- side panel
    panel_frame(SX, SY, SWD, SH, "KILL.LOG",
                f'<text x="{SX + SWD - 14}" y="{SY + 21}" text-anchor="end" font-size="12" fill="{dim}">tail -f</text>')
    L, R = SX + 18, SX + SWD - 18
    y = SY + HDR + 30
    A(f'<text x="{L}" y="{y}" font-size="12" fill="{dim}" letter-spacing="2">SCORE</text>')
    A(f'<text x="{R}" y="{y}" text-anchor="end" font-size="12" fill="{dim}" letter-spacing="2">HI <tspan fill="{text}">{FINAL:05d}</tspan></text>')
    score, times, vals = 0, [0.0], [0]
    for k in kills:
        score += CAT_PTS[k["cat"]]; times.append(k["th"]); vals.append(score)
    for i, v in enumerate(vals):
        t1 = times[i + 1] if i + 1 < len(times) else LOOP
        A(f'<text x="{L}" y="{y + 40}" font-size="38" font-weight="700" fill="{text}" letter-spacing="3" opacity="0" {glow}>{v:05d}{window(times[i], t1)}</text>')
    # progress
    y += 76
    A(f'<text x="{L}" y="{y}" font-size="12" fill="{dim}" letter-spacing="2">TARGETS PWNED</text>')
    for i in range(TOTAL + 1):
        t0 = 0 if i == 0 else kills[i - 1]["th"]; t1 = kills[i]["th"] if i < TOTAL else LOOP
        A(f'<text x="{R}" y="{y}" text-anchor="end" font-size="12" fill="{text}" opacity="0">{i}/{TOTAL}{window(t0, t1)}</text>')
    bw = R - L
    A(f'<rect x="{L}" y="{y + 10}" width="{bw}" height="8" rx="4" fill="{faint}" fill-opacity="0.5"/>')
    A(f'<rect x="{L}" y="{y + 10}" width="0" height="8" rx="4" fill="{cyan}" {glow}>'
      f'{anim("width", [0] + [f"{bw * (i + 1) / TOTAL:.1f}" for i in range(TOTAL)], [0] + [k["th"] for k in kills])}</rect>')
    # per category
    y += 46
    for ci, name in enumerate(CATS):
        ks = [k for k in kills if k["cat"] == ci]; n = len(ks); col = cat_col[ci]
        A(f'<rect x="{L}" y="{y - 9}" width="8" height="8" rx="2" fill="{col}"/>')
        A(f'<text x="{L + 16}" y="{y}" font-size="12" fill="{text}" letter-spacing="1">{esc(name)}</text>')
        for i in range(n + 1):
            t0 = 0 if i == 0 else ks[i - 1]["th"]; t1 = ks[i]["th"] if i < n else LOOP
            A(f'<text x="{R}" y="{y}" text-anchor="end" font-size="12" fill="{dim}" opacity="0">{i}/{n}{window(t0, t1)}</text>')
        A(f'<rect x="{L}" y="{y + 7}" width="{bw}" height="4" rx="2" fill="{faint}" fill-opacity="0.5"/>')
        A(f'<rect x="{L}" y="{y + 7}" width="0" height="4" rx="2" fill="{col}">'
          f'{anim("width", [0] + [f"{bw * (i + 1) / n:.1f}" for i in range(n)], [0] + [k["th"] for k in ks])}</rect>')
        y += 34
    # kill feed
    y += 4
    A(f'<line x1="{L}" y1="{y}" x2="{R}" y2="{y}" stroke="{border}"/>')
    y += 24
    A(f'<text x="{L}" y="{y}" font-size="12" fill="{dim}">$ tail -f /var/log/pwned.log</text>')
    feed_y0, LH, NL = y + 28, 25, 6
    A(f'<text x="{L}" y="{feed_y0}" font-size="13" fill="{dim}" opacity="0">waiting for targets…{window(0, kills[0]["th"])}</text>')
    for i, k in enumerate(kills):
        col = cat_col[k["cat"]]
        ts, ys, ops = [0.0], [feed_y0], [0]
        for j in range(i, min(i + NL, TOTAL)):
            ts.append(kills[j]["th"]); ys.append(feed_y0 + (j - i) * LH); ops.append(round(1 - (j - i) * 0.12, 2))
        if i + NL < TOTAL:
            ts.append(kills[i + NL]["th"]); ys.append(feed_y0 + NL * LH); ops.append(0)
        trans = ";".join(f"0 {v - feed_y0}" for v in ys)
        A(f'<g opacity="0">{anim("opacity", ops, ts)}'
          f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" values="{trans}" '
          f'keyTimes="{";".join(kt(v) for v in ts)}" {AN()}/>'
          f'<text x="{L}" y="{feed_y0}" font-size="13" fill="{text}"><tspan fill="{col}">✖</tspan> {esc(ICONS[k["slug"]][1])}</text>'
          f'<text x="{R}" y="{feed_y0}" text-anchor="end" font-size="13" font-weight="700" fill="{col}">+{CAT_PTS[k["cat"]]}</text></g>')
    A("</svg>")
    return "\n".join(o)


for dark, name in [(True, "invaders-dark.svg"), (False, "invaders-light.svg")]:
    random.seed(7)
    svg = build(dark)
    open(os.path.join(OUT, name), "w").write(svg)
    print(f"{name}: {len(svg) / 1024:.0f} KB, kills={TOTAL}, wave cleared at {T_CLEAR:.2f}s / {LOOP}s")
