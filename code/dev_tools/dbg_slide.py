import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from view import views
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy
dev, seed = sys.argv[1], int(sys.argv[2])
env = BatteryRemovalEnv(device=dev); env.reset(seed)
pol = SkillPolicy(env)
pol.run_par(pol.push_to_fence())
frames = []
cnt = [0]
def cb(name):
    cnt[0] += 1
    off, dz = pol.cover_offset()
    print(f"   {name}: cover offset {1000*off:.1f} dz {1000*dz:.1f} latch {env.d.eq_active[env.latch]}")
    if cnt[0] % 2 == 0:
        views(env, str(HERE / "_out" / f"slide_{cnt[0]:02d}.png"), [(env.d.body("remote_cover").xpos, 0.2, 200, -30)])
pol.on_phase = cb
pol.run_par(pol.slide_cover())
