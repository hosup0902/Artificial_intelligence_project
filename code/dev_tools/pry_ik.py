import sys; sys.path.insert(0, '.')
import numpy as np
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy
from battery_sim.scene import FENCE_X
dev = sys.argv[1] if len(sys.argv) > 1 else "tv_remote"
env = BatteryRemovalEnv(device=dev); env.reset(0)
pol = SkillPolicy(env, verbose=False)
pol.run_par(pol.pick_tool())
dm = pol.dm
p = np.array([FENCE_X - dm["L"] / 2, 0.005, 0.006]); R = np.eye(3)
pol.device = lambda: (p, R)
th = np.radians(float(sys.argv[2])); Rt_des = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0], [-np.sin(th), 0, np.cos(th)]])
axes = pol.tool_axes(Rt_des); off = pol.tool_rel[0]
print("tool_rel tip", np.round(1000 * off, 1), "Rrel z", np.round(pol.tool_rel[1][:, 2], 3))
cx0, cz, T = dm["cx0"], dm["cov_z0"], dm["T"]
pts = {"approach": (cx0 + 0.04, T + 0.012), "above": (cx0 - 0.004, T + 0.002), "low": (cx0 - 0.004, dm["slot_floor"] + 0.0011),
       "pushed": (cx0 + 0.0075, dm["slot_floor"] + 0.0011), "lifted": (cx0 + 0.0055, cz + 0.0012), "back": (cx0 - 0.0095, cz - 0.0035)}
for k, (x, z) in pts.items():
    tgt = p + np.array([x, 0, z])
    for name, ax in (("full", axes), ("z-only", {2: axes[2]})):
        q, e, r = pol.L.solve_best(tgt, ax, off)
        pt_, R_ = pol.L.ik.fk(q, off)
        print(f"{k:9s} {name:6s} tip target {np.round(tgt,3)} err {1000*e:5.1f} mm rot {r:.3f}  q {np.round(np.degrees(q),0)}")
