"""Instrumented flip planning on a pre-flip snapshot: python dev_tools/dbg_flip.py <dev> <seed>"""
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from snap import load
from battery_sim.scene import BATTERY_BIN
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=True, stage="preflip")
A = pol.R
p_tcp, R_tcp = A.tool((0, 0, 0))
pd, Rd = pol.device()
comp = env.d.site("remote_comp").xpos.copy()
corners = np.array([[sx * pol.L_ / 2, sy * pol.W / 2, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, pol.T)])
rel = (R_tcp.T @ (pd - p_tcp), R_tcp.T @ Rd, R_tcp.T @ (comp - p_tcp), corners)
print("device z", round(pd[2], 3), "grasp rel (dev in tcp) mm", np.round(1000 * rel[0], 1), "comp rel", np.round(1000 * rel[2], 1))
prel, Rrel, comp_off, corners = rel
ik = A.ik
bc = np.array(BATTERY_BIN["center"][:2]); top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
rng = np.random.default_rng(0)
cands = []; n_inv = n_clear = 0
for _ in range(60000):
    q = rng.uniform(ik.lo, ik.hi); q[4] = rng.uniform(-0.15, 0.15)
    _, Rd_, cw, cp = pol._dev_geom(q, rel)
    if Rd_[2, 2] > -0.5: continue
    n_inv += 1
    if cw[:, 2].min() < top + 0.035 or cp[2] > top + 0.30: continue
    n_clear += 1
    dd = np.linalg.norm(cp[:2] - bc)
    if dd < 0.04: cands.append((dd, q))
cands.sort(key=lambda c: c[0])
print(f"inverted {n_inv}, clear of rim {n_clear}, pocket within 40 mm of bin centre {len(cands)}")
stats = dict(collide=0, roll=0, transit=0, ok=0)
for dd, q in cands[:80]:
    if pol.arm_collides(q): stats["collide"] += 1; continue
    path = pol._roll_path(q, rel)
    if path is None: stats["roll"] += 1; continue
    if pol._transit_route(A.qcmd.copy(), path[0], rel) is None: stats["transit"] += 1; continue
    stats["ok"] += 1
print(stats)
