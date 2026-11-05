import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np, mujoco
from battery_sim.env import BatteryRemovalEnv
from view import views
dev = sys.argv[1]
env = BatteryRemovalEnv(device=dev, randomize=False); env.reset(0)
m, d = env.m, env.d
for mat in range(m.nmat):
    if m.mat(mat).name.endswith("_plain") and m.mat(mat).name.startswith(("plastic", "navy")): m.mat_rgba[mat, 3] = 0.3
d.eq_active[env.latch] = 0
a = m.joint("remote_cover_free").qposadr[0]; d.qpos[a:a+3] = [0.6, 0.6, 0.02]
for k in ("R", "L"): env.set_ctrl(np.radians([90 if k == "R" else -90, -100, 40, 80, 0]), 0.0, arm=k)
mujoco.mj_forward(m, d); env.step(0.5)
bid = m.body("remote_body").id
p, R = env.body_pose("remote_body")
for k in range(300):
    d.xfrc_applied[bid, :3] = [0, 0, -(0.075 + 0.05) * 9.81 * 4]
    m.opt.gravity[:] = [3.0 * np.sin(k * 0.9), 2.0 * np.cos(k * 0.7), 9.81 * (1 + 2.0 * np.sin(k * 0.6))]
    env.step(0.01)
    out = []
    for i in range(2):
        pc, Rc = env.body_pose(f"remote_cell{i}"); ax = R.T @ Rc[:, 2]; c = R.T @ (pc - p)
        plus = c - ax * env.dims["cell_len"] / 2; minus = c + ax * env.dims["cell_len"] / 2
        out.append(f"+({1000*(plus[0]-env.dims['cx0']):.1f},{1000*plus[1]:.1f},{1000*plus[2]:.1f}) -({1000*(minus[0]-env.dims['cx0']):.1f},{1000*minus[1]:.1f},{1000*minus[2]:.1f})")
    if k % 10 == 0 or 60 <= k <= 0: print(k, " | ".join(out))
    if k in (999,):
        pl = d.site("remote_plus").xpos
        views(env, str(HERE / "_out" / f"ret_{k:02d}.png"), [(pl + [0.02, 0, 0], 0.12, 90, 10), (pl + [0.02, 0, 0], 0.12, 180, 30)])
