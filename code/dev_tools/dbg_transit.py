import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from snap import load
from battery_sim.scene import BATTERY_BIN
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
A = pol.R; ik = A.ik
p_tcp, R_tcp = A.tool((0, 0, 0)); pd, Rd = pol.device(); comp = env.d.site("remote_comp").xpos.copy()
corners = np.array([[sx * pol.L_ / 2, sy * pol.W / 2, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, pol.T)])
rel = (R_tcp.T @ (pd - p_tcp), R_tcp.T @ Rd, R_tcp.T @ (comp - p_tcp), corners)
bc = np.array(BATTERY_BIN["center"][:2]); top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
half = BATTERY_BIN["size"][0] / 2 - 0.025
def why(q0, q1, n=25):
    for t in np.linspace(0, 1, n):
        q = q0 + (q1 - q0) * t
        _, Rd_, cw_, cp = pol._dev_geom(q, rel)
        ob = np.all(np.abs(cp[:2] - bc) < half)
        if (Rd_[2, 2] < pol.upright_min - 0.05) if ob else not pol.cells_safe(Rd_): return f"tilt t={t:.2f} up={Rd_[2,2]:.2f} over_bin={ob} comp={np.round(cp,3)}"
        if not pol._clear_of_obstacles(cw_): return f"obstacle t={t:.2f} minz={cw_[:,2].min():.3f}"
        if pol.arm_collides(q): return f"collide t={t:.2f}"
    return "ok"
q0 = A.qcmd.copy()
_, R0 = ik.fk(q0)
print("lift pose device up z", round(pol._dev_geom(q0, rel)[1][2, 2], 3), "comp", np.round(pol._dev_geom(q0, rel)[3], 3))
for h in (0.06, 0.09, 0.12):
    qc, err, rerr = ik.solve(q0, [bc[0], bc[1], top + h], {2: R0[:, 2]}, rel[2], iters=300)
    print(f"carry h={h}: ik err {1000*err:.1f} rot {rerr:.3f}; q0->qc: {why(q0, qc)}; up at qc {pol._dev_geom(qc, rel)[1][2,2]:.2f}")
# full planner diagnostics: why do candidate flip poses fail?
rng = np.random.default_rng(0); cands = []
from battery_sim.policy import DROP_LEAD
for _ in range(120000):
    q = rng.uniform(ik.lo, ik.hi); q[4] = rng.uniform(-0.15, 0.15)
    _, Rd_, cw, cp = pol._dev_geom(q, rel)
    if Rd_[2, 2] > -0.64 or cw[:, 2].min() < top + 0.035 or cp[2] > top + 0.30: continue
    uh = Rd_[:2, 2] / max(np.linalg.norm(Rd_[:2, 2]), 1e-6)
    dd = np.linalg.norm(cp[:2] + DROP_LEAD * uh - bc)
    if dd < 0.045 and np.linalg.norm(cp[:2] - bc) < 0.05: cands.append((dd + (cp[2] - top), q))
cands.sort(key=lambda c: c[0])
st = dict(collide=0, roll=0, transit=0, ok=0); reasons = {}
for dd, q in cands[:60]:
    if pol.arm_collides(q): st["collide"] += 1; continue
    path = pol._roll_path(q, rel)
    if path is None: st["roll"] += 1; continue
    r = pol._transit_route(A.qcmd.copy(), path[0], rel)
    if r is None:
        st["transit"] += 1
        w = why(A.qcmd.copy(), path[0]); reasons[w.split()[0]] = reasons.get(w.split()[0], 0) + 1
        if st["transit"] <= 3: print("  direct route:", w, "| q_up up", round(pol._dev_geom(path[0], rel)[1][2, 2], 2))
        continue
    st["ok"] += 1
print(len(cands), st, reasons)
