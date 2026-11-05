"""Render the four waste-appliance types on the jig: closed (cover latched) and opened (cover removed)."""
import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.devices import DEVICE_ORDER, DEVICES  # noqa: E402
from battery_sim.env import BatteryRemovalEnv  # noqa: E402

OUT = Path(__file__).resolve().parent / "renders"
font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 30)
tiles = []
for dev in DEVICE_ORDER:
    env = BatteryRemovalEnv(device=dev, randomize=False)
    env.reset(0)
    m, d = env.m, env.d
    # park the arm out of view
    env.set_ctrl(np.radians([60, -100, 40, 80, 0]), 0.0)
    env.step(1.0)
    r = mujoco.Renderer(m, 540, 720)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = d.body("remote_body").xpos + [0.0, 0, 0.01]
    cam.distance, cam.azimuth, cam.elevation = 0.30, 215, -48
    imgs = []
    r.update_scene(d, cam)
    imgs.append(r.render().copy())
    d.eq_active[env.latch] = 0
    a = m.joint("remote_cover_free").qposadr[0]
    d.qpos[a:a + 3] = [0.6, 0.6, 0.02]
    mujoco.mj_forward(m, d)
    cam.lookat[:] = d.site("remote_comp").xpos
    cam.distance = 0.17
    r.update_scene(d, cam)
    imgs.append(r.render().copy())
    spec = DEVICES[dev]
    lab = f"{spec.label}  {spec.length*1000:.0f}x{spec.width*1000:.0f}x{spec.thick*1000:.0f} mm, {spec.cell.name} x2"
    for k, im in enumerate(imgs):
        pi = Image.fromarray(im)
        dr = ImageDraw.Draw(pi)
        if k == 0:
            dr.rectangle([0, 0, 720, 46], fill=(0, 0, 0))
            dr.text((12, 6), lab, font=font, fill=(255, 220, 60))
        tiles.append(pi)
    r.close()
W, H = 720, 540
sheet = Image.new("RGB", (W * 4, H * 2))
for i in range(4):
    sheet.paste(tiles[2 * i], (i * W, 0))
    sheet.paste(tiles[2 * i + 1], (i * W, H))
sheet.save(OUT / "devices_lineup.png")
print(OUT / "devices_lineup.png")
