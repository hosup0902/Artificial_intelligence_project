import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from snap import load
from view import views
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
m = env.m
for mat in range(m.nmat):
    if m.mat(mat).name.endswith("_plain") and m.mat(mat).name.startswith(("plastic", "navy")):
        m.mat_rgba[mat, 3] = 0.3
def cb(name): pass
orig = pol.flip_over_bin
done = {}
def stop_at_flip():
    g = orig()
    for _ in g:
        yield
        if "at" in done: break
        pd, Rd = pol.device()
        if Rd[2, 2] < -0.6 and env.d.time > 0:
            done["at"] = env.d.time
pol.run_par(stop_at_flip())
env.step(1.0)
c = env.d.site("remote_comp").xpos
print("cells", [np.round(env.d.body(f"remote_cell{i}").xpos, 3) for i in range(2)], "state", [(round(1000*a,1), round(1000*b,1), round(t,1)) for a, b, t in pol.cell_state()])
views(env, str(HERE / "_out" / "inverted.png"), [(c, 0.15, 0, -10), (c, 0.15, 90, 10), (c, 0.15, 180, 30)])
