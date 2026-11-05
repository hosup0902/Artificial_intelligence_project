"""Full-run pry trace (deterministic, unlike snapshots): python dev_tools/dbg_pry_full.py <dev> <seed>"""
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from view import views
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy, R_LEAN
env = BatteryRemovalEnv(device=sys.argv[1]); env.reset(int(sys.argv[2]))
pol = SkillPolicy(env, verbose=False)
pol.run_par(pol._main_prep(), pol._tool_prep()); pol.run_par(pol.tool_standby())
pol.run_par(pol.grasp_device(lift=False, gx=pol.dm["hold_x"], lean=R_LEAN))
m = env.m
for mat in range(m.nmat):
    if m.mat(mat).name.endswith("_plain") and m.mat(mat).name.startswith(("plastic", "navy")): m.mat_rgba[mat, 3] = 0.3
cnt = [0]
def cb(name):
    cnt[0] += 1
    st = [(round(1000*a,1), round(1000*b,1), round(t,1)) for a, b, t in pol.cell_state()]
    tp = env.d.site("pry_tip").xpos; p, R = pol.device()
    print(f"{cnt[0]:02d} {name}: t={env.d.time:.2f} cells {st} tip(dev) {np.round(1000*(R.T@(tp-p)) - [1000*pol.dm['cx0'],0,0],1)}")
    if name not in ("pry_lift_step",) or 12 <= cnt[0] <= 15:
        pl = env.d.site("remote_plus").xpos
        views(env, str(HERE / "_out" / f"pf_{cnt[0]:02d}_{name}.png"), [(pl + [0.01, 0, 0.004], 0.08, 90, -10), (pl + [0.01, 0, 0.004], 0.08, 270, -10), (pl, 0.1, 200, -40)])
pol.on_phase = cb
pol.run_par(pol.pry_cells(0))
