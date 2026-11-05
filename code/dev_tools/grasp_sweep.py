import sys; sys.path.insert(0, '.')
import numpy as np
from battery_sim.env import BatteryRemovalEnv, GRIP_OPEN, GRIP_CLOSED
from battery_sim.policy import SkillPolicy, DOWN
from battery_sim.scene import TOOL_RACK
env = BatteryRemovalEnv(device="tv_remote")
def tilt():
    z = env.d.body("pry_tool").xmat.reshape(3, 3)[:, 2]
    return np.round(np.degrees(np.arcsin(z[:2])), 1)
for dz in (0.005, 0.015, 0.025):
    for clr in (0.0, 0.002, 0.004):
        for sgn in (1, -1):
            env.reset(0); pol = SkillPolicy(env, verbose=False); A = pol.L
            pt, Rt = pol.tool_pose(); hx = Rt[:, 0]
            gz = TOOL_RACK["plate_z"] + dz
            off = np.array([0.0205 - 0.0055 - clr, 0, 0]); axes = {2: DOWN, 0: -sgn * hx}
            c = pt[:2]
            pol.run_par(A.goto([c[0], c[1] + 0.06, gz + 0.004], axes, off, grip=GRIP_OPEN, dur=1.5))
            pol.run_par(A.move([c[0], c[1], gz], axes, off, speed=0.03, settle=0.1))
            t0 = tilt()
            # fast compliant close
            g = env.d.qpos[A.io.gq]
            while g > GRIP_CLOSED:
                g -= 0.01; A.grip_cmd = g; A.set(A.qcmd, g); env.step(0.02)
                if env.grip_force("L", "pry_tool") > 20: break
            env.step(0.3); t1 = tilt(); gq = g
            pol.run_par(A.move([c[0], c[1], gz + 0.004], axes, off, speed=0.02, settle=0.1))
            pol.run_par(A.move([c[0] - 0.045, c[1], gz + 0.004], axes, off, speed=0.04, settle=0.3))
            print(f"dz {dz} clr {clr} sgn {sgn}: tilt before {t0} closed {t1} (jaw {gq:.2f}) carried {tilt()} squeeze {env.grip_force('L','pry_tool'):.0f}N x {env.d.body('pry_tool').xpos[0]:.3f}")
