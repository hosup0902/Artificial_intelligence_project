import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from view import views
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy
from battery_sim.scene import TOOL_RACK
env = BatteryRemovalEnv(device="tv_remote"); env.reset(0)
pol = SkillPolicy(env, verbose=True)
pol.run_par(pol.pick_tool()); pol.run_par(pol.tool_standby())
cnt = [0]
def cb(name):
    cnt[0] += 1
    pt, Rt = pol.tool_pose()
    print(f"   {name}: tool {np.round(pt, 4)} z-axis {np.round(Rt[:, 2], 2)} tip {np.round(env.d.site('pry_tip').xpos, 4)}")
    c = np.array([*TOOL_RACK["center"], 0.05])
    views(env, str(HERE / "_out" / f"ret_{cnt[0]:02d}_{name}.png"), [(c, 0.2, 180, -10), (c, 0.2, 90, -10)])
pol.on_phase = cb
pol.run_par(pol.return_tool())
