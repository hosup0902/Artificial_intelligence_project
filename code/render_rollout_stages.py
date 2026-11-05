"""Render the key moments of one rollout of the final bimanual policy (figures for the report / slides).

  MUJOCO_GL=osmesa python render_rollout_stages.py --device tv_remote --seed 5
  -> renders/final/<device>_s<seed>_<NN>_<moment>_<camera>.png  (+ a contact sheet <device>_s<seed>_sheet.png)

Moments: start, after each evaluation stage (fence, tool picked, cover off, held, cells pried, lifted, flipped,
in crate) and the pry sub-steps (blade inserted, cells pushed past the lips, + ends lifted, cells set on the lips).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv  # noqa: E402
from battery_sim.policy import SkillPolicy  # noqa: E402

OUT = Path(__file__).resolve().parent / "renders" / "final"


def _font(size):
    for f in ("C:/Windows/Fonts/malgunbd.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()
STAGE_CAMS = {
    "start": ("wide", "overview", "hero"),
    "push_to_fence": ("hero",),
    "pick_tool": ("hero", "overview"),
    "slide_cover": ("closeup", "hero"),
    "hold_device": ("closeup", "hero"),
    "pry_cells": ("closeup", "slotcam"),
    "grasp_device": ("hero",),
    "flip_over_bin": ("bincam", "overview"),
    "drop_in_crate": ("overview", "hero"),
}
PHASE_CAMS = {
    "pry_inserted": ("closeup", "slotcam", "side"),
    "pry_pushed": ("closeup", "slotcam", "side"),
    "pry_lifted": ("closeup", "slotcam", "side"),
    "pry_set_down": ("closeup", "slotcam", "side"),
}
LABEL = {
    "start": "1. start", "push_to_fence": "2. R: push to the jig fence", "pick_tool": "3. L: pick the pry tool",
    "slide_cover": "4. R: press + slide the cover off", "hold_device": "5. R: hold the remote",
    "pry_inserted": "6a. L: blade into the pry notch", "pry_pushed": "6b. cells pushed past the lips",
    "pry_lifted": "6c. + ends levered above the lips", "pry_set_down": "6d. cells resting on the lips",
    "pry_cells": "6e. tool withdrawn - cells free", "grasp_device": "7. R: re-grasp and lift",
    "flip_over_bin": "8. R: flip + shake over the battery bin", "drop_in_crate": "9. R: body into the crate",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="tv_remote")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--size", default="720x1280")
    args = ap.parse_args()
    h, w = map(int, args.size.split("x"))
    OUT.mkdir(parents=True, exist_ok=True)
    env = BatteryRemovalEnv(device=args.device)
    env.reset(args.seed)
    pol = SkillPolicy(env, verbose=False)
    ren = mujoco.Renderer(env.m, h, w)
    shots = []

    def shoot(name, cams):
        for cam in cams:
            ren.update_scene(env.d, camera=cam)
            img = Image.fromarray(ren.render())
            fn = OUT / f"{args.device}_s{args.seed}_{len(shots):02d}_{name}_{cam}.png"
            img.save(fn)
            shots.append((name, cam, img))
        print(f"{env.d.time:6.2f}s  {name}")

    shoot("start", STAGE_CAMS["start"])
    seen = set()
    orig = env.step

    def step(sec):
        orig(sec)
        for n, _, ok in env.log.stages:
            if n in STAGE_CAMS and n not in seen and ok:
                seen.add(n)
                shoot(n, STAGE_CAMS[n])

    env.step = step
    pol.on_phase = lambda n: shoot(n, PHASE_CAMS[n]) if n in PHASE_CAMS and n not in seen and not seen.add(n) else None
    rep = pol.run()
    print("success:", rep.success)
    # contact sheet: first camera of each moment
    firsts = []
    for name, cam, img in shots:
        if not firsts or firsts[-1][0] != name:
            firsts.append((name, cam, img))
    cols = 4
    tw, th = 480, 270
    rows = (len(firsts) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 30)), "white")
    dr = ImageDraw.Draw(sheet)
    f = _font(18)
    for i, (name, cam, img) in enumerate(firsts):
        x, y = (i % cols) * tw, (i // cols) * (th + 30)
        sheet.paste(img.resize((tw, th)), (x, y + 30))
        dr.text((x + 6, y + 5), f"{LABEL.get(name, name)}  [{cam}]", fill="black", font=f)
    sheet.save(OUT / f"{args.device}_s{args.seed}_sheet.png")
    print("sheet:", OUT / f"{args.device}_s{args.seed}_sheet.png")


if __name__ == "__main__":
    main()
