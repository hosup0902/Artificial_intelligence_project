import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np, mujoco
from snap import load
from view import views
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=True)
for k in range(3):
    if pol.run_par(pol.pry_cells(attempt=k)): break
def show(tag):
    pd, Rd = pol.device()
    st = [(round(1000*a,1), round(1000*b,1), round(t,1)) for a, b, t in pol.cell_state()]
    print(f"== {tag}: device up {np.round(Rd[:,2],3)} cells {st} free {pol.cells_free()}")
    views(env, str(HERE / "_out" / f"rg_{tag}.png"), [(pd + Rd @ [0, 0, 0.01], 0.3, 270, -20), (pd, 0.3, 200, -40)])
show("after_pry")
pol.run_par(pol.tool_retreat())
def r_side():
    A = pol.R
    yield from pol.release_device(); show("released")
    ok = yield from pol.grasp_device(); show("lifted")
pol.on_phase = lambda n: show(n) if n == "grasp_closed" else None
pol.run_par(r_side())
m, d = env.m, env.d
pd, Rd = pol.device(); f6 = np.zeros(6)
for i in range(d.ncon):
    c = d.contact[i]; b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
    if m.body("remote_body").id in (b1, b2) and (b1 in env.arm_bodies["R"] or b2 in env.arm_bodies["R"]):
        mujoco.mj_contactForce(m, d, i, f6)
        print(f"  {m.geom(c.geom1).name or '?'} | {m.geom(c.geom2).name or '?'}: {f6[0]:.1f} N at dev {np.round(1000*(Rd.T@(c.pos-pd)),1)} n_dev {np.round(Rd.T@c.frame[:3],2)}")
