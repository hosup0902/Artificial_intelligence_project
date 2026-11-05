"""Run one seed with video and save a contact-sheet montage of frames (for debugging)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv  # noqa: E402
from battery_sim.policy import SkillPolicy  # noqa: E402

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
cam = sys.argv[2] if len(sys.argv) > 2 else "closeup"
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
env = BatteryRemovalEnv(device=(sys.argv[5] if len(sys.argv) > 5 else "tv_remote"), video=True, video_cam=cam, video_every=0.04, size=(360, 640))
env.reset(seed)
SkillPolicy(env).run()
fr = env.frames
times = np.arange(len(fr)) * 0.04
idx = [i for i in range(len(fr)) if t0 <= times[i] <= t1]
pick = np.linspace(idx[0], idx[-1], 12).astype(int)
tiles = []
for i in pick:
    im = Image.fromarray(fr[i])
    ImageDraw.Draw(im).text((8, 8), f"t={times[i]:.2f}s", fill=(255, 255, 0))
    tiles.append(im)
W, H = tiles[0].size
sheet = Image.new("RGB", (W * 4, H * 3))
for k, im in enumerate(tiles):
    sheet.paste(im, ((k % 4) * W, (k // 4) * H))
out = Path(__file__).resolve().parent / "renders" / f"debug_s{seed}_{cam}.png"
sheet.save(out)
print(out)
