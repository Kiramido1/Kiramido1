#!/usr/bin/env python3
"""
Space Invaders banner generator -> invaders-dark.svg / invaders-light.svg (repo root).

A scripted, looping game rendered with SVG SMIL animations (works inside <img>/<picture> on GitHub):
  - 5x11 alien formation marching left/right and stepping down (discrete steps, 2-frame sprites)
  - the player ship glides between targets and shoots; every bullet hits the lowest live alien in a column
  - explosions, score counter, alien bombs that miss, a mystery UFO, "WAVE CLEARED", then the loop restarts

Run:  cd generator && python3 gen_invaders.py
"""
import json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
PAL = json.load(open(os.path.join(HERE, "profile.json")))["palette"]
random.seed(42)

W, H = 1180, 520
TITLE_H = 36
PAD = 22
FX, FY, FW, FH = PAD, TITLE_H + PAD, W - 2 * PAD, H - TITLE_H - 2 * PAD   # game frame
PX = 4                      # sprite pixel size
LOOP = 18.0                 # seconds
STEP = 0.45                 # formation step period
ROWS, COLS = 5, 11
CELL_W, CELL_H = 62, 44
FORM_X0, FORM_Y0 = FX + 60, FY + 112
DX, DY = 14, 10
PLAYER_Y = FY + FH - 62     # top of the player sprite
GROUND_Y = FY + FH - 22
BULLET_V = 820.0            # px/s
PLAYER_V = 950.0            # px/s

S = {
    "squid": (["...##...", "..####..", ".######.", "##.##.##", "########", "..#..#..", ".#.##.#.", "#.#..#.#"],
              ["...##...", "..####..", ".######.", "##.##.##", "########", ".#.##.#.", "#......#", ".#....#."]),
    "crab": (["..#.....#..", "...#...#...", "..#######..", ".##.###.##.", "###########", "#.#######.#", "#.#.....#.#", "...##.##..."],
             ["..#.....#..", "#..#...#..#", "#.#######.#", "###.###.###", "###########", ".#########.", "..#.....#..", ".#.......#."]),
    "octo": (["....####....", ".##########.", "############", "###..##..###", "############", "...##..##...", "..##.##.##..", "##........##"],
             ["....####....", ".##########.", "############", "###..##..###", "############", "..###..###..", ".##..##..##.", "..##....##.."]),
}
PLAYER = ["......#......", ".....###.....", ".....###.....", ".###########.", "#############",
          "#############", "#############", "#############"]
BOOM = ["....#...#....", ".#..#...#..#.", "..#.......#..", "...#.....#...", "##.........##",
        "...#.....#...", "..#.......#..", ".#..#...#..#.", "....#...#...."]
UFO = [".....######.....", "...##########...", "..############..", ".##.##.##.##.##.",
       "################", "..###..##..###..", "...#........#..."]
ROW_KIND = ["squid", "crab", "crab", "octo", "octo"]
ROW_PTS = [30, 20, 20, 10, 10]


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


def sw(rows): return len(rows[0]) * PX


def kt(t): return f"{min(max(t / LOOP, 0), 1):.4f}"


def anim(attr, vals, times, discrete=True):
    """vals[i] holds from times[i]; times[0] must be 0."""
    return (f'<animate attributeName="{attr}" values="{";".join(map(str, vals))}" '
            f'keyTimes="{";".join(kt(t) for t in times)}" dur="{LOOP}s" repeatCount="indefinite"'
            f'{" calcMode=\"discrete\"" if discrete else ""}/>')


def window(t0, t1):
    """opacity animation: visible only in [t0, t1)."""
    vals, times = [0], [0]
    if t0 > 0:
        vals.append(1); times.append(t0)
    else:
        vals[0] = 1
    if t1 < LOOP:
        vals.append(0); times.append(t1)
    return anim("opacity", vals, times)


# ------------------------------------------------------------- formation path (one offset per step)
NSTEP = int(round(LOOP / STEP))
alien_span = (COLS - 1) * CELL_W + sw(S["octo"][0])
max_dx = (FX + FW - 40) - (FORM_X0 + alien_span)
offs, ox, oy, dirn = [], 0, 0, 1
for k in range(NSTEP):
    offs.append((ox, oy))
    if 0 <= ox + dirn * DX <= max_dx:
        ox += dirn * DX
    else:
        oy += DY; dirn = -dirn


def form_off(t): return offs[min(int(t / STEP), NSTEP - 1)]


def alien_local(r, c):
    kind = ROW_KIND[r]
    x = c * CELL_W + (sw(S["octo"][0]) - sw(S[kind][0])) / 2
    return x, r * CELL_H


