import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np, mujoco
from snap import load
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
m, d = env.m, env.d
orig = env.step
last = [0.0]
def step(sec):
    orig(sec)
    for i in range(2):
        b = m.body(f"remote_cell{i}").id
        v = np.linalg.norm(d.cvel[b][3:]) if False else np.linalg.norm(d.qvel[m.jnt_dofadr[m.body_jntadr[b]]:][:3])
        if v > 0.4 and d.time - last[0] > 0.05:
            last[0] = d.time
            cons = []
            for k in range(d.ncon):
                c = d.contact[k]; b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
                if b in (b1, b2):
                    cons.append(m.geom(c.geom1 if b2 == b else c.geom2).name or m.body(b1 if b2 == b else b2).name)
            print(f"t={d.time:.2f} cell{i} v={v:.2f} m/s pos {np.round(d.body(b).xpos,3)} spring {1000*d.qpos[m.joint(f'remote_spring{i}').qposadr[0]]:.1f}mm contacts {cons[:6]}")
env.step = step
pol.verbose = True
pol.run_par(pol.flip_over_bin())
