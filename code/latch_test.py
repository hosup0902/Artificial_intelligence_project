"""Physics check of the cell retention latch.

With the cover removed, gravity is reversed (= device held upside down) while the device is
pinned to the tray by an applied force. Latched cells must stay in the pocket; with the lips
disabled (control) they must fall out. Optional shaking adds +-3 g vertical accelerations.
"""
import sys
from pathlib import Path
import mujoco
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv


def trial(remove_lip=False, shake=False, unlatched=False, secs=2.0):
    env = BatteryRemovalEnv(randomize=False)
    env.reset(0)
    m, d = env.m, env.d
    d.eq_active[env.latch] = 0
    a = m.joint("remote_cover_free").qposadr[0]
    d.qpos[a:a + 3] = [0.5, 0.5, 0.05]
    if remove_lip:
        for t in ("L", "R"):
            gid = m.geom(f"remote_lip{t}").id
            m.geom_contype[gid] = m.geom_conaffinity[gid] = 0
    dev = m.body("remote_body").id
    mass = m.body_subtreemass[dev]
    if unlatched:   # emulate the unlatch skill: cells pushed 4 mm into the springs, + ends lifted onto the stop
        for i in range(2):
            ja = m.joint(f"remote_cell{i}_free").qposadr[0]
            R = d.body("remote_body").xmat.reshape(3, 3)
            d.qpos[ja:ja + 3] += R @ [0.004, 0, 0.0]
        for _ in range(50):
            for i in range(2):
                d.xfrc_applied[m.body(f"remote_cell{i}").id, :3] = [0, 0, 0]
            mujoco.mj_step(m, d)
    m.opt.gravity[:] = (0, 0, 9.81)
    for k in range(int(secs / m.opt.timestep)):
        f = -2.0 * mass * 9.81
        if shake:
            f += -3 * 9.81 * mass * np.sign(np.sin(2 * np.pi * 4 * k * m.opt.timestep))
        d.xfrc_applied[dev, :3] = [0, 0, f]
        mujoco.mj_step(m, d)
    out = [np.linalg.norm(d.body(f"remote_cell{i}").xpos - d.site("remote_comp").xpos) for i in range(2)]
    moved = np.linalg.norm(d.body("remote_body").xpos - [0.205, 0.005, 0.0062])
    m.opt.gravity[:] = (0, 0, -9.81)
    return np.round(np.array(out) * 1000, 0), round(moved * 1000, 1)


if __name__ == "__main__":
    print("latched, inverted           : cell-pocket dist mm, device moved mm", trial())
    print("latched, inverted + shaking :", trial(shake=True))
    print("no lip (control), inverted  :", trial(remove_lip=True))
