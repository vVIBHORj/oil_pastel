
"""
Oil Pastel Patch Painter
------------------------
Give it an image and it "paints" it as an oil pastel artwork on a paper canvas.
The artwork is NOT generated all at once: the canvas is filled patch by patch at
random places, in three passes (broad -> medium -> detail), until the picture is
complete.

Usage:
    python oil_pastel_patches.py photo.jpg
    python oil_pastel_patches.py photo.jpg --video timelapse.mp4 --speed 4
    python oil_pastel_patches.py photo.jpg --no-window          # headless (no live window)

Keys (live window):  SPACE = pause/resume   S = save snapshot   Q / ESC = quit

Requires:  pip install opencv-python numpy
"""

import argparse
import math
import os
import sys
import time

import cv2
import numpy as np


# --------------------------------------------------------------------------- #
#  Image preparation
# --------------------------------------------------------------------------- #
def load_image(path, max_side):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"Could not read image: {path}")
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1.0 or max(h, w) < max_side * 0.6:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
                         if scale < 1 else cv2.INTER_CUBIC)
    return img


def boost(img, sat=1.28, val=1.04):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * sat, 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] * val, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def make_color_sources(img):
    """Three colour references: coarse (very smooth) -> fine (keeps detail)."""
    fine = cv2.bilateralFilter(img, 7, 40, 5)
    mid = cv2.bilateralFilter(fine, 9, 55, 7)
    coarse = cv2.pyrMeanShiftFiltering(mid, 10, 32)
    coarse = cv2.GaussianBlur(coarse, (0, 0), 2.0)
    return boost(coarse, 1.3), boost(mid, 1.28), boost(fine, 1.22)


def stroke_field(img, sigma=6):
    """Orientation field (along edges) + coherence + edge energy."""
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 2).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + math.pi / 2  # stroke runs along edges
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6)
    energy = np.sqrt(jxx + jyy)
    return theta.astype(np.float32), coherence.astype(np.float32), energy.astype(np.float32)


# --------------------------------------------------------------------------- #
#  Canvas / paper
# --------------------------------------------------------------------------- #
def make_paper(h, w, rng):
    base = np.array([226, 236, 243], np.float32)  # warm cream (BGR)
    n1 = rng.normal(0, 1, (h, w)).astype(np.float32)
    n2 = rng.normal(0, 1, (h, w)).astype(np.float32)
    fine = cv2.GaussianBlur(n1, (0, 0), 0.8)
    broad = cv2.GaussianBlur(n2, (0, 0), 4.0)
    fine /= fine.std() + 1e-6
    broad /= broad.std() + 1e-6
    paper = base[None, None, :] + (fine * 5.0 + broad * 3.0)[..., None]
    # "tooth": raised grain that catches pigment (0..1, mean ~0.5)
    tooth = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.1)
    tooth = np.clip(0.5 + tooth / (tooth.std() + 1e-6) * 0.2, 0, 1).astype(np.float32)
    return np.clip(paper, 0, 255).astype(np.float32), tooth


def build_frame_base(h, w, margin, rng):
    """Dark table + soft shadow + cream paper board with a border + masking tape."""
    H, W = h + 2 * margin, w + 2 * margin
    pad = margin
    FH, FW = H + 2 * pad, W + 2 * pad
    bg = np.full((FH, FW, 3), 52, np.float32)
    bg += cv2.GaussianBlur(rng.normal(0, 1, (FH, FW)).astype(np.float32), (0, 0), 1.5)[..., None] * 3
    yy, xx = np.mgrid[0:FH, 0:FW].astype(np.float32)
    vig = 1 - 0.25 * (((xx - FW / 2) / (FW / 2)) ** 2 + ((yy - FH / 2) / (FH / 2)) ** 2)
    bg *= vig[..., None]

    shadow = np.zeros((FH, FW), np.float32)
    cv2.rectangle(shadow, (pad + 7, pad + 10), (pad + W + 7, pad + H + 10), 1.0, -1)
    shadow = cv2.GaussianBlur(shadow, (0, 0), 9)
    bg *= (1 - 0.55 * shadow)[..., None]

    board, _ = make_paper(H, W, rng)
    bg[pad:pad + H, pad:pad + W] = board

    # masking tape on the four corners (RGBA-ish layer)
    tape_col = np.zeros((FH, FW, 3), np.float32)
    tape_a = np.zeros((FH, FW), np.float32)
    tw, tl = int(margin * 0.9), int(margin * 2.2)
    corners = [(pad, pad, -38), (pad + W, pad, 38), (pad, pad + H, 38), (pad + W, pad + H, -38)]
    for cx, cy, ang in corners:
        rect = ((cx, cy), (tl, tw), ang)
        box = cv2.boxPoints(rect).astype(np.int32)
        cv2.fillPoly(tape_a, [box], 0.82)
        cv2.fillPoly(tape_col, [box], (170, 205, 222))
    tape_a = cv2.GaussianBlur(tape_a, (0, 0), 0.8)
    return bg, tape_col, tape_a, (pad + margin, pad + margin)


