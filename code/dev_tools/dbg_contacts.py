"""Full-run pry with contact listing at each phase: python dev_tools/dbg_contacts.py <dev> <seed> [max_phase]"""
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np, mujoco
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy, R_LEAN
env = BatteryRemovalEnv(device=sys.argv[1]); env.reset(int(sys.argv[2]))
mx = int(sys.argv[3]) if len(sys.argv) > 3 else 99
pol = SkillPolicy(env, verbose=False)
pol.run_par(pol._main_prep(), pol._tool_prep()); pol.run_par(pol.tool_standby())
pol.run_par(pol.grasp_device(lift=False, gx=pol.dm["hold_x"], lean=R_LEAN))
m, d = env.m, env.d
dev_b = {m.body(b).id for b in ("remote_body", "remote_cover", "remote_cell0", "remote_cell1")}
cnt = [0]
def cb(name):
    cnt[0] += 1
    if cnt[0] > mx: return
    p, R = pol.device()
    st = [(round(1000*a,1), round(1000*b,1), round(t,1)) for a, b, t in pol.cell_state()]
    print(f"{cnt[0]:02d} {name} t={d.time:.2f} dev_z={1000*p[2]:.1f} cells {st}")
    f6 = np.zeros(6)
    for i in range(d.ncon):
        c = d.contact[i]; b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
        rob = (b1 in env.robot_bodies, b2 in env.robot_bodies)
        if (rob[0] and b2 in dev_b) or (rob[1] and b1 in dev_b) or ({b1, b2} <= dev_b and b1 != b2):
            mujoco.mj_contactForce(m, d, i, f6)
            if abs(f6[0]) < 0.05: continue
            n = R.T @ c.frame[:3]; pos = 1000 * (R.T @ (c.pos - p))
            g1 = m.geom(c.geom1).name or m.body(b1).name; g2 = m.geom(c.geom2).name or m.body(b2).name
            print(f"     {g1:>22s} | {g2:<22s} f={f6[0]:6.2f} n(dev)={np.round(n,2)} at {np.round(pos,1)}")
pol.on_phase = cb
pol.run_par(pol.pry_cells(0))
