import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from collections import Counter
from snap import load
from battery_sim.scene import BATTERY_BIN
from battery_sim.policy import _rot, DROP_LEAD
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
A = pol.R; ik = A.ik
p_tcp, R_tcp = A.tool((0, 0, 0)); pd, Rd = pol.device(); comp = env.d.site("remote_comp").xpos.copy()
corners = np.array([[sx * pol.L_ / 2, sy * pol.W / 2, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, pol.T)])
rel = (R_tcp.T @ (pd - p_tcp), R_tcp.T @ Rd, R_tcp.T @ (comp - p_tcp), corners)
prel, Rrel, comp_off, _ = rel
bc = np.array(BATTERY_BIN["center"][:2]); top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
hb = BATTERY_BIN["size"][0] / 2 + 0.015; half = BATTERY_BIN["size"][0] / 2 - 0.02
rng = np.random.default_rng(0); cands = []
for _ in range(120000):
    q = rng.uniform(ik.lo, ik.hi); q[4] = rng.uniform(-0.15, 0.15)
    _, Rd_, cw, cp = pol._dev_geom(q, rel)
    if Rd_[2, 2] > pol.FLIP_MIN_UPZ if False else Rd_[2, 2] > -0.5 or cw[:, 2].min() < top + 0.035 or cp[2] > top + 0.30: continue
    uh = Rd_[:2, 2] / max(np.linalg.norm(Rd_[:2, 2]), 1e-6)
    dd = np.linalg.norm(cp[:2] + DROP_LEAD * uh - bc)
    if dd < 0.045 and np.linalg.norm(cp[:2] - bc) < 0.05: cands.append((dd + (cp[2] - top), q))
cands.sort(key=lambda c: c[0])
why = Counter(); best_upz = []
for _, qf in cands[:150]:
    if pol.arm_collides(qf): why["flip pose collides"] += 1; continue
    p, R = ik.fk(qf); pocket = p + R @ comp_off; yv = R[:, 1]
    res = {}
    for sgn in (1, -1):
        q = qf; prev = qf; reason = "steps exhausted"; upz = -1
        for k in range(1, 23):
            a_k = _rot(R[:, 2], yv, sgn * np.radians(10 * k))
            q, err, rerr = ik.solve(q, pocket, {2: a_k, 1: yv}, comp_off, iters=120)
            if err > 0.015 or rerr > 0.08: reason = f"ik {1000*err:.0f}mm"; break
            _, Rd2, cw, cp = pol._dev_geom(q, rel)
            over = np.all(np.abs(cw[:, :2] - bc) < hb, axis=1)
            if np.any(cw[:, 2] < np.where(over, top + 0.030, 0.015)): reason = "corner low"; break
            if Rd2[2, 2] < 0.2 and np.abs(cp[:2] - bc).max() > half: reason = "pocket off bin"; break
            if pol.arm_collides(q): reason = "collide"; break
            if np.abs(q - prev).max() > np.radians(25): reason = "jump"; break
            prev = q; upz = Rd2[2, 2]
            if upz > pol.upright_min: reason = "OK"; break
        res[sgn] = (reason.split()[0], round(upz, 2))
    why[str(sorted(res.values()))] += 1
for k, v in why.most_common(12): print(v, k)