def alien_world_center(r, c, t):
    x, y = alien_local(r, c); o = form_off(t)
    return FORM_X0 + o[0] + x + sw(S[ROW_KIND[r]][0]) / 2, FORM_Y0 + o[1] + y + 8 * PX


# ------------------------------------------------------------- kill schedule
alive_low = {c: ROWS - 1 for c in range(COLS)}   # lowest live row per column
pw = sw(PLAYER)
player_x = FX + FW / 2                           # centre x
t = 1.2
kills, moves = [], [(0.0, player_x)]
while any(v >= 0 for v in alive_low.values()):
    cands = [c for c, r in alive_low.items() if r >= 0]
    # prefer nearby columns, a little randomness so it looks human
    cands.sort(key=lambda c: abs(alien_world_center(alive_low[c], c, t)[0] - player_x) + random.uniform(0, 120))
    c = cands[0]; r = alive_low[c]
    tx = alien_world_center(r, c, t + 0.4)[0]
    tf = t + 0.1 + abs(tx - player_x) / PLAYER_V
    for _ in range(4):                           # settle on a hit time well inside one formation step
        ax, ay = alien_world_center(r, c, tf + 0.3)
        th = tf + (PLAYER_Y - ay) / BULLET_V
        ph = (th % STEP) / STEP
        if 0.12 < ph < 0.88:
            ax, ay = alien_world_center(r, c, th)
            tx2 = ax
            if abs(tx2 - tx) < 1:
                break
            tx = tx2; tf = t + 0.1 + abs(tx - player_x) / PLAYER_V
        else:
            tf += STEP * 0.3
    ax, ay = alien_world_center(r, c, th)
    tf = max(tf, t + 0.1 + abs(ax - player_x) / PLAYER_V)
    moves.append((tf - 0.06, ax)); moves.append((tf + 0.04, ax))
    kills.append(dict(r=r, c=c, tf=tf, th=th, x=ax, y=ay))
    player_x = ax; alive_low[c] -= 1; t = tf + 0.08
T_CLEAR = kills[-1]["th"] + 0.5
assert T_CLEAR < LOOP - 1.5, f"wave too slow: {T_CLEAR:.2f}s"
moves.append((LOOP - 0.6, player_x)); moves.append((LOOP, FX + FW / 2))
kill_t = {(k["r"], k["c"]): k["th"] for k in kills}


def player_at(tt):
    for (a, xa), (b, xb) in zip(moves, moves[1:]):
        if a <= tt <= b:
            return xa + (xb - xa) * (tt - a) / max(b - a, 1e-6)
    return moves[-1][1]


# ------------------------------------------------------------- render
def build(dark):
    bg = PAL["bg"] if dark else PAL["bg_light"]
    panel = "#0D1528" if dark else "#FFFFFF"
    border = "#1E293B" if dark else "#CBD5E1"
    chrome = PAL["chrome_dark"] if dark else PAL["chrome_light"]
    purple = PAL["portrait_dark"] if dark else PAL["portrait_light"]
    green = PAL["accent"] if dark else "#059669"
    text = PAL["text"] if dark else PAL["text_light"]
    dim = PAL["text_dim"] if dark else PAL["text_dim_light"]
    live = PAL["live"]
    row_col = [chrome, purple, purple, green, green]

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,\'Liberation Mono\',monospace">']
    # defs: 2-frame sprites
    o.append("<defs>")
    for kind, (f1, f2) in S.items():
        o.append(f'<g id="{kind}"><path d="{sprite_path(f1)}">'
                 f'<animate attributeName="opacity" values="1;0" dur="{2 * STEP}s" repeatCount="indefinite" calcMode="discrete"/></path>'
                 f'<path d="{sprite_path(f2)}" opacity="0">'
                 f'<animate attributeName="opacity" values="0;1" dur="{2 * STEP}s" repeatCount="indefinite" calcMode="discrete"/></path></g>')
    o.append(f'<path id="boom" d="{sprite_path(BOOM, 4)}"/>')
    o.append(f'<path id="ship" d="{sprite_path(PLAYER)}"/>')
    o.append(f'<path id="ship_s" d="{sprite_path(PLAYER, 2)}"/>')
    o.append(f'<path id="ufo" d="{sprite_path(UFO)}"/>')
    o.append(f'<clipPath id="gc"><rect x="{FX + 1}" y="{FY + 31}" width="{FW - 2}" height="{FH - 32}"/></clipPath>')
    o.append("</defs>")

    # terminal chrome
    o.append(f'<rect width="{W}" height="{H}" rx="12" fill="{bg}"/>')
    o.append(f'<rect width="{W}" height="{TITLE_H}" rx="12" fill="{panel}"/><rect y="{TITLE_H - 12}" width="{W}" height="12" fill="{panel}"/>')
    o.append(f'<line x1="0" y1="{TITLE_H}" x2="{W}" y2="{TITLE_H}" stroke="{border}"/>')
    for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        o.append(f'<circle cx="{20 + 20 * i}" cy="18" r="6" fill="{c}"/>')
    o.append(f'<text x="{W / 2}" y="23" text-anchor="middle" font-size="13" fill="{dim}">invaders.sh --live</text>')
    o.append(f'<rect x="{FX}" y="{FY}" width="{FW}" height="{FH}" rx="8" fill="{panel}" stroke="{border}"/>')
    o.append(f'<text x="{FX + 14}" y="{FY + 20}" font-size="13" fill="{chrome}" letter-spacing="1">ARCADE.SIM</text>')
    lx = FX + FW - 74
    o.append(f'<rect x="{lx}" y="{FY + 7}" width="60" height="18" rx="9" fill="{live}" fill-opacity="0.15" stroke="{live}"/>')
    o.append(f'<circle cx="{lx + 13}" cy="{FY + 16}" r="3" fill="{live}"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="{lx + 22}" y="{FY + 20}" font-size="11" fill="{live}" letter-spacing="1">LIVE</text>')
    o.append(f'<line x1="{FX}" y1="{FY + 30}" x2="{FX + FW}" y2="{FY + 30}" stroke="{border}"/>')

    o.append('<g clip-path="url(#gc)">')
    # stars
    for _ in range(70):
        sx, sy = random.uniform(FX + 10, FX + FW - 10), random.uniform(FY + 40, GROUND_Y - 10)
        d = random.uniform(1.6, 4.0)
        o.append(f'<rect x="{sx:.0f}" y="{sy:.0f}" width="2" height="2" fill="{dim}" opacity="0.3">'
                 f'<animate attributeName="opacity" values="0.08;0.45;0.08" dur="{d:.1f}s" begin="-{random.uniform(0, d):.1f}s" repeatCount="indefinite"/></rect>')

    # HUD
    hy = FY + 58
    o.append(f'<text x="{FX + 24}" y="{hy}" font-size="15" fill="{dim}" letter-spacing="2">SCORE</text>')
    score, vals, times = 0, ["0000"], [0]
    for k in sorted(kills, key=lambda k: k["th"]):
        score += ROW_PTS[k["r"]]; vals.append(f"{score:04d}"); times.append(k["th"])
    final = score
    # one <text> per score value, each shown only in its time window
    for i, v in enumerate(vals):
        t0 = times[i]; t1 = times[i + 1] if i + 1 < len(times) else LOOP
        o.append(f'<text x="{FX + 96}" y="{hy}" font-size="15" fill="{text}" letter-spacing="2" opacity="0">{v}'
                 f'{window(t0, t1)}</text>')
    o.append(f'<text x="{W / 2}" y="{hy}" text-anchor="middle" font-size="15" fill="{dim}" letter-spacing="2">HI-SCORE '
             f'<tspan fill="{text}">{final:04d}</tspan></text>')
    o.append(f'<text x="{FX + FW - 168}" y="{hy}" font-size="15" fill="{dim}" letter-spacing="2">LIVES</text>')
    for i in range(3):
        o.append(f'<use href="#ship_s" xlink:href="#ship_s" x="{FX + FW - 100 + i * 32}" y="{hy - 13}" fill="{green}"/>')

    # mystery UFO (crosses right -> left, gets shot? no — it escapes)
    uy = FY + 76
    o.append(f'<use href="#ufo" xlink:href="#ufo" y="{uy}" x="{FX + FW + 10}" fill="{live}" opacity="0">'
             f'{window(6.0, 10.5)}'
             f'<animate attributeName="x" values="{FX + FW + 10};{FX + FW + 10};{FX - 80};{FX - 80}" keyTimes="0;{kt(6.0)};{kt(10.5)};1" dur="{LOOP}s" repeatCount="indefinite"/></use>')

    # formation
    tv = [form_off(i * STEP) for i in range(NSTEP)]
    o.append(f'<g transform="translate({FORM_X0} {FORM_Y0})"><g>')
    o.append(f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" dur="{LOOP}s" repeatCount="indefinite" '
             f'values="{";".join(f"{a} {b}" for a, b in tv)}" keyTimes="{";".join(kt(i * STEP) for i in range(NSTEP))}"/>')
    for r in range(ROWS):
        for c in range(COLS):
            x, y = alien_local(r, c); th = kill_t[(r, c)]
            o.append(f'<use href="#{ROW_KIND[r]}" xlink:href="#{ROW_KIND[r]}" x="{x:.0f}" y="{y}" fill="{row_col[r]}">'
                     f'{anim("opacity", [1, 0], [0, th])}</use>')
            bx = x + sw(S[ROW_KIND[r]][0]) / 2 - sw(BOOM) / 2
            o.append(f'<use href="#boom" xlink:href="#boom" x="{bx:.0f}" y="{y - 2}" fill="{text}" opacity="0">{window(th, th + 0.22)}</use>')
    o.append("</g></g>")

    # bullets
    for k in kills:
        y0, y1 = PLAYER_Y - 14, k["y"] - 8
        o.append(f'<rect x="{k["x"] - 1.5:.1f}" y="{y0}" width="3" height="14" fill="{chrome}" opacity="0">'
                 f'{window(k["tf"], k["th"])}'
                 f'<animate attributeName="y" values="{y0};{y0};{y1:.0f};{y1:.0f}" keyTimes="0;{kt(k["tf"])};{kt(k["th"])};1" dur="{LOOP}s" repeatCount="indefinite"/></rect>')

    # alien bombs that miss: zig-zag bolts dropped from live bottom aliens
    bombs, tb = 0, 1.8
    while tb < T_CLEAR - 1.5 and bombs < 14:
        live_cols = [c for c in range(COLS) if any(kill_t[(r, c)] > tb + 0.1 for r in range(ROWS))]
        c = random.choice(live_cols)
        r = max(r for r in range(ROWS) if kill_t[(r, c)] > tb + 0.1)
        bx, by = alien_world_center(r, c, tb)
        fall = (GROUND_Y - by) / 300.0
        if abs(player_at(tb + fall * (PLAYER_Y - by) / (GROUND_Y - by)) - bx) > 45:
            zz = "M0 0l3 3l-3 3l3 3l-3 3"
            o.append(f'<path d="{zz}" stroke="{live}" stroke-width="2" fill="none" opacity="0" transform="translate({bx:.0f} {by:.0f})">'
                     f'{window(tb, tb + fall)}'
                     f'<animateTransform attributeName="transform" type="translate" values="{bx:.0f} {by:.0f};{bx:.0f} {by:.0f};{bx:.0f} {GROUND_Y - 12};{bx:.0f} {GROUND_Y - 12}" '
                     f'keyTimes="0;{kt(tb)};{kt(tb + fall)};1" dur="{LOOP}s" repeatCount="indefinite"/></path>')
            bombs += 1
        tb += random.uniform(0.7, 1.4)

    # player
    mt = [m[0] for m in moves]; mx = [m[1] - pw / 2 for m in moves]
    if mt[0] > 0:
        mt.insert(0, 0); mx.insert(0, mx[0])
    o.append(f'<use href="#ship" xlink:href="#ship" y="{PLAYER_Y}" x="{mx[0]:.0f}" fill="{green}">'
             f'<animate attributeName="x" values="{";".join(f"{v:.1f}" for v in mx)}" keyTimes="{";".join(kt(v) for v in mt)}" dur="{LOOP}s" repeatCount="indefinite"/></use>')
    # ground
    o.append(f'<line x1="{FX + 14}" y1="{GROUND_Y}" x2="{FX + FW - 14}" y2="{GROUND_Y}" stroke="{green}" stroke-width="2" opacity="0.7"/>')

    # messages
    cy = FY + FH / 2 + 10
    o.append(f'<text x="{W / 2}" y="{cy}" text-anchor="middle" font-size="22" fill="{text}" letter-spacing="6" opacity="0">'
             f'WAVE 01 · READY{window(0, 1.1)}</text>')
    o.append(f'<g opacity="0">{window(T_CLEAR, LOOP - 0.15)}'
             f'<text x="{W / 2}" y="{cy}" text-anchor="middle" font-size="26" fill="{chrome}" letter-spacing="6">WAVE CLEARED</text>'
             f'<text x="{W / 2}" y="{cy + 32}" text-anchor="middle" font-size="14" fill="{dim}" letter-spacing="2">'
             f'$ ./next_wave --target=prod_</text></g>')
    o.append("</g></svg>")
    return "\n".join(o)


for dark, name in [(True, "invaders-dark.svg"), (False, "invaders-light.svg")]:
    random.seed(7)
    svg = build(dark)
    open(os.path.join(OUT, name), "w").write(svg)
    print(f"{name}: {len(svg) / 1024:.0f} KB, kills={len(kills)}, wave cleared at {T_CLEAR:.2f}s / {LOOP}s")
