"""Procedural textures for the e-waste battery-removal workstation scene.

Every texture is generated from a fixed seed so the scene is reproducible.
The look is modelled on a Korean small-appliance (소형 폐가전) dismantling line:
green epoxy factory floor, white sandwich-panel walls, steel workbench with an
ESD mat, perforated steel tool board, safety posters, and battery collection bins.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path("C:/Windows/Fonts")
FONT_KR = str(FONT_DIR / "malgun.ttf")
FONT_KR_BOLD = str(FONT_DIR / "malgunbd.ttf")
FONT_MONO = str(FONT_DIR / "consola.ttf")


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _noise(rng: np.random.Generator, size: int, octaves=(4, 16, 64, 256), weights=None) -> np.ndarray:
    """Multi-octave value noise in [0, 1], shape (size, size)."""
    weights = weights or [1.0 / (i + 1) for i in range(len(octaves))]
    acc = np.zeros((size, size), np.float32)
    for o, w in zip(octaves, weights):
        small = rng.random((o, o)).astype(np.float32)
        img = Image.fromarray((small * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        acc += w * np.asarray(img, np.float32) / 255.0
    acc -= acc.min()
    return acc / max(acc.max(), 1e-6)


def _save(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path)


def _tint(base_rgb, n: np.ndarray, amp: float) -> np.ndarray:
    base = np.array(base_rgb, np.float32)[None, None, :]
    return base * (1.0 + amp * (n[..., None] - 0.5))


# ---------------------------------------------------------------------------
# Building surfaces
# ---------------------------------------------------------------------------

def floor_epoxy(out: Path, rng) -> None:
    """Worn green epoxy floor typical of Korean factories, with scuffs."""
    s = 1024
    n = _noise(rng, s)
    img = _tint((74, 122, 92), n, 0.25)
    # tyre / cart scuff streaks
    sc = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(sc)
    for _ in range(40):
        x0, y0 = rng.integers(0, s, 2)
        L = rng.integers(80, 400)
        ang = rng.uniform(-0.3, 0.3)
        d.line([(x0, y0), (x0 + L * np.cos(ang), y0 + L * np.sin(ang))], fill=int(rng.integers(30, 90)),
               width=int(rng.integers(2, 10)))
    for _ in range(25):  # worn patches
        x, y = rng.integers(0, s, 2)
        r = rng.integers(20, 90)
        d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=int(rng.integers(20, 60)))
    sc = np.asarray(sc.filter(ImageFilter.GaussianBlur(4)), np.float32) / 255.0
    grey = np.array([120, 125, 118], np.float32)
    img = img * (1 - sc[..., None]) + grey * sc[..., None]
    # specular-ish sparkle
    img += (rng.random((s, s, 1)) - 0.5) * 10
    _save(img, out)


def wall_sandwich_panel(out: Path, rng) -> None:
    """Off-white corrugated sandwich panel (샌드위치 패널) with vertical ribs."""
    w, h = 1024, 1024
    n = _noise(rng, w, octaves=(4, 32, 128))
    img = _tint((226, 226, 220), n, 0.06)
    x = np.arange(w)
    rib = 0.5 + 0.5 * np.cos(2 * np.pi * x / 64.0)  # 8 ribs across one texture tile
    shade = 1.0 - 0.07 * rib[None, :, None]
    img = img * shade
    # panel seam every texture width
    img[:, :3] *= 0.75
    # faint dirt toward the bottom
    grad = np.linspace(0, 1, h)[:, None, None] ** 4
    img = img * (1 - 0.12 * grad * n[..., None])
    _save(img, out)


def ceiling_panel(out: Path, rng) -> None:
    s = 512
    n = _noise(rng, s, octaves=(8, 64))
    img = _tint((200, 202, 205), n, 0.05)
    img[::128, :] *= 0.7
    img[:, ::128] *= 0.7
    _save(img, out)


def hazard_stripe(out: Path, rng) -> None:
    w, h = 1024, 64
    img = Image.new("RGB", (w, h), (235, 190, 20))
    d = ImageDraw.Draw(img)
    for x in range(-h, w + h, 64):
        d.polygon([(x, h), (x + 32, h), (x + 32 + h, 0), (x + h, 0)], fill=(25, 25, 25))
    arr = np.asarray(img, np.float32)
    arr *= (0.85 + 0.3 * _noise(rng, 1024, octaves=(8, 64))[:h, :, None])
    _save(arr, out)


# ---------------------------------------------------------------------------
# Workbench
# ---------------------------------------------------------------------------

def esd_mat(out: Path, rng) -> None:
    """Grey-blue anti-static rubber mat with fine texture and scratches."""
    s = 1024
    n = _noise(rng, s, octaves=(8, 64, 256, 512))
    img = _tint((70, 92, 108), n, 0.18)
    sc = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(sc)
    for _ in range(120):
        x0, y0 = rng.integers(0, s, 2)
        L = rng.integers(10, 90)
        a = rng.uniform(0, np.pi)
        d.line([(x0, y0), (x0 + L * np.cos(a), y0 + L * np.sin(a))], fill=int(rng.integers(40, 120)), width=1)
    sc = np.asarray(sc, np.float32)[..., None] / 255.0
    img = img * (1 - 0.35 * sc) + 160 * 0.35 * sc
    _save(img, out)


def brushed_steel(out: Path, rng, base=(150, 156, 160)) -> None:
    s = 512
    streak = rng.random((s, 1)).astype(np.float32)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize((s, s), Image.BILINEAR), np.float32) / 255
    streak = np.repeat(rng.random((s, 1)), s, axis=1) * 0.5 + 0.5 * _noise(rng, s, octaves=(4, 16))
    img = _tint(base, streak.astype(np.float32), 0.12)
    _save(img, out)


def painted_steel(out: Path, rng, base=(64, 98, 140)) -> None:
    s = 256
    n = _noise(rng, s, octaves=(4, 32, 128))
    img = _tint(base, n, 0.12)
    _save(img, out)


def pegboard(out: Path, rng) -> None:
    """Perforated grey steel tool board (타공판) with a hole grid."""
    s = 1024
    n = _noise(rng, s, octaves=(4, 32))
    img = Image.fromarray(np.clip(_tint((150, 156, 160), n, 0.08), 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    pitch = 32
    for y in range(pitch // 2, s, pitch):
        for x in range(pitch // 2, s, pitch):
            d.rounded_rectangle([x - 3, y - 7, x + 3, y + 7], radius=3, fill=(30, 32, 34))
    _save(np.asarray(img), out)


# ---------------------------------------------------------------------------
# Signage (Korean)
# ---------------------------------------------------------------------------

def _poster(out: Path, size, bg, header_bg, header, header_fg, lines, line_fg, icon=None, border=None):
    w, h = size
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    hh = int(h * 0.28)
    d.rectangle([0, 0, w, hh], fill=header_bg)
    f = _font(FONT_KR_BOLD, int(hh * 0.42))
    tw = d.textlength(header, font=f)
    d.text(((w - tw) / 2, hh * 0.25), header, font=f, fill=header_fg)
    y = hh + h * 0.06
    for txt, scale, bold in lines:
        fnt = _font(FONT_KR_BOLD if bold else FONT_KR, int(h * scale))
        tw = d.textlength(txt, font=fnt)
        d.text(((w - tw) / 2, y), txt, font=fnt, fill=line_fg)
        y += h * scale * 1.45
    if border:
        d.rectangle([4, 4, w - 5, h - 5], outline=border, width=10)
    arr = np.asarray(img, np.float32)
    arr *= 0.93 + 0.07 * _noise(np.random.default_rng(len(header)), max(w, h), octaves=(4, 32))[:h, :w, None]
    _save(arr, out)


def posters(tex: Path) -> None:
    _poster(tex / "poster_zone.png", (1024, 768), (250, 214, 30), (20, 20, 20), "폐건전지 분리 작업 구역",
            (250, 214, 30),
            [("소형 폐가전은 파쇄 전", 0.075, True), ("반드시 건전지를 분리하십시오", 0.075, True),
             ("Battery removal zone", 0.05, False)], (20, 20, 20), border=(20, 20, 20))
    _poster(tex / "poster_fire.png", (768, 1024), (255, 255, 255), (200, 20, 25), "화재 주의",
            (255, 255, 255),
            [("배터리 미분리 시", 0.055, True), ("파쇄·압축 공정에서", 0.055, True), ("화재가 발생합니다", 0.055, True),
             ("", 0.03, False), ("부풀거나 손상된 전지는", 0.042, False), ("즉시 격리함에 보관", 0.042, False)],
            (30, 30, 30), border=(200, 20, 25))
    _poster(tex / "poster_rules.png", (768, 1024), (240, 244, 248), (20, 70, 140), "안전 수칙",
            (255, 255, 255),
            [("1. 보호장갑·보안경 착용", 0.045, True), ("2. 전지 단자 단락 금지", 0.045, True),
             ("3. 전지는 종류별 분리 배출", 0.045, True), ("4. 작업대 정리정돈", 0.045, True),
             ("5. 이상 발생 시 즉시 보고", 0.045, True)], (20, 30, 50))


def bin_labels(tex: Path) -> None:
    # battery collection box: red body with white label panel
    img = Image.new("RGB", (1024, 512), (196, 28, 32))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 70, 964, 442], radius=30, fill=(250, 250, 250))
    f1 = _font(FONT_KR_BOLD, 120)
    f2 = _font(FONT_KR_BOLD, 54)
    t = "폐건전지 수거함"
    d.text(((1024 - d.textlength(t, font=f1)) / 2, 110), t, font=f1, fill=(196, 28, 32))
    t = "USED BATTERIES"
    d.text(((1024 - d.textlength(t, font=f2)) / 2, 300), t, font=f2, fill=(60, 60, 60))
    _save(np.asarray(img), tex / "label_battery_bin.png")
    # appliance body crate label
    img = Image.new("RGB", (1024, 512), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1024, 140], fill=(20, 80, 160))
    f1 = _font(FONT_KR_BOLD, 96)
    t = "소형 폐가전"
    d.text(((1024 - d.textlength(f1 and t, font=f1)) / 2, 18), t, font=f1, fill=(255, 255, 255))
    f2 = _font(FONT_KR_BOLD, 64)
    t = "전지 분리 완료품"
    d.text(((1024 - d.textlength(t, font=f2)) / 2, 220), t, font=f2, fill=(20, 40, 80))
    f3 = _font(FONT_KR, 44)
    t = "Battery-free appliances"
    d.text(((1024 - d.textlength(t, font=f3)) / 2, 340), t, font=f3, fill=(80, 80, 80))
    _save(np.asarray(img), tex / "label_body_bin.png")
    # input tray label
    img = Image.new("RGB", (1024, 256), (250, 250, 250))
    d = ImageDraw.Draw(img)
    f = _font(FONT_KR_BOLD, 110)
    t = "투입 ▶ 분리"
    d.text(((1024 - d.textlength(t, font=f)) / 2, 50), t, font=f, fill=(30, 30, 30))
    _save(np.asarray(img), tex / "label_input.png")


# ---------------------------------------------------------------------------
# Plastics / devices
# ---------------------------------------------------------------------------

def worn_plastic(out: Path, rng, base, amp=0.10, dirt=0.25) -> None:
    s = 512
    n = _noise(rng, s, octaves=(4, 32, 128, 512))
    img = _tint(base, n, amp)
    sc = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(sc)
    for _ in range(60):
        x0, y0 = rng.integers(0, s, 2)
        L = rng.integers(5, 60)
        a = rng.uniform(0, np.pi)
        d.line([(x0, y0), (x0 + L * np.cos(a), y0 + L * np.sin(a))], fill=int(rng.integers(60, 160)), width=1)
    sc = np.asarray(sc, np.float32)[..., None] / 255.0
    img = img * (1 - 0.3 * sc) + 200 * 0.3 * sc
    grime = _noise(rng, s, octaves=(2, 8))[..., None]
    img = img * (1 - dirt * grime * 0.5)
    _save(img, out)


def device_sticker(out: Path, model: str, spec: str) -> None:
    """Rating sticker on the underside of a device (generic, no brand)."""
    w, h = 768, 384
    img = Image.new("RGB", (w, h), (232, 232, 226))
    d = ImageDraw.Draw(img)
    fm = _font(FONT_MONO, 44)
    fk = _font(FONT_KR, 40)
    d.text((30, 24), f"MODEL: {model}", font=fm, fill=(30, 30, 30))
    d.text((30, 84), spec, font=fm, fill=(30, 30, 30))
    d.text((30, 144), "제조국: 대한민국   KC", font=fk, fill=(30, 30, 30))
    rng = np.random.default_rng(abs(hash(model)) % 2**32)
    x = 30
    while x < w - 40:
        bw = int(rng.integers(2, 7))
        d.rectangle([x, 230, x + bw, 350], fill=(20, 20, 20))
        x += bw + int(rng.integers(2, 7))
    arr = np.asarray(img, np.float32) * (0.9 + 0.1 * _noise(rng, w, octaves=(4, 16))[:h, :w, None])
    _save(arr, out)


def battery_wrap(out: Path, body_rgb, cap_rgb, text: str) -> None:
    """Cylindrical label wrap for an AA cell (u around the cell, v along it)."""
    w, h = 512, 256
    img = Image.new("RGB", (w, h), body_rgb)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, int(h * 0.28)], fill=cap_rgb)
    f = _font(FONT_KR_BOLD, 54)
    d.text((40, 110), text, font=f, fill=(250, 250, 250))
    f2 = _font(FONT_MONO, 34)
    d.text((300, 120), "1.5V AA", font=f2, fill=(250, 250, 250))
    _save(np.asarray(img), out)


def keyboard_top(out: Path, rng) -> None:
    w, h = 1024, 384
    img = Image.new("RGB", (w, h), (40, 40, 42))
    d = ImageDraw.Draw(img)
    kw = 60
    for r in range(6):
        y = 14 + r * 62
        off = [0, 20, 30, 45, 60, 0][r]
        x = 14 + off
        while x < w - kw:
            c = int(rng.integers(205, 235))
            d.rounded_rectangle([x, y, x + kw - 8, y + 52], radius=6, fill=(c, c, c - 3))
            x += kw
    arr = np.asarray(img, np.float32) * (0.85 + 0.15 * _noise(rng, w, octaves=(4, 16))[:h, :w, None])
    _save(arr, out)


def remote_top(out: Path, rng, base=(35, 35, 38)) -> None:
    """Button side of a TV remote, used for the remotes heaped in the waste crate."""
    w, h = 256, 768
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    d.ellipse([90, 40, 166, 116], fill=(190, 30, 30))
    for r in range(4):
        for c in range(3):
            x, y = 40 + c * 64, 170 + r * 70
            d.rounded_rectangle([x, y, x + 46, y + 44], radius=10, fill=(120, 120, 125))
    d.ellipse([58, 470, 198, 610], fill=(90, 90, 95))
    d.ellipse([103, 515, 153, 565], fill=(140, 140, 145))
    for r in range(2):
        for c in range(4):
            x, y = 26 + c * 54, 640 + r * 52
            d.rounded_rectangle([x, y, x + 40, y + 36], radius=8, fill=[(200, 40, 40), (40, 160, 60), (220, 200, 40), (40, 90, 200)][c])
    arr = np.asarray(img, np.float32) * (0.85 + 0.15 * _noise(rng, h, octaves=(4, 32))[:h, :w, None])
    _save(arr, out)


def generate_all(tex_dir: Path, seed: int = 7) -> None:
    tex_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    floor_epoxy(tex_dir / "floor_epoxy.png", rng)
    wall_sandwich_panel(tex_dir / "wall_panel.png", rng)
    ceiling_panel(tex_dir / "ceiling.png", rng)
    hazard_stripe(tex_dir / "hazard.png", rng)
    esd_mat(tex_dir / "esd_mat.png", rng)
    brushed_steel(tex_dir / "steel_brushed.png", rng)
    painted_steel(tex_dir / "steel_blue.png", rng, base=(58, 92, 135))
    painted_steel(tex_dir / "steel_grey.png", rng, base=(120, 124, 128))
    pegboard(tex_dir / "pegboard.png", rng)
    posters(tex_dir)
    bin_labels(tex_dir)
    worn_plastic(tex_dir / "plastic_remote.png", rng, (38, 38, 41))
    worn_plastic(tex_dir / "plastic_mouse.png", rng, (52, 54, 58), dirt=0.15)
    worn_plastic(tex_dir / "plastic_clock.png", rng, (226, 222, 210), amp=0.05, dirt=0.35)
    worn_plastic(tex_dir / "plastic_red_bin.png", rng, (196, 28, 32), amp=0.06, dirt=0.1)
    worn_plastic(tex_dir / "plastic_blue_crate.png", rng, (30, 85, 165), amp=0.06, dirt=0.2)
    worn_plastic(tex_dir / "plastic_grey_tray.png", rng, (105, 108, 112), amp=0.06, dirt=0.2)
    device_sticker(tex_dir / "sticker_remote.png", "RC-2041", "DC 3V (1.5V AA x 2)")
    device_sticker(tex_dir / "sticker_mouse.png", "WM-310", "DC 1.5V (AA x 1)")
    device_sticker(tex_dir / "sticker_clock.png", "DC-55", "DC 1.5V (AA x 1)")
    device_sticker(tex_dir / "sticker_stb.png", "STB-700", "DC 3V (1.5V AAA x 2)")
    device_sticker(tex_dir / "sticker_ac.png", "AC-R12", "DC 3V (1.5V AA x 2)")
    device_sticker(tex_dir / "sticker_light.png", "LR-5", "DC 3V (1.5V AAA x 2)")
    battery_wrap(tex_dir / "battery_a.png", (25, 25, 25), (205, 140, 30), "알카라인")
    battery_wrap(tex_dir / "battery_b.png", (30, 60, 150), (220, 220, 225), "알카라인")
    keyboard_top(tex_dir / "keyboard.png", rng)
    remote_top(tex_dir / "remote_top.png", rng)
    remote_top(tex_dir / "remote_top2.png", rng, base=(170, 170, 175))
    # MuJoCo maps a 2D texture mirrored on the -x/+y faces of a box; signage mounted on
    # -x facing surfaces uses a horizontally flipped copy so the text reads correctly.
    for n in ("poster_zone", "poster_fire", "poster_rules", "label_battery_bin", "label_body_bin", "label_input"):
        Image.open(tex_dir / f"{n}.png").transpose(Image.FLIP_LEFT_RIGHT).save(tex_dir / f"{n}_mx.png")


if __name__ == "__main__":
    generate_all(Path(__file__).parent / "mjcf" / "assets" / "tex")
