"""Breakthrough: a paper plane smashes through the night itself.

A huge break in the night sky pours daylight into the frame. The plane
flies straight through the break, glass shards fly outward, and the
shards burst into a flock of birds. Drawn from scratch with the
standard library only. The program writes one deterministic PNG, with
no text in the image, no network use, and no randomness that can vary
between runs.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

SKY_TOP = (8, 10, 38)
SKY_MID = (18, 25, 76)
SKY_LOW = (34, 40, 102)
INK = (6, 8, 28)
CITY = (7, 9, 26)
PAPER = (247, 249, 255)
PAPER_SHADE = (201, 214, 242)
PAPER_DARK = (143, 163, 212)
GOLD = (255, 192, 77)
GOLD_DEEP = (224, 142, 31)
GOLD_PALE = (255, 222, 140)
CYAN = (94, 220, 255)
ICE = (184, 236, 255)
GLASS = (140, 190, 235)
HOLE_CORE = (255, 247, 214)
HOLE_GOLD = (255, 209, 102)
HOLE_SKY = (127, 200, 255)
HOLE_EDGE = (74, 168, 232)
EMBER = (255, 120, 40)

HOLE = (650, 380)
HOLE_R = 270
CORE = (730, 300)
NOSE = (665, 375)
ANGLE = math.radians(-32)

buf = bytearray(W * H * 3)


def mix(a, b, t):
    return tuple(int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3))


def sky_color(y):
    t = y / (H - 1)
    if t < 0.55:
        return mix(SKY_TOP, SKY_MID, t / 0.55)
    return mix(SKY_MID, SKY_LOW, (t - 0.55) / 0.45)


def put(x, y, rgb, alpha):
    if alpha <= 0:
        return
    if x < 0 or x >= W or y < 0 or y >= H:
        return
    i = (y * W + x) * 3
    if alpha >= 255:
        buf[i] = rgb[0]
        buf[i + 1] = rgb[1]
        buf[i + 2] = rgb[2]
        return
    inv = 255 - alpha
    buf[i] = (rgb[0] * alpha + buf[i] * inv + 127) // 255
    buf[i + 1] = (rgb[1] * alpha + buf[i + 1] * inv + 127) // 255
    buf[i + 2] = (rgb[2] * alpha + buf[i + 2] * inv + 127) // 255


def hash01(n):
    n = (n * 2654435761) & 0xFFFFFFFF
    n ^= n >> 13
    n = (n * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def _chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw.extend(buf[y * stride:(y + 1) * stride])
    data = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", data)
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def disc(cx, cy, r, rgb, alpha, soft=0):
    if r <= 0 or alpha <= 0:
        return
    x0 = max(0, int(cx - r))
    x1 = min(W - 1, int(cx + r))
    y0 = max(0, int(cy - r))
    y1 = min(H - 1, int(cy + r))
    core = max(0, r - soft)
    core2 = core * core
    r2 = r * r
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            if soft <= 0 or d2 <= core2:
                put(x, y, rgb, alpha)
            else:
                d = math.sqrt(d2)
                f = (r - d) / soft
                put(x, y, rgb, int(alpha * f))


def ring(cx, cy, rx, ry, thick, rgb, alpha):
    x0 = max(0, int(cx - rx - thick))
    x1 = min(W - 1, int(cx + rx + thick))
    y0 = max(0, int(cy - ry - thick))
    y1 = min(H - 1, int(cy + ry + thick))
    band = thick / ((rx + ry) * 0.5)
    for y in range(y0, y1 + 1):
        ny = (y - cy) / ry
        for x in range(x0, x1 + 1):
            nx = (x - cx) / rx
            d = math.sqrt(nx * nx + ny * ny)
            gap = abs(d - 1.0)
            if gap <= band * 0.5:
                put(x, y, rgb, alpha)
            elif gap <= band:
                f = 1.0 - (gap - band * 0.5) / (band * 0.5)
                put(x, y, rgb, int(alpha * f))


def stamp(cx, cy, half, rgb, alpha):
    for y in range(cy - half, cy + half + 1):
        for x in range(cx - half, cx + half + 1):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= half * half + half:
                put(x, y, rgb, alpha)


def stroke(x0, y0, x1, y1, half, rgb, alpha):
    dx = x1 - x0
    dy = y1 - y0
    steps = int(max(abs(dx), abs(dy))) + 1
    if steps <= 1:
        stamp(int(round(x0)), int(round(y0)), half, rgb, alpha)
        return
    for i in range(steps + 1):
        t = i / steps
        stamp(int(round(x0 + dx * t)), int(round(y0 + dy * t)), half, rgb, alpha)


def fill_poly(points, rgb, alpha):
    if len(points) < 3 or alpha <= 0:
        return
    ys = [p[1] for p in points]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            ax, ay = points[i]
            bx, by = points[(i + 1) % n]
            if ay == by:
                continue
            lo = ay if ay < by else by
            hi = by if ay < by else ay
            if lo <= y < hi:
                t = (y - ay) / (by - ay)
                xs.append(ax + (bx - ax) * t)
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(W - 1, int(math.floor(xs[k + 1])))
            for x in range(xa, xb + 1):
                put(x, y, rgb, alpha)


def outline_poly(points, rgb, alpha, half=1):
    n = len(points)
    for i in range(n):
        ax, ay = points[i]
        bx, by = points[(i + 1) % n]
        stroke(ax, ay, bx, by, half, rgb, alpha)


def arc_ellipse(cx, cy, rx, ry, a0, a1, half, rgb, alpha):
    steps = 90
    prev = None
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        p = (int(round(cx + math.cos(a) * rx)),
             int(round(cy + math.sin(a) * ry)))
        if prev is not None:
            stroke(prev[0], prev[1], p[0], p[1], half, rgb, alpha)
        prev = p


def paint_background():
    for y in range(H):
        c = sky_color(y)
        row = bytes(c) * W
        buf[y * W * 3:(y + 1) * W * 3] = row
    disc(512, 1060, 520, (58, 46, 96), 34, soft=260)
    disc(HOLE[0], HOLE[1], 430, (52, 74, 150), 46, soft=210)
    disc(-40, -40, 400, INK, 52, soft=230)
    disc(-40, 1064, 400, INK, 48, soft=230)
    disc(1064, 1064, 430, INK, 48, soft=230)
    fill_poly([(60, 0), (195, 0), (1024, 880), (1024, 715)], PAPER, 8)
    fill_poly([(0, 240), (0, 330), (520, 1024), (400, 1024)], ICE, 6)


def paint_stars():
    for n in range(210):
        x = int(hash01(n * 2 + 11) * W)
        y = int(hash01(n * 2 + 101) * H)
        dx = x - HOLE[0]
        dy = y - HOLE[1]
        if dx * dx + dy * dy < (HOLE_R + 24) * (HOLE_R + 24):
            continue
        if y > 900:
            continue
        s = hash01(n * 2 + 7)
        a = 55 + int(s * 165)
        put(x, y, PAPER, a)
        if s > 0.80:
            put(x + 1, y, PAPER, a // 2)
            put(x, y + 1, PAPER, a // 2)
        if s > 0.93:
            put(x - 1, y, PAPER, a // 2)
            put(x, y - 1, PAPER, a // 2)
            put(x + 2, y, PAPER, a // 3)
            put(x - 2, y, PAPER, a // 3)


def paint_moon():
    disc(150, 130, 78, GOLD_PALE, 26, soft=52)
    pts = []
    for deg in range(70, 351, 10):
        a = math.radians(deg)
        pts.append((150 + 46 * math.cos(a), 130 + 46 * math.sin(a)))
    for deg in range(350, 69, -10):
        a = math.radians(deg)
        pts.append((170 + 42 * math.cos(a), 116 + 42 * math.sin(a)))
    fill_poly(pts, (255, 244, 205), 255)


def paint_skyline():
    x = -10
    k = 0
    while x < W + 10:
        wdt = 52 + int(hash01(k * 3 + 1) * 62)
        hgt = 58 + int(hash01(k * 3 + 2) * 96)
        top = H - hgt
        fill_poly([(x, H), (x, top), (x + wdt, top), (x + wdt, H)], CITY, 255)
        if hash01(k * 3 + 3) > 0.62:
            ax = x + wdt // 2
            stroke(ax, top, ax, top - 22, 1, CITY, 255)
            put(ax, top - 23, (255, 96, 80), 220)
        for wy in range(top + 12, H - 10, 19):
            for wx in range(x + 9, x + wdt - 9, 15):
                if hash01(wx * 7 + wy * 13 + k) > 0.62:
                    for dy in range(4):
                        for ddx in range(3):
                            put(wx + ddx, wy + dy, GOLD, 175)
        x += wdt + int(hash01(k * 5 + 9) * 14)
        k += 1


def paint_hole():
    cx, cy = HOLE
    r = HOLE_R
    for y in range(max(0, cy - r), min(H - 1, cy + r) + 1):
        dy = y - cy
        half = int(math.sqrt(max(0, r * r - dy * dy)))
        for x in range(max(0, cx - half), min(W - 1, cx + half) + 1):
            dcx = x - CORE[0]
            dcy = y - CORE[1]
            dc = math.sqrt(dcx * dcx + dcy * dcy)
            t = dc / 310.0
            if t < 0.32:
                c = mix(HOLE_CORE, HOLE_GOLD, t / 0.32)
            elif t < 0.68:
                c = mix(HOLE_GOLD, HOLE_SKY, (t - 0.32) / 0.36)
            else:
                c = mix(HOLE_SKY, HOLE_EDGE, min(1.0, (t - 0.68) / 0.32))
            i = (y * W + x) * 3
            buf[i] = c[0]
            buf[i + 1] = c[1]
            buf[i + 2] = c[2]
    for ang, ln in ((-0.5, 250), (0.35, 235), (1.15, 210), (2.2, 225),
                    (-1.5, 240), (-2.4, 215), (2.9, 200), (-2.95, 190)):
        ux, uy = math.cos(ang), math.sin(ang)
        vx, vy = -uy, ux
        tip = (CORE[0] + ux * ln, CORE[1] + uy * ln)
        base1 = (CORE[0] + vx * 14, CORE[1] + vy * 14)
        base2 = (CORE[0] - vx * 14, CORE[1] - vy * 14)
        fill_poly([tip, base1, base2], PAPER, 30)


def cloud(cx, cy, s):
    disc(cx, cy + 7, int(s * 0.62), (168, 214, 248), 150)
    disc(cx - int(s * 0.55), cy + 4, int(s * 0.42), PAPER, 235)
    disc(cx + int(s * 0.55), cy + 5, int(s * 0.46), PAPER, 235)
    disc(cx, cy - int(s * 0.18), int(s * 0.55), PAPER, 245)
    disc(cx - int(s * 0.2), cy - int(s * 0.3), int(s * 0.34),
         (255, 252, 240), 245)


def paint_clouds():
    cloud(560, 250, 46)
    cloud(790, 195, 40)
    cloud(845, 385, 44)
    cloud(655, 515, 42)
    cloud(785, 525, 38)
    for (x, y, s) in ((592, 232, 9), (832, 300, 8), (706, 545, 7)):
        stroke(x - s, y, x, y - 3, 1, (52, 96, 160), 190)
        stroke(x, y - 3, x + s, y, 1, (52, 96, 160), 190)


def paint_rim():
    cx, cy = HOLE
    ring(cx, cy, HOLE_R - 6, HOLE_R - 6, 9, (20, 32, 84), 110)
    segs = 30
    for i in range(segs):
        a0 = i * 2.0 * math.pi / segs
        a1 = (i + 1) * 2.0 * math.pi / segs
        am = (a0 + a1) * 0.5
        out = HOLE_R + 4 + hash01(i * 7 + 4) * 26
        if hash01(i * 7 + 6) > 0.82:
            out += 16
        inner = HOLE_R - 18
        p0 = (cx + math.cos(a0) * inner, cy + math.sin(a0) * inner)
        p1 = (cx + math.cos(am) * out, cy + math.sin(am) * out)
        p2 = (cx + math.cos(a1) * inner, cy + math.sin(a1) * inner)
        col = ICE if i % 3 == 0 else (PAPER if i % 3 == 1 else GLASS)
        fill_poly([p0, p1, p2], col, 130)
        if i % 4 == 0:
            stroke(int(round(p0[0])), int(round(p0[1])),
                   int(round(p1[0])), int(round(p1[1])), 1, PAPER, 150)
        sunlit = -0.9 < am < 0.3
        if sunlit and i % 3 == 0:
            stroke(int(round(p1[0])), int(round(p1[1])),
                   int(round(p2[0])), int(round(p2[1])), 1, GOLD, 160)


def paint_cracks():
    cx, cy = HOLE
    for k in range(18):
        base = hash01(k * 17 + 3) * 2.0 * math.pi
        reach = 120 + hash01(k * 17 + 9) * 140
        segs = 5
        drift = (hash01(k * 17 + 13) - 0.5) * 0.45
        px = cx + math.cos(base) * (HOLE_R + 6)
        py = cy + math.sin(base) * (HOLE_R + 6)
        ang = base
        for s in range(segs):
            step = reach / segs
            ang += drift + (hash01(k * 31 + s * 7 + 1) - 0.5) * 0.32
            qx = px + math.cos(ang) * step
            qy = py + math.sin(ang) * step
            col = ICE if s % 2 == 0 else PAPER
            a = 195 - s * 38
            stroke(int(round(px)), int(round(py)),
                   int(round(qx)), int(round(qy)),
                   2 if s == 0 else 1, col, max(50, a))
            if s == 1 and hash01(k * 13 + s * 3 + 5) > 0.3:
                side = ang + 0.85
                ex = px + math.cos(side) * step * 0.6
                ey = py + math.sin(side) * step * 0.6
                stroke(int(round(px)), int(round(py)),
                       int(round(ex)), int(round(ey)), 1, ICE, 150)
            px, py = qx, qy


def paint_speed_lines():
    cx, cy = NOSE
    for k in range(11):
        ang = hash01(k * 11 + 2) * 2.0 * math.pi
        start = 210 + hash01(k * 11 + 5) * 60
        ln = 170 + hash01(k * 11 + 7) * 220
        wd = 3 + hash01(k * 11 + 9) * 4
        ux, uy = math.cos(ang), math.sin(ang)
        vx, vy = -uy, ux
        bx, by = cx + ux * start, cy + uy * start
        tip = (cx + ux * (start + ln), cy + uy * (start + ln))
        col = PAPER if k % 3 == 0 else CYAN
        fill_poly([(bx + vx * wd, by + vy * wd),
                   (bx - vx * wd, by - vy * wd), tip], col, 44)


def paint_shock():
    ring(NOSE[0], NOSE[1], 335, 315, 4, CYAN, 72)
    arc_ellipse(NOSE[0], NOSE[1], 285, 268, -1.9, -0.15, 2, PAPER, 170)
    arc_ellipse(NOSE[0], NOSE[1], 285, 268, 2.6, 3.6, 2, ICE, 130)


def paint_trail():
    ux, uy = math.cos(ANGLE), math.sin(ANGLE)
    vx, vy = -uy, ux
    tx = NOSE[0] - 425 * ux
    ty = NOSE[1] - 425 * uy
    pts = []
    for i in range(29):
        t = i / 28.0
        back = t * 600
        sway = math.sin(t * 2.1) * 42 * t - t * t * 40
        px = tx - ux * back + vx * sway
        py = ty - uy * back + vy * sway
        pts.append((px, py, 46 - 40 * t))
    for scale, col, alpha in ((1.0, GOLD_DEEP, 165),
                              (0.62, GOLD, 225),
                              (0.30, GOLD_PALE, 235)):
        for i in range(len(pts) - 1):
            ax, ay, aw = pts[i]
            bx, by, bw = pts[i + 1]
            dx, dy = bx - ax, by - ay
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            aw *= scale
            bw *= scale
            fill_poly([(ax + nx * aw, ay + ny * aw),
                       (bx + nx * bw, by + ny * bw),
                       (bx - nx * bw, by - ny * bw),
                       (ax - nx * aw, ay - ny * aw)], col, alpha)
    for i in range(len(pts) - 1):
        ax, ay, _ = pts[i]
        bx, by, _ = pts[i + 1]
        stroke(int(round(ax)), int(round(ay)), int(round(bx)), int(round(by)),
               2, mix(PAPER, GOLD, 0.5), 150)
    for i in (3, 7, 11, 15, 19, 23, 27):
        x, y, _ = pts[i]
        disc(int(round(x)), int(round(y)), 7, GOLD, 220, soft=3)
        disc(int(round(x)), int(round(y)), 3, PAPER, 245)
    for k in range(26):
        t = hash01(k * 9 + 1)
        i = int(t * 27)
        x, y, wdt = pts[i]
        off = (hash01(k * 9 + 3) - 0.5) * (wdt * 2.6 + 30)
        ex = x + vx * off + (hash01(k * 9 + 5) - 0.5) * 30
        ey = y + vy * off + (hash01(k * 9 + 7) - 0.5) * 30
        disc(int(round(ex)), int(round(ey)), 3 + int(hash01(k * 9 + 11) * 4),
             EMBER if k % 3 == 0 else GOLD, 210, soft=2)


def shard_shape(mx, my, ln, wd, tilt, seed):
    ux, uy = math.cos(tilt), math.sin(tilt)
    vx, vy = -uy, ux
    j1 = (hash01(seed + 1) - 0.5) * wd * 0.7
    j2 = (hash01(seed + 2) - 0.5) * wd * 0.7
    tip = (mx + ux * ln * 0.6 + vx * j1, my + uy * ln * 0.6 + vy * j1)
    mid = (mx + vx * wd * 0.55, my + vy * wd * 0.55)
    base = (mx - ux * ln * 0.45 + vx * j2, my - uy * ln * 0.45 + vy * j2)
    low = (mx - vx * wd * 0.42, my - vy * wd * 0.42)
    return [tip, mid, base, low]


def paint_shard(mx, my, ln, wd, tilt, seed, sunlit):
    poly = shard_shape(mx, my, ln, wd, tilt, seed)
    fill_poly(poly, ICE, 125)
    fill_poly([poly[0], poly[1], poly[3]], PAPER, 90)
    outline_poly(poly, PAPER, 195, half=1)
    stroke(int(round(poly[0][0])), int(round(poly[0][1])),
           int(round(poly[2][0])), int(round(poly[2][1])), 1, CYAN, 150)
    if sunlit:
        stroke(int(round(poly[0][0])), int(round(poly[0][1])),
               int(round(poly[1][0])), int(round(poly[1][1])), 1, GOLD, 215)


def paint_shards():
    cx, cy = NOSE
    for k in range(26):
        ang = hash01(k * 7 + 2) * 2.0 * math.pi
        dist = 300 + hash01(k * 7 + 4) * 260
        ln = 34 + hash01(k * 7 + 6) * 76
        wd = 13 + hash01(k * 7 + 8) * 22
        mx = cx + math.cos(ang) * dist
        my = cy + math.sin(ang) * dist
        tilt = ang + 0.7 + (hash01(k * 7 + 10) - 0.5) * 0.8
        sunlit = mx > cx and my < cy + 120
        paint_shard(mx, my, ln, wd, tilt, k * 11, sunlit)


def bird(cx, cy, size, tilt, pose, rgb, alpha):
    if pose == "up":
        raw = [(-1.0, -0.52), (-0.35, -0.05), (0.0, 0.05), (0.35, -0.05),
               (1.0, -0.52), (0.45, 0.18), (0.0, 0.12), (-0.45, 0.18)]
    else:
        raw = [(-1.0, -0.22), (-0.35, 0.0), (0.0, 0.06), (0.35, 0.0),
               (1.0, -0.22), (0.45, 0.20), (0.0, 0.14), (-0.45, 0.20)]
    ct, st = math.cos(tilt), math.sin(tilt)
    pts = []
    for lx, ly in raw:
        x = lx * size
        y = ly * size
        pts.append((cx + x * ct - y * st, cy + x * st + y * ct))
    fill_poly(pts, rgb, alpha)
    outline_poly(pts, INK, 75, half=1)
    disc(int(round(cx)), int(round(cy)), max(2, int(size * 0.10)), rgb, alpha)


def paint_birds():
    spots = [
        (430, 110, 44, -0.30, "up", PAPER),
        (540, 80, 48, -0.18, "flat", PAPER),
        (880, 90, 40, -0.05, "up", GOLD),
        (975, 300, 34, 0.15, "flat", PAPER),
        (980, 470, 28, 0.25, "up", PAPER),
        (930, 620, 24, 0.35, "flat", GOLD),
        (330, 150, 36, -0.34, "up", PAPER),
        (210, 300, 30, -0.24, "flat", PAPER),
        (150, 480, 26, -0.10, "up", PAPER),
        (700, 720, 22, 0.20, "flat", PAPER),
    ]
    for i, (x, y, s, tilt, pose, col) in enumerate(spots):
        if col is PAPER and i % 3 == 1:
            col = mix(PAPER, GOLD, 0.35)
        bird(x, y, s, tilt, pose, col, 255)


def paint_flash():
    cx, cy = NOSE
    disc(cx, cy, 150, CYAN, 30, soft=100)
    disc(cx, cy, 100, ICE, 50, soft=60)
    disc(cx, cy, 58, PAPER, 100, soft=35)
    disc(cx, cy, 28, PAPER, 230, soft=12)
    base = ANGLE
    for off, ln, wd in ((0.0, 250, 9), (math.pi, 130, 8),
                        (math.pi / 2, 175, 8), (-math.pi / 2, 175, 8),
                        (0.9, 105, 6), (-0.9, 105, 6),
                        (2.2, 90, 5), (-2.2, 90, 5)):
        ang = base + off
        ux, uy = math.cos(ang), math.sin(ang)
        vx, vy = -uy, ux
        tip = (cx + ux * ln, cy + uy * ln)
        tail = (cx - ux * ln * 0.30, cy - uy * ln * 0.30)
        left = (cx + vx * wd, cy + vy * wd)
        right = (cx - vx * wd, cy - vy * wd)
        fill_poly([tip, left, tail, right], PAPER, 230)
    ux, uy = math.cos(base), math.sin(base)
    vx, vy = -uy, ux
    fill_poly([(cx + ux * 170, cy + uy * 170),
               (cx + vx * 5, cy + vy * 5),
               (cx - ux * 55, cy - uy * 55),
               (cx - vx * 5, cy - vy * 5)], GOLD, 175)
    disc(cx, cy, 15, PAPER, 255, soft=5)


def paint_plane():
    ux, uy = math.cos(ANGLE), math.sin(ANGLE)
    vx, vy = -uy, ux
    nx, ny = NOSE
    tx, ty = nx - 440 * ux, ny - 440 * uy
    up = (nx - 300 * ux - 110 * vx, ny - 300 * uy - 110 * vy)
    down = (nx - 290 * ux + 130 * vx, ny - 290 * uy + 130 * vy)
    t1 = (tx - 36 * vx, ty - 36 * vy)
    t2 = (tx + 36 * vx, ty + 36 * vy)
    tm = (tx - 60 * ux, ty - 60 * uy)
    fill_poly([t1, t2, tm], PAPER_DARK, 255)
    fill_poly([NOSE, up, t1], PAPER_SHADE, 255)
    fill_poly([NOSE, down, t2], PAPER, 255)
    fill_poly([NOSE, t1, t2], mix(PAPER_SHADE, PAPER_DARK, 0.5), 255)
    fill_poly([NOSE, (nx - 260 * ux - 12 * vx, ny - 260 * uy - 12 * vy),
               (nx - 260 * ux + 12 * vx, ny - 260 * uy + 12 * vy)],
              mix(PAPER, GOLD, 0.22), 255)
    stroke(int(round(nx)), int(round(ny)), int(round(tx)), int(round(ty)),
           2, PAPER_DARK, 210)
    q1 = (nx - 240 * ux - 16 * vx, ny - 240 * uy - 16 * vy)
    stroke(int(round(q1[0])), int(round(q1[1])), int(round(up[0])),
           int(round(up[1])), 1, PAPER_DARK, 150)
    q2 = (nx - 240 * ux + 16 * vx, ny - 240 * uy + 16 * vy)
    stroke(int(round(q2[0])), int(round(q2[1])), int(round(down[0])),
           int(round(down[1])), 1, PAPER_DARK, 150)
    stroke(int(round(up[0])), int(round(up[1])), int(round(t1[0])),
           int(round(t1[1])), 2, INK, 120)
    stroke(int(round(down[0])), int(round(down[1])), int(round(t2[0])),
           int(round(t2[1])), 2, INK, 120)
    stroke(int(round(t1[0])), int(round(t1[1])), int(round(tm[0])),
           int(round(tm[1])), 2, INK, 120)
    stroke(int(round(tm[0])), int(round(tm[1])), int(round(t2[0])),
           int(round(t2[1])), 2, INK, 120)
    stroke(int(round(nx)), int(round(ny)), int(round(up[0])),
           int(round(up[1])), 2, PAPER, 255)
    stroke(int(round(nx)), int(round(ny)), int(round(down[0])),
           int(round(down[1])), 3, GOLD, 240)
    disc(int(round(nx)), int(round(ny)), 8, PAPER, 255, soft=3)


def sparkle(x, y, s, rgb, alpha):
    fill_poly([(x, y - s), (x + s * 0.28, y), (x, y + s), (x - s * 0.28, y)],
              rgb, alpha)
    fill_poly([(x - s, y), (x, y - s * 0.28), (x + s, y), (x, y + s * 0.28)],
              rgb, alpha)
    disc(x, y, 3, PAPER, 255)


def paint_sparkles():
    sparkle(905, 235, 30, PAPER, 230)
    sparkle(470, 195, 24, PAPER, 215)
    sparkle(820, 585, 24, GOLD, 215)
    sparkle(300, 760, 20, ICE, 205)
    sparkle(955, 480, 20, PAPER, 210)
    sparkle(640, 700, 18, GOLD, 200)
    sparkle(350, 330, 18, ICE, 200)
    sparkle(700, 170, 18, PAPER, 205)


def paint_particles(count, dmin, dmax, seed):
    cx, cy = NOSE
    for k in range(count):
        ang = hash01(k * 13 + seed + 2) * 2.0 * math.pi
        dist = dmin + (hash01(k * 13 + seed + 5) ** 1.4) * (dmax - dmin)
        x = int(round(cx + math.cos(ang) * dist))
        y = int(round(cy + math.sin(ang) * dist))
        s = 2 + int(hash01(k * 13 + seed + 7) * 5)
        pick = hash01(k * 13 + seed + 9)
        col = PAPER if pick < 0.4 else (GOLD if pick < 0.7 else CYAN)
        disc(x, y, s, col, 150 + int(hash01(k * 13 + seed + 11) * 105),
             soft=1)


def paint_foreground_shards():
    giants = [
        (905, 845, 150, 52, 0.7, 501),
        (985, 700, 110, 40, -0.5, 502),
        (70, 210, 90, 32, 2.4, 503),
        (55, 430, 90, 34, 1.2, 504),
    ]
    for (mx, my, ln, wd, tilt, seed) in giants:
        poly = shard_shape(mx, my, ln, wd, tilt, seed)
        fill_poly(poly, ICE, 85)
        fill_poly([poly[0], poly[1], poly[3]], PAPER, 60)
        outline_poly(poly, PAPER, 210, half=1)
        stroke(int(round(poly[0][0])), int(round(poly[0][1])),
               int(round(poly[2][0])), int(round(poly[2][1])), 1, CYAN, 150)
        disc(int(round(poly[0][0])), int(round(poly[0][1])), 4, PAPER, 240)


def main():
    paint_background()
    paint_stars()
    paint_moon()
    paint_skyline()
    paint_hole()
    paint_clouds()
    paint_rim()
    paint_cracks()
    paint_speed_lines()
    paint_shock()
    paint_trail()
    paint_shards()
    paint_particles(100, 170, 670, 0)
    paint_birds()
    paint_flash()
    paint_plane()
    paint_sparkles()
    paint_particles(36, 200, 420, 500)
    paint_foreground_shards()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    write_png(os.path.join(outdir, "entry.png"))


if __name__ == "__main__":
    main()
