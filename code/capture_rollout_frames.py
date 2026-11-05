"""Re-run one seed and save high-res stills from chosen cameras at chosen sim times (for slides/report)."""
import sys
from pathlib import Path
import mujoco
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
SHOTS = [(t, "closeup") for t in (9.0, 11.0)] +         [(round(40.0 + 0.5 * k, 1), cam) for k in range(18) for cam in ("slotcam", "closeup")] +         [(round(58.0 + 0.5 * k, 1), "bincam") for k in range(14)] + [(66.0, "top")] +         [(t, cam) for t in (70.0, 71.0, 72.0) for cam in ("hero",)]
out = Path(__file__).resolve().parent / "renders" / f"rollout_latch_s{seed}"
out.mkdir(parents=True, exist_ok=True)
env = BatteryRemovalEnv()
r = mujoco.Renderer(env.m, 720, 1280)
pending = sorted(SHOTS)
orig_step = env.step
def step(seconds):
    m, d = env.m, env.d
    for _ in range(max(1, int(round(seconds / m.opt.timestep)))):
        orig_step(m.opt.timestep)
        while pending and d.time >= pending[0][0]:
            t, cam = pending.pop(0)
            r.update_scene(d, camera=cam)
            Image.fromarray(r.render()).save(out / f"t{t:05.1f}_{cam}.png")
env.step = step
env.reset(seed)
rep = SkillPolicy(env, verbose=False).run()
print("success", rep.success, "->", out)
