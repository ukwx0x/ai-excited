#!/usr/bin/env python3
"""Breakthrough.

A paper dart plane smashes through the night sky and daylight pours
through the break. Drawn from scratch with the standard library only:
a framebuffer, polygon fills, glow passes, and a PNG encoder.
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
OUT_PATH = "/output/entry.png"

fb = bytearray(W * H * 3)


def clamp_byte(v):
    v = int(v + 0.5)
    if v < 0:
        return 0
    if v > 255:
        return 255
    return v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rgb(c0, c1, t):
    return (lerp(c0[0], c1[0], t), lerp(c0[1], c1[1], t), lerp(c0[2], c1[2], t))


def multi_stop(stops, t):
    # stops: list of (pos, rgb) sorted by pos; t in the same scale.
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            p0, c0 = stops[i - 1]
            p1, c1 = stops[i]
            f = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
            return lerp_rgb(c0, c1, f)
    return stops[-1][1]


def hspan(y, xa, xb, r, g, b):
    if y < 0 or y >= H:
        return
    x0 = int(math.ceil(xa))
    x1 = int(xb)
    if x0 < 0:
        x0 = 0
    if x1 > W:
        x1 = W
    if x1 <= x0:
        return
    o = (y * W + x0) * 3
    fb[o:o + (x1 - x0) * 3] = bytes((r, g, b)) * (x1 - x0)


def hspan_blend(y, xa, xb, r, g, b, a):
    if y < 0 or y >= H or a <= 0.0:
        return
    x0 = int(math.ceil(xa))
    x1 = int(xb)
    if x0 < 0:
        x0 = 0
    if x1 > W:
        x1 = W
    ia = 1.0 - a
    for x in range(x0, x1):
        o = (y * W + x) * 3
        fb[o] = clamp_byte(fb[o] * ia + r * a)
        fb[o + 1] = clamp_byte(fb[o + 1] * ia + g * a)
        fb[o + 2] = clamp_byte(fb[o + 2] * ia + b * a)


def blend_px(x, y, r, g, b, a):
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        o = (y * W + x) * 3
        ia = 1.0 - a
        fb[o] = clamp_byte(fb[o] * ia + r * a)
        fb[o + 1] = clamp_byte(fb[o + 1] * ia + g * a)
        fb[o + 2] = clamp_byte(fb[o + 2] * ia + b * a)


def scan_spans(pts, y):
    # x intersections of polygon edges with the line y + 0.5.
    yc = y + 0.5
    xs = []
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 <= yc < y1) or (y1 <= yc < y0):
            t = (yc - y0) / (y1 - y0)
            xs.append(x0 + t * (x1 - x0))
    xs.sort()
    return xs


def fill_poly(pts, rgb):
    r, g, b = rgb
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H, int(max(ys)) + 1)
    for y in range(y0, y1):
        xs = scan_spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            hspan(y, xs[k], xs[k + 1], r, g, b)


def fill_poly_blend(pts, rgb, a):
    r, g, b = rgb
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H, int(max(ys)) + 1)
    for y in range(y0, y1):
        xs = scan_spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            hspan_blend(y, xs[k], xs[k + 1], r, g, b, a)


def fill_poly_fn(pts, fn):
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H, int(max(ys)) + 1)
    for y in range(y0, y1):
        xs = scan_spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            x0 = max(0, int(math.ceil(xs[k])))
            x1 = min(W, int(xs[k + 1]))
            for x in range(x0, x1):
                r, g, b = fn(x, y)
                o = (y * W + x) * 3
                fb[o] = clamp_byte(r)
                fb[o + 1] = clamp_byte(g)
                fb[o + 2] = clamp_byte(b)


def fill_circle(cx, cy, rad, rgb):
    r, g, b = rgb
    y0 = max(0, int(math.ceil(cy - rad)))
    y1 = min(H, int(cy + rad) + 1)
    for y in range(y0, y1):
        dy = y + 0.5 - cy
        rem = rad * rad - dy * dy
        if rem < 0:
            continue
        dx = math.sqrt(rem)
        hspan(y, cx - dx, cx + dx, r, g, b)


def fill_circle_blend(cx, cy, rad, rgb, a):
    r, g, b = rgb
    y0 = max(0, int(math.ceil(cy - rad)))
    y1 = min(H, int(cy + rad) + 1)
    for y in range(y0, y1):
        dy = y + 0.5 - cy
        rem = rad * rad - dy * dy
        if rem < 0:
            continue
        dx = math.sqrt(rem)
        hspan_blend(y, cx - dx, cx + dx, r, g, b, a)


def disc_add(cx, cy, rad, rgb, strength):
    # Soft additive disc with quadratic falloff.
    r, g, b = rgb
    x0 = max(0, int(cx - rad))
    x1 = min(W, int(cx + rad) + 1)
    y0 = max(0, int(cy - rad))
    y1 = min(H, int(cy + rad) + 1)
    r2 = rad * rad
    dx2 = []
    for x in range(x0, x1):
        dx = x + 0.5 - cx
        dx2.append(dx * dx)
    for y in range(y0, y1):
        dy = y + 0.5 - cy
        dy2 = dy * dy
        row = y * W
        for xi in range(x1 - x0):
            d2 = dx2[xi] + dy2
            if d2 >= r2:
                continue
            t = 1.0 - d2 / r2
            s = strength * t * t
            o = (row + x0 + xi) * 3
            fb[o] = min(255, fb[o] + int(r * s + 0.5))
            fb[o + 1] = min(255, fb[o + 1] + int(g * s + 0.5))
            fb[o + 2] = min(255, fb[o + 2] + int(b * s + 0.5))


def segment_quad(p0, p1, w0, w1):
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    ln = math.hypot(dx, dy)
    if ln == 0:
        return None
    nx = -dy / ln
    ny = dx / ln
    a0 = w0 * 0.5
    a1 = w1 * 0.5
    return [
        (x0 + nx * a0, y0 + ny * a0),
        (x1 + nx * a1, y1 + ny * a1),
        (x1 - nx * a1, y1 - ny * a1),
        (x0 - nx * a0, y0 - ny * a0),
    ]


def stroke_polyline(pts, w0, w1, rgb, a, closed=False):
    # Tapered stroke along a path, width lerped from w0 to w1 by length.
    segs = list(zip(pts, pts[1:]))
    if closed and len(pts) > 2:
        segs.append((pts[-1], pts[0]))
    total = 0.0
    lens = []
    for p0, p1 in segs:
        ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        lens.append(ln)
        total += ln
    if total == 0:
        return
    acc = 0.0
    for (p0, p1), ln in zip(segs, lens):
        wa = lerp(w0, w1, acc / total)
        wb = lerp(w0, w1, (acc + ln) / total)
        quad = segment_quad(p0, p1, wa, wb)
        if quad:
            fill_poly_blend(quad, rgb, a)
        fill_circle_blend(p0[0], p0[1], max(wa, 1.0) * 0.5, rgb, a)
        acc += ln
    fill_circle_blend(segs[-1][1][0], segs[-1][1][1], max(w1, 1.0) * 0.5, rgb, a)


def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xin = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xin:
                inside = not inside
    return inside


def draw_sky():
    stops = [(0.0, (7, 9, 32)), (430.0, (16, 20, 58)),
             (760.0, (30, 32, 82)), (1024.0, (24, 26, 66))]
    for y in range(H):
        c = multi_stop(stops, float(y))
        hspan(y, 0, W, clamp_byte(c[0]), clamp_byte(c[1]), clamp_byte(c[2]))


def draw_stars(rng):
    palette = [(255, 255, 255), (255, 240, 210), (210, 225, 255)]
    for _ in range(380):
        x = rng.randrange(W)
        y = rng.randrange(880)
        bright = rng.uniform(0.45, 1.0)
        c = palette[rng.randrange(len(palette))]
        r = int(c[0] * bright)
        g = int(c[1] * bright)
        b = int(c[2] * bright)
        o = (y * W + x) * 3
        fb[o] = r
        fb[o + 1] = g
        fb[o + 2] = b
        if rng.random() < 0.14 and x + 1 < W:
            o2 = (y * W + x + 1) * 3
            fb[o2] = r
            fb[o2 + 1] = g
            fb[o2 + 2] = b
    for _ in range(14):
        x = rng.randrange(30, W - 30)
        y = rng.randrange(30, 700)
        arm = rng.randrange(5, 10)
        for d in range(1, arm + 1):
            a = 0.85 * (1.0 - d / (arm + 1.0))
            blend_px(x + d, y, 255, 255, 255, a)
            blend_px(x - d, y, 255, 255, 255, a)
            blend_px(x, y + d, 255, 255, 255, a)
            blend_px(x, y - d, 255, 255, 255, a)
        fill_circle_blend(x, y, 1.6, (255, 255, 255), 0.95)


def draw_moon():
    cx, cy, rad = 168.0, 158.0, 52.0
    disc_add(cx, cy, 150.0, (150, 170, 235), 0.30)
    fill_circle(cx, cy, rad, (238, 240, 250))
    fill_circle_blend(cx + 12.0, cy + 14.0, 46.0, (198, 206, 232), 0.22)
    for mx, my, mr in [(-18.0, -12.0, 12.0), (14.0, -20.0, 9.0),
                       (8.0, 16.0, 14.0), (-6.0, 24.0, 8.0)]:
        fill_circle_blend(cx + mx, cy + my, mr, (206, 212, 234), 0.5)


def draw_skyline(rng):
    x = -12.0
    windows = 0
    while x < W + 12:
        w = rng.uniform(42.0, 105.0)
        tall = rng.random() < 0.08
        top = rng.uniform(800.0, 845.0) if tall else rng.uniform(845.0, 968.0)
        fill_poly([(x, top), (x + w, top), (x + w, H), (x, H)], (11, 13, 32))
        if rng.random() < 0.30:
            sw = w * 0.62
            sx = x + (w - sw) * 0.5
            fill_poly([(sx, top - 26.0), (sx + sw, top - 26.0),
                       (sx + sw, top), (sx, top)], (11, 13, 32))
        if rng.random() < 0.22:
            ax = x + w * rng.uniform(0.3, 0.7)
            ah = rng.uniform(18.0, 34.0)
            fill_poly([(ax - 1.0, top - ah), (ax + 1.0, top - ah),
                       (ax + 1.0, top), (ax - 1.0, top)], (11, 13, 32))
            fill_circle(ax, top - ah, 1.8, (255, 70, 60))
        cols = int(w // 13)
        rows = int((H - top) // 17)
        for ci in range(cols):
            for ri in range(rows):
                if windows >= 170:
                    break
                if rng.random() < 0.11:
                    wx = x + 5.0 + ci * 13.0
                    wy = top + 7.0 + ri * 17.0
                    warm = rng.random() < 0.7
                    col = (255, 186, 95) if warm else (185, 210, 255)
                    fill_poly([(wx, wy), (wx + 3.0, wy), (wx + 3.0, wy + 5.0),
                               (wx, wy + 5.0)], col)
                    windows += 1
        x += w + rng.uniform(2.0, 14.0)


HOLE_CX = 565.0
HOLE_CY = 445.0
HOLE_R = 238.0


def hole_points(rng):
    pts = []
    n = 30
    for i in range(n):
        th = 2.0 * math.pi * i / n
        f = (1.0 + 0.16 * math.sin(3.0 * th + 1.3)
             + 0.10 * math.sin(7.0 * th + 4.1)
             + 0.06 * math.sin(11.0 * th + 2.2)
             + rng.uniform(-0.05, 0.05))
        if i % 5 == 2:
            f *= 1.16
        f = max(0.76, min(1.24, f))
        r = HOLE_R * f
        pts.append((HOLE_CX + r * math.cos(th), HOLE_CY + r * math.sin(th)))
    return pts


def radius_at(pts, theta):
    # Interpolate the polygon radius at an angle. Vertices run in
    # increasing angle order, so index order matches angle order.
    n = len(pts)
    t = theta % (2.0 * math.pi)
    pos = t / (2.0 * math.pi) * n
    i0 = int(pos) % n
    i1 = (i0 + 1) % n
    frac = pos - int(pos)
    r0 = math.hypot(pts[i0][0] - HOLE_CX, pts[i0][1] - HOLE_CY)
    r1 = math.hypot(pts[i1][0] - HOLE_CX, pts[i1][1] - HOLE_CY)
    return r0 + (r1 - r0) * frac


def draw_hole(pts, rng):
    disc_add(HOLE_CX, HOLE_CY, 430.0, (255, 176, 92), 0.50)
    # Torn dark rim: the hole shape grown a little, painted dark first.
    rim = []
    for (x, y) in pts:
        rim.append((HOLE_CX + (x - HOLE_CX) * 1.04,
                    HOLE_CY + (y - HOLE_CY) * 1.04))
    fill_poly(rim, (13, 15, 38))
    # Daylight: radial dawn gradient from a hot core.
    core_x = HOLE_CX - 5.0
    core_y = HOLE_CY - 45.0
    stops = [(0.0, (255, 253, 242)), (0.30, (255, 235, 180)),
             (0.55, (255, 205, 120)), (0.78, (255, 172, 88)),
             (1.0, (248, 138, 62))]
    table = []
    for i in range(256):
        t = math.sqrt(i / 255.0)
        table.append(multi_stop(stops, t))
    r2n = HOLE_R * HOLE_R

    def daylight(x, y):
        dx = x + 0.5 - core_x
        dy = y + 0.5 - core_y
        b = int((dx * dx + dy * dy) / r2n * 255.0)
        if b > 255:
            b = 255
        return table[b]

    fill_poly_fn(pts, daylight)
    # Faint sun rays inside the break, each walked to the torn edge.
    for k in range(6):
        th = -2.8 + k * 0.85 + rng.uniform(-0.08, 0.08)
        dx = math.cos(th)
        dy = math.sin(th)
        ex, ey = core_x, core_y
        for _step in range(60):
            nx = ex + dx * 6.0
            ny = ey + dy * 6.0
            if not point_in_poly(nx, ny, pts):
                break
            ex, ey = nx, ny
        stroke_polyline([(core_x, core_y), (ex, ey)], 24.0, 3.0,
                        (255, 246, 220), 0.10)
    # Lit torn edge.
    stroke_polyline(pts, 3.0, 3.0, (255, 228, 170), 0.95, closed=True)


def draw_cracks(pts, rng):
    for _ in range(11):
        th = rng.uniform(0.0, 2.0 * math.pi)
        r0 = radius_at(pts, th) * 0.90
        x = HOLE_CX + r0 * math.cos(th)
        y = HOLE_CY + r0 * math.sin(th)
        heading = th
        steps = rng.randrange(7, 16)
        path = [(x, y)]
        for _s in range(steps):
            heading += rng.uniform(-0.38, 0.38)
            ln = rng.uniform(16.0, 27.0)
            x += ln * math.cos(heading)
            y += ln * math.sin(heading)
            path.append((x, y))
        stroke_polyline(path, 11.0, 5.0, (255, 150, 60), 0.20)
        stroke_polyline(path, 5.0, 1.4, (255, 222, 150), 0.95)
        if rng.random() < 0.4 and len(path) > 4:
            bi = len(path) * 3 // 5
            bx, by = path[bi]
            bh = heading + rng.uniform(0.6, 1.1) * (1 if rng.random() < 0.5 else -1)
            bpath = [(bx, by)]
            for _s in range(rng.randrange(4, 7)):
                bh += rng.uniform(-0.3, 0.3)
                ln = rng.uniform(12.0, 20.0)
                bx += ln * math.cos(bh)
                by += ln * math.sin(bh)
                bpath.append((bx, by))
            stroke_polyline(bpath, 7.0, 3.0, (255, 150, 60), 0.18)
            stroke_polyline(bpath, 2.6, 1.0, (255, 222, 150), 0.9)


def draw_shards(rng):
    for si in range(15):
        th = rng.uniform(0.0, 2.0 * math.pi)
        dist = HOLE_R * rng.uniform(1.02, 1.85)
        cx = HOLE_CX + dist * math.cos(th)
        cy = HOLE_CY + dist * math.sin(th)
        if cy < 90.0 or cy > 934.0 or cx < 90.0 or cx > W - 90.0:
            continue
        s = rng.uniform(20.0, 85.0)
        ux, uy = math.cos(th), math.sin(th)
        rot = rng.uniform(-0.5, 0.5)
        ca, sa = math.cos(rot), math.sin(rot)
        ux, uy = ux * ca - uy * sa, ux * sa + uy * ca
        px, py = -uy, ux
        j1 = rng.uniform(0.7, 1.3)
        j2 = rng.uniform(0.7, 1.3)
        p1 = (cx + ux * s * 0.9, cy + uy * s * 0.9)
        p2 = (cx - ux * s * 0.30 + px * s * 0.42 * j1,
              cy - uy * s * 0.30 + py * s * 0.42 * j1)
        p3 = (cx - ux * s * 0.35 - px * s * 0.42 * j2,
              cy - uy * s * 0.35 - py * s * 0.42 * j2)
        if rng.random() < 0.6:
            p4 = (cx - ux * s * 0.55, cy - uy * s * 0.55)
            shape = [p1, p2, p4, p3]
        else:
            shape = [p1, p2, p3]
        fill_poly_blend(shape, (186, 216, 246), 0.82)
        edge_col = (240, 248, 255)
        dark_col = (110, 130, 170)
        # Bright edge facing the hole, darker edges elsewhere.
        stroke_polyline([p2, p3], 2.0, 2.0, edge_col, 0.9)
        stroke_polyline([p1, p2], 1.5, 1.5, dark_col, 0.7)
        stroke_polyline([p3, p1], 1.5, 1.5, dark_col, 0.7)
        if si % 5 == 0:
            ix, iy = int(cx), int(cy)
            for d in range(1, 8):
                a = 0.8 * (1.0 - d / 8.0)
                blend_px(ix + d, iy, 255, 255, 255, a)
                blend_px(ix - d, iy, 255, 255, 255, a)
                blend_px(ix, iy + d, 255, 255, 255, a)
                blend_px(ix, iy - d, 255, 255, 255, a)


PLANE_NOSE = (850.0, 220.0)
PLANE_ANG = -22.0 * math.pi / 180.0
PLANE_FAR = (-290.0, -150.0)
PLANE_TAIL_TOP = (-242.0, -28.0)
PLANE_TAIL_BOT = (-218.0, 30.0)
PLANE_TAIL = (-230.0, 1.0)
PLANE_NEAR = (-175.0, 78.0)
PLANE_FOLD = (-110.0, 34.0)
PLANE_INNER = (-60.0, 26.0)


def plane_pt(lx, ly):
    c = math.cos(PLANE_ANG)
    s = math.sin(PLANE_ANG)
    return (PLANE_NOSE[0] + lx * c - ly * s,
            PLANE_NOSE[1] + lx * s + ly * c)


def draw_plane():
    nose = plane_pt(0.0, 0.0)
    far = plane_pt(*PLANE_FAR)
    tail_top = plane_pt(*PLANE_TAIL_TOP)
    tail_bot = plane_pt(*PLANE_TAIL_BOT)
    near = plane_pt(*PLANE_NEAR)
    fold = plane_pt(*PLANE_FOLD)
    inner = plane_pt(*PLANE_INNER)
    fill_poly([nose, far, tail_top], (251, 253, 255))
    fill_poly([nose, tail_top, tail_bot], (206, 217, 238))
    fill_poly([nose, tail_bot, near], (184, 197, 220))
    fill_poly_blend([nose, tail_bot, near], (255, 200, 130), 0.14)
    fill_poly([nose, inner, fold], (158, 172, 198))
    stroke_polyline([nose, far, tail_top, tail_bot, near], 3.0, 3.0,
                    (18, 24, 52), 0.7, closed=True)
    stroke_polyline([nose, tail_top], 3.0, 3.0, (140, 152, 180), 0.8)
    stroke_polyline([nose, far], 3.0, 3.0, (255, 255, 255), 0.95)
    stroke_polyline([tail_bot, near], 3.0, 3.0, (255, 214, 140), 0.9)
    stroke_polyline([nose, near], 3.0, 3.0, (255, 214, 140), 0.9)


def draw_trail(tail):
    p0 = tail
    p1 = (480.0, 380.0)
    p2 = (360.0, 540.0)
    p3 = (270.0, 645.0)
    samples = []
    n = 70
    for i in range(n + 1):
        t = i / n
        mt = 1.0 - t
        x = (mt * mt * mt * p0[0] + 3.0 * mt * mt * t * p1[0]
             + 3.0 * mt * t * t * p2[0] + t * t * t * p3[0])
        y = (mt * mt * mt * p0[1] + 3.0 * mt * t * p1[1]
             + 3.0 * mt * t * t * p2[1] + t * t * t * p3[1])
        samples.append((x, y))
    for i, (x, y) in enumerate(samples):
        t = i / n
        rad = 30.0 * (1.0 - t) ** 0.8 + 3.0
        col = lerp_rgb((255, 244, 205), (255, 140, 55), t)
        disc_add(x, y, rad, (int(col[0]), int(col[1]), int(col[2])),
                 0.50 * (1.0 - t * 0.5))
    stroke_polyline(samples, 6.0, 1.5, (255, 250, 230), 0.8)
    rng = random.Random(31337)
    for _ in range(16):
        t = rng.uniform(0.1, 0.95)
        x, y = samples[int(t * n)]
        x += rng.uniform(-26.0, 26.0)
        y += rng.uniform(-26.0, 26.0)
        disc_add(x, y, rng.uniform(2.0, 4.5), (255, 240, 200), 0.8)


def draw_vignette():
    cx, cy = 512.0, 512.0
    scale = 724.0
    table = []
    for i in range(2048):
        d2 = i / 2047.0
        t = (d2 - 0.30) / 0.70
        if t < 0.0:
            t = 0.0
        if t > 1.0:
            t = 1.0
        table.append(1.0 - 0.16 * t * t)
    for y in range(H):
        dy = (y + 0.5 - cy) / scale
        dy2 = dy * dy
        if dy2 < 0.30:
            half = scale * math.sqrt(0.30 - dy2)
            xl = int(cx - half)
            xr = int(cx + half) + 1
            x_ranges = [(0, max(0, xl)), (min(W, xr), W)]
        else:
            x_ranges = [(0, W)]
        for (x0, x1) in x_ranges:
            for x in range(x0, x1):
                dx = (x + 0.5 - cx) / scale
                d2 = dx * dx + dy2
                idx = int(d2 * 2047.0)
                if idx > 2047:
                    idx = 2047
                f = table[idx]
                if f >= 1.0:
                    continue
                o = (y * W + x) * 3
                fb[o] = int(fb[o] * f + 0.5)
                fb[o + 1] = int(fb[o + 1] * f + 0.5)
                fb[o + 2] = int(fb[o + 2] * f + 0.5)


def png_bytes():
    stride = W * 3
    raw = bytearray()
    prev = bytes(stride)
    for y in range(H):
        row = bytes(fb[y * stride:(y + 1) * stride])
        filt = bytes((a - b) & 0xFF for a, b in zip(row, prev))
        raw.append(2)
        raw += filt
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data +
                struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    rng = random.Random(20261116)
    draw_sky()
    draw_stars(rng)
    draw_moon()
    draw_skyline(rng)
    pts = hole_points(rng)
    draw_hole(pts, rng)
    draw_cracks(pts, rng)
    draw_shards(rng)
    tail = plane_pt(*PLANE_TAIL)
    draw_trail(tail)
    draw_plane()
    draw_vignette()
    data = png_bytes()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