# --------------------------------------------------------------------------- #
#  Painter
# --------------------------------------------------------------------------- #
# (patch radius, stroke width, stroke length, stroke density) as fractions of image size
PASSES = [
    dict(name="Broad colour blocking", r=0.100, w=0.026, l=0.080, dens=3.4, src=0, edge_only=False),
    dict(name="Mid-tone layering",     r=0.056, w=0.013, l=0.045, dens=2.6, src=1, edge_only=False),
    dict(name="Detail & highlights",   r=0.031, w=0.0065, l=0.024, dens=2.0, src=2, edge_only=True),
]


class OilPastelPainter:
    def __init__(self, img, seed=None, density=1.0):
        self.rng = np.random.default_rng(seed)
        self.img = img
        self.h, self.w = img.shape[:2]
        self.S = min(self.h, self.w)
        self.density = density
        self.sources = make_color_sources(img)
        self.theta, self.coh, self.energy = stroke_field(self.sources[1])

        self.canvas, self.tooth = make_paper(self.h, self.w, self.rng)
        self.height = np.zeros((self.h, self.w), np.float32)   # wax relief
        self.cover = np.zeros((self.h, self.w), np.float32)    # how covered each pixel is

        self.margin = max(18, int(0.055 * max(self.h, self.w)))
        self.frame_base, self.tape_col, self.tape_a, self.origin = build_frame_base(
            self.h, self.w, self.margin, self.rng)

    # ---------------- patch shape ---------------- #
    def blob_mask(self, r):
        size = int(r * 2.5) | 1
        c = size // 2
        n = 26
        ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
        rad = r * (0.78 + 0.34 * self.rng.random(n))
        rad = (np.roll(rad, 1) + rad * 2 + np.roll(rad, -1)) / 4  # smooth ring
        pts = np.stack([c + rad * np.cos(ang), c + rad * np.sin(ang)], 1).astype(np.int32)
        m = np.zeros((size, size), np.float32)
        cv2.fillPoly(m, [pts], 1.0, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), max(1.0, r * 0.07))
        return m, c

    # ---------------- one stroke ---------------- #
    def trace(self, x, y, length, step):
        ix, iy = int(np.clip(x, 0, self.w - 1)), int(np.clip(y, 0, self.h - 1))
        coh = float(self.coh[iy, ix])
        wobble = 0.10 + 0.55 * (1 - coh)
        base = float(self.theta[iy, ix]) + self.rng.normal(0, 0.12 + 0.5 * (1 - coh))
        n_half = max(2, int(length / step / 2))

        def walk(sign):
            px, py = x, y
            th = base
            prev = np.array([math.cos(th), math.sin(th)]) * sign
            out = []
            for _ in range(n_half):
                jx, jy = int(np.clip(px, 0, self.w - 1)), int(np.clip(py, 0, self.h - 1))
                th = float(self.theta[jy, jx]) + self.rng.normal(0, wobble * 0.35)
                d = np.array([math.cos(th), math.sin(th)])
                if d @ prev < 0:
                    d = -d
                d = 0.6 * prev + 0.4 * d
                d /= np.linalg.norm(d) + 1e-9
                px, py = px + d[0] * step, py + d[1] * step
                out.append((px, py))
                prev = d
            return out

        back = walk(-1)[::-1]
        fwd = walk(+1)
        return np.array(back + [(x, y)] + fwd, np.float32)

    def paint_stroke(self, pts, width, color, patch, px0, py0, pressure):
        pmask = patch
        ph, pw = pmask.shape
        pad = int(width / 2) + 3
        x0 = int(max(pts[:, 0].min() - pad, px0, 0))
        y0 = int(max(pts[:, 1].min() - pad, py0, 0))
        x1 = int(min(pts[:, 0].max() + pad, px0 + pw, self.w))
        y1 = int(min(pts[:, 1].max() + pad, py0 + ph, self.h))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return

        # bristle streaks along the stroke
        tang = np.gradient(pts, axis=0)
        nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
        nrm /= (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9)
        mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
        nb = max(3, int(width / 1.5))
        thick = 2 if width > 9 else 1
        for o in np.linspace(-width / 2, width / 2, nb):
            if self.rng.random() < 0.08:
                continue  # gap between bristles
            bp = (pts + nrm * (o + self.rng.normal(0, 0.25))) - np.array([x0, y0], np.float32)
            cv2.polylines(mask, [bp.astype(np.int32).reshape(-1, 1, 2)], False,
                          int(self.rng.uniform(120, 255)), thick, cv2.LINE_AA)
        m = cv2.GaussianBlur(mask, (3, 3), 0).astype(np.float32) / 255.0

        tooth = self.tooth[y0:y1, x0:x1]
        grain = np.clip((tooth + pressure - 0.72) * 3.2, 0, 1)      # pigment skips paper valleys
        pm = pmask[y0 - py0:y1 - py0, x0 - px0:x1 - px0]
        a = np.clip(m * grain * pm * 0.94, 0, 1)
        if a.max() <= 0.01:
            return

        col = np.array(color, np.float32)[None, None, :] * (0.86 + 0.26 * m[..., None])
        roi = self.canvas[y0:y1, x0:x1]
        roi[:] = roi * (1 - a[..., None]) + col * a[..., None]

        hroi = self.height[y0:y1, x0:x1]
        hroi[:] = hroi * (1 - a) + (0.5 + 0.5 * m) * a
        croi = self.cover[y0:y1, x0:x1]
        np.maximum(croi, a, out=croi)

    # ---------------- one patch ---------------- #
    def paint_patch(self, cx, cy, cfg):
        S = self.S
        r = cfg["r"] * S
        sw, sl = max(2.0, cfg["w"] * S), cfg["l"] * S
        src = self.sources[cfg["src"]]
        patch, c = self.blob_mask(r)
        px0, py0 = int(cx) - c, int(cy) - c

        n = int(self.density * cfg["dens"] * math.pi * r * r / (sw * sl * 0.55))
        n = max(5, n)
        shift = self.rng.normal(0, 5, 3)  # each patch has its own slight colour/lightness drift
        step = max(1.5, sw * 0.55)

        for _ in range(n):
            ang = self.rng.uniform(0, 2 * math.pi)
            rad = r * 0.85 * math.sqrt(self.rng.random())
            x = np.clip(cx + rad * math.cos(ang), 0, self.w - 1)
            y = np.clip(cy + rad * math.sin(ang), 0, self.h - 1)
            color = src[int(y), int(x)].astype(np.float32) + shift + self.rng.normal(0, 4, 3)
            color = np.clip(color, 0, 255)
            length = sl * self.rng.uniform(0.7, 1.3)
            width = sw * self.rng.uniform(0.8, 1.2)
            pts = self.trace(x, y, length, step)
            self.paint_stroke(pts, width, color, patch, px0, py0, self.rng.uniform(0.55, 0.95))

    # ---------------- patch scheduling ---------------- #
    def cells(self, cfg):
        cell = cfg["r"] * self.S * 1.1
        nx, ny = max(1, int(math.ceil(self.w / cell))), max(1, int(math.ceil(self.h / cell)))
        out = []
        for j in range(ny):
            for i in range(nx):
                cx = (i + 0.5) * self.w / nx + self.rng.uniform(-0.3, 0.3) * cell
                cy = (j + 0.5) * self.h / ny + self.rng.uniform(-0.3, 0.3) * cell
                out.append((float(np.clip(cx, 0, self.w - 1)), float(np.clip(cy, 0, self.h - 1))))
        order = self.rng.permutation(len(out))      # <- random places, random order
        out = [out[i] for i in order]
        if cfg["edge_only"]:
            e = np.array([self.energy[int(y), int(x)] for x, y in out])
            thr = np.percentile(e, 40)
            out = [p for p, ev in zip(out, e) if ev >= thr]
        return out

    def run(self):
        """Generator: paints one patch per step, yields (pass_name, done, total)."""
        plan = [(cfg, self.cells(cfg)) for cfg in PASSES[:1]]
        total = len(plan[0][1])
        # pre-count approx for the other passes
        approx_rest = sum(len(self.cells(cfg)) for cfg in PASSES[1:])
        total += approx_rest
        done = 0

        for k, cfg in enumerate(PASSES):
            cells = plan[0][1] if k == 0 else self.cells(cfg)
            for cx, cy in cells:
                self.paint_patch(cx, cy, cfg)
                done += 1
                yield cfg["name"], done, total

            if k == 0:
                # make sure no bare-paper holes are left after the first pass
                small = dict(cfg, r=cfg["r"] * 0.6, w=cfg["w"] * 0.8, l=cfg["l"] * 0.8)
                for _ in range(500):
                    holes = (self.cover < 0.30).astype(np.uint8)
                    holes = cv2.erode(holes, np.ones((9, 9), np.uint8))
                    ys, xs = np.nonzero(holes)
                    if len(xs) < 20:
                        break
                    for _ in range(min(12, len(xs))):
                        t = self.rng.integers(len(xs))
                        self.paint_patch(float(xs[t]), float(ys[t]), small)
                        done += 1
                        total = max(total, done)
                        yield cfg["name"] + " (filling gaps)", done, total

    # ---------------- rendering ---------------- #
    def render(self):
        hb = cv2.GaussianBlur(self.height, (0, 0), 1.0)
        gx = cv2.Sobel(hb, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(hb, cv2.CV_32F, 0, 1, ksize=3)
        shade = 1 + np.clip(-(gx + gy) * 0.09, -0.22, 0.22)  # light from top-left -> waxy relief
        painted = np.clip(self.canvas * shade[..., None], 0, 255)

        frame = self.frame_base.copy()
        ox, oy = self.origin
        frame[oy:oy + self.h, ox:ox + self.w] = painted
        # inner edge, like paper lifting off the board
        cv2.rectangle(frame, (ox - 1, oy - 1), (ox + self.w, oy + self.h), (150, 170, 185), 1, cv2.LINE_AA)
        frame = frame * (1 - self.tape_a[..., None]) + self.tape_col * self.tape_a[..., None]
        return np.clip(frame, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
#  Live window (always on)
# --------------------------------------------------------------------------- #
class LiveWindow:
    """Live view of the painting: a Tkinter window (built into Python), with an OpenCV window as backup."""

    def __init__(self, title, frame_shape):
        self.title = title
        self.backend = None
        self.closed = False
        self._keys = []
        fh, fw = frame_shape[:2]
        # 1) Tkinter first: ships with Python on Windows and fails safely if there is no display
        try:
            self._init_tk(fh, fw)
            self.backend = "tk"
            return
        except Exception:
            pass
        # 2) OpenCV's own window (only when a display exists - GUI builds of OpenCV can
        #    abort the whole program on a machine with no display)
        has_display = sys.platform in ("win32", "darwin") or bool(
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if has_display:
            try:
                cv2.namedWindow(title, cv2.WINDOW_NORMAL)
                scale = min(1.0, 880.0 / fh)
                cv2.resizeWindow(title, int(fw * scale), int(fh * scale))
                cv2.imshow(title, np.full((fh, fw, 3), 40, np.uint8))
                cv2.waitKey(1)
                self.backend = "cv2"
            except cv2.error as e:
                print(f"Could not open a window: {e}")

    def _init_tk(self, fh, fw):
        import tkinter as tk
        self._tk = tk
        self.root = tk.Tk()
        self.root.title(self.title)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.scale = min(1.0, (sh - 120) / fh, (sw - 40) / fw)
        self.label = tk.Label(self.root, bg="#282828")
        self.label.pack()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Key>", lambda e: self._keys.append(e.keysym.lower()))
        self.root.update()

    def _on_close(self):
        self.closed = True

    def show(self, frame):
        if self.backend == "cv2":
            cv2.imshow(self.title, frame)
        elif self.backend == "tk":
            import base64
            if self.scale < 1.0:
                frame = cv2.resize(frame, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".png", frame)  # PNG into Tk directly, no Pillow needed
            photo = self._tk.PhotoImage(data=base64.b64encode(buf.tobytes()))
            self.label.configure(image=photo)
            self.label.image = photo

    def poll(self, wait_ms=1):
        """Process window events. Returns 'space', 'q', 'escape', 's' or None."""
        if self.backend == "cv2":
            k = cv2.waitKey(max(1, wait_ms)) & 0xFF
            try:
                if cv2.getWindowProperty(self.title, cv2.WND_PROP_VISIBLE) < 1:
                    self.closed = True
            except cv2.error:
                self.closed = True
            return {27: "escape", 32: "space", ord("q"): "q", ord("s"): "s"}.get(k)
        if self.backend == "tk":
            try:
                self.root.update()
            except self._tk.TclError:
                self.closed = True
                return None
            if wait_ms > 1:
                time.sleep(wait_ms / 1000.0)
            return self._keys.pop(0) if self._keys else None
        return None

    def wait_until_closed(self):
        print("Done - press Q / Esc in the window (or close it) to exit.")
        while not self.closed:
            if self.poll(50) in ("q", "escape"):
                break

    def close(self):
        if self.backend == "cv2":
            cv2.destroyAllWindows()
        elif self.backend == "tk":
            try:
                self.root.destroy()
            except Exception:
                pass


def with_progress(frame, text):
    """Draw a small status line in the dark table area below the paper (window only)."""
    out = frame.copy()
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    x = max(8, (out.shape[1] - tw) // 2)          # centred, clear of the corner tape
    cv2.putText(out, text, (x, out.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (200, 205, 210), 1, cv2.LINE_AA)
    return out


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Paint an image as oil pastel, patch by patch at random places.")
    ap.add_argument("image")
    ap.add_argument("-o", "--out", help="final image path (default: <name>_oilpastel.png)")
    ap.add_argument("--size", type=int, default=900, help="longest side of the artwork in px (default 900)")
    ap.add_argument("--speed", type=int, default=3, help="patches painted per displayed frame (default 3)")
    ap.add_argument("--density", type=float, default=1.0, help="stroke density multiplier (default 1.0)")
    ap.add_argument("--seed", type=int, default=None, help="random seed for a repeatable painting")
    ap.add_argument("--video", help="save a time-lapse mp4 of the painting process")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--no-window", action="store_true", help="headless mode: do NOT open the live window")
    args = ap.parse_args()

    img = load_image(args.image, args.size)
    out_path = args.out or os.path.splitext(args.image)[0] + "_oilpastel.png"

    print("Preparing canvas and colour studies (a few seconds)...")
    painter = OilPastelPainter(img, seed=args.seed, density=args.density)

    win = None
    if not args.no_window:
        win = LiveWindow("Oil Pastel Canvas", painter.frame_base.shape)
        if win.backend is None:
            print("\nNo window could be opened, painting without one.\n"
                  "Tkinter is part of normal Python - on Linux install it with:\n"
                  "  sudo apt install python3-tk\n"
                  "On Windows/Mac, reinstall Python from python.org (tick 'tcl/tk').\n")
            win = None
        else:
            win.show(with_progress(painter.render(), "Blank canvas - starting..."))
            win.poll(1)

    writer = None
    if args.video:
        fh, fw = painter.frame_base.shape[:2]
        writer = cv2.VideoWriter(args.video, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (fw, fh))

    paused, quit_now, last_name = False, False, ""
    count = 0
    for name, done, total in painter.run():
        if name != last_name:
            print(f"\n== {name} ==")
            last_name = name
        count += 1
        if count % args.speed == 0:
            pct = min(100, int(100 * done / max(total, 1)))
            if win or writer:
                frame = painter.render()
                if writer:
                    writer.write(frame)
                if win:
                    win.show(with_progress(frame, f"{name}   {pct}%   [Space pause | S snapshot | Q quit]"))
                    key = win.poll(1)
                    if key == "s":
                        cv2.imwrite(out_path.replace(".png", f"_snap{done}.png"), frame)
                    elif key == "space":
                        paused = True
                    elif key in ("q", "escape"):
                        quit_now = True
                    while paused and not quit_now and not win.closed:
                        key = win.poll(50)
                        if key == "space":
                            paused = False
                        elif key in ("q", "escape"):
                            quit_now = True
                    if win.closed:
                        quit_now = True
            print(f"\r  patches: {done}/{total}  (~{pct}%)", end="", flush=True)
        if quit_now:
            break

    print()
    final = painter.render()
    cv2.imwrite(out_path, final)
    art_only = out_path.replace(".png", "_artwork_only.png")
    ox, oy = painter.origin
    cv2.imwrite(art_only, final[oy:oy + painter.h, ox:ox + painter.w])
    if writer:
        for _ in range(args.fps * 2):
            writer.write(final)
        writer.release()
        print(f"Time-lapse saved: {args.video}")
    print(f"Saved: {out_path}\nSaved: {art_only}")

    if win:
        if not quit_now:
            win.show(final)
            win.wait_until_closed()
        win.close()


if __name__ == "__main__":
    main()