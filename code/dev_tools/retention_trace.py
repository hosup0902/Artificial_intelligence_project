import sys; sys.path.insert(0, '.')
import numpy as np, mujoco
from battery_sim.env import BatteryRemovalEnv
dev = sys.argv[1]
env = BatteryRemovalEnv(device=dev, randomize=False); env.reset(0)
m, d = env.m, env.d
d.eq_active[env.latch] = 0
a = m.joint("remote_cover_free").qposadr[0]; d.qpos[a:a+3] = [0.6, 0.6, 0.02]
mujoco.mj_forward(m, d); env.step(0.5)
bid = m.body("remote_body").id
p0, R0 = env.body_pose("remote_body")
for k in range(300):
    d.xfrc_applied[bid, :3] = [0, 0, -(0.075 + 0.05) * 9.81 * 4]
    m.opt.gravity[:] = [3.0 * np.sin(k * 0.9), 2.0 * np.cos(k * 0.7), 9.81 * (1 + 2.0 * np.sin(k * 0.6))]
    env.step(0.01)
    if k % 10 == 0:
        p, R = env.body_pose("remote_body")
        out = []
        for i in range(2):
            pc, Rc = env.body_pose(f"remote_cell{i}")
            l = R.T @ (pc - p); ax = R.T @ Rc[:, 2]
            out.append((np.round(1000 * l, 1), np.round(ax, 2)))
        print(k, "dev z", round(1000 * p[2], 1), out)
