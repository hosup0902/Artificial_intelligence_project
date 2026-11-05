import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
SP = str(HERE / "_out"); sys.argv.insert(1, SP)   # usage (from code/): python dev_tools/dbg_pry.py <device> <seed>
import numpy as np
from snap import load
from view import views
dev, seed = sys.argv[2], int(sys.argv[3])
env, pol = load(dev, seed)
d = env.d
m = env.m
for mat in range(m.nmat):
    if m.mat(mat).name.endswith("_plain") and m.mat(mat).name.startswith(("plastic", "navy")):
        m.mat_rgba[mat, 3] = 0.25
tiles = []; cnt = [0]
def cb(name):
    pl = d.site("remote_plus").xpos
    st = pol.cell_state()
    tp = d.site("pry_tip").xpos; p, R = pol.device()
    print(f"   {name}: cells {[(round(1000*a,1), round(1000*b,1), round(c,1)) for a,b,c in st]}  tip(dev) {np.round(1000*(R.T@(tp-p)) - [1000*pol.dm['cx0'],0,0],1)}")
    cnt[0] += 1
    if name in ("pry_approach", "pry_above"):
        print("      device", np.round(1000 * d.body("remote_body").xpos, 1))
        views(env, f"{SP}/pry_{cnt[0]:02d}_{name}_wide.png", ["hero", (pl, 0.3, 200, -30), (pl, 0.3, 120, -20)])
    views(env, f"{SP}/pry_{cnt[0]:02d}_{name}.png", [(pl + [0.006, 0, 0.004], 0.06, 90, -3), (pl + [0.006, 0, 0.004], 0.06, 270, -3), (pl + [0.01, 0, 0], 0.07, 180, -60)],
          collision=False)
pol.on_phase = cb
ok = pol.run_par(pol.pry_cells(0))
