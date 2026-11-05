import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from snap import load
from battery_sim.scene import BATTERY_BIN
from battery_sim.policy import _rot
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
A = pol.R; ik = A.ik
p_tcp, R_tcp = A.tool((0, 0, 0)); pd, Rd = pol.device(); comp = env.d.site("remote_comp").xpos.copy()
corners = np.array([[sx * pol.L_ / 2, sy * pol.W / 2, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, pol.T)])
rel = (R_tcp.T @ (pd - p_tcp), R_tcp.T @ Rd, R_tcp.T @ (comp - p_tcp), corners)
prel, Rrel, comp_off, _ = rel
print("Rrel (device axes in TCP frame):\n", np.round(Rrel, 2), "\ncomp_off mm", np.round(1000*comp_off, 1))
bc = np.array(BATTERY_BIN["center"][:2]); top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
rng = np.random.default_rng(0); n = 0
for _ in range(120000):
    q = rng.uniform(ik.lo, ik.hi); q[4] = rng.uniform(-0.15, 0.15)
    _, Rd_, cw, cp = pol._dev_geom(q, rel)
    if Rd_[2, 2] > -0.5 or cw[:, 2].min() < top + 0.035 or cp[2] > top + 0.30 or np.linalg.norm(cp[:2] - bc) > 0.045: continue
    if pol.arm_collides(q): continue
    p, R = ik.fk(q); pocket = p + R @ comp_off; yv = R[:, 1]
    out = []
    for sgn in (1, -1):
        a1 = _rot(R[:, 2], yv, sgn * np.radians(10))
        q1, err, rerr = ik.solve(q, pocket, {2: a1, 1: yv}, comp_off, iters=120)
        out.append((round(1000*err, 1), round(rerr, 3), round(float(np.degrees(np.abs(q1 - q).max())), 1)))
    print("q", np.round(np.degrees(q), 0), "upz", round(Rd_[2, 2], 2), "step1 (+/-):", out)
    n += 1
    if n >= 8: break
