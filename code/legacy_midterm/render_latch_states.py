"""Close renders of the battery latch: latched (cover removed) vs. after the unlatch skill (seed 0)."""
import sys
from pathlib import Path
import mujoco
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy

OUT = Path(__file__).resolve().parent / "renders"
env = BatteryRemovalEnv(); env.reset(0)
pol = SkillPolicy(env, verbose=False)
r = mujoco.Renderer(env.m, 720, 960)

def shot(tag, az, el, dist):
    cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    p, R = pol.device()
    cam.lookat[:] = env.d.site("remote_plus").xpos + R[:, 0] * 0.012 + [0, 0, 0.004]
    cam.distance, cam.azimuth, cam.elevation = dist, az, el
    r.update_scene(env.d, cam)
    Image.fromarray(r.render()).save(OUT / f"latch_{tag}.png")

pol.push_to_fence(); pol.slide_cover() or pol.slide_cover(1); pol.push_to_fence(name="reseat_on_fence")
pol.goto(pol.tool((0, 0, 0))[0] + [0, 0, 0.08], {2: (0, 0, -1)}, (0, 0, 0), dur=1.0)
for az in (240, 300):
    shot(f"before_az{az}", az, -28, 0.10)
ok = pol.unlatch_cells() or pol.unlatch_cells(attempt=1)
pol.goto(pol.tool((0, 0, 0))[0] + [0, 0, 0.08], {2: (0, 0, -1)}, (0, 0, 0), dur=1.0)
for az in (240, 300):
    shot(f"after_az{az}", az, -28, 0.10)
print("unlatched:", ok, pol._cell_state())
