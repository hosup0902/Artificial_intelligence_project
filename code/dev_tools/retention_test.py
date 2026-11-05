import sys; sys.path.insert(0, '.')
import numpy as np, mujoco
from battery_sim.env import BatteryRemovalEnv
dev = sys.argv[1]
env = BatteryRemovalEnv(device=dev, randomize=False); env.reset(0)
m, d = env.m, env.d
d.eq_active[env.latch] = 0
a = m.joint("remote_cover_free").qposadr[0]; d.qpos[a:a+3] = [0.6, 0.6, 0.02]
for k in ("R", "L"):
    env.set_ctrl(np.radians([90 if k == "R" else -90, -100, 40, 80, 0]), 0.0, arm=k)
mujoco.mj_forward(m, d); env.step(0.5)
bid = m.body("remote_body").id
c0 = [d.body(f"remote_cell{i}").xpos.copy() for i in range(2)]
for k in range(300):          # device pinned by an applied force, gravity reversed (= upside down) and shaken
    d.xfrc_applied[bid, :3] = [0, 0, -(0.075 + 0.05) * 9.81 * 4]
    m.opt.gravity[:] = [3.0 * np.sin(k * 0.9), 2.0 * np.cos(k * 0.7), 9.81 * (1 + 2.0 * np.sin(k * 0.6))]
    env.step(0.01)
moved = [round(1000 * np.linalg.norm(d.body(f"remote_cell{i}").xpos - c0[i]), 1) for i in range(2)]
print(f"RETENTION {dev}: cell displacement mm {moved} ->", "retained" if max(moved) < 30 else "FELL OUT")
