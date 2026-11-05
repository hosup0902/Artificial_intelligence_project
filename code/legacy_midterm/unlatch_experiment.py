"""Experiment harness for the unlatch (push-into-spring + pop-up) motion. Not used by the policy."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv, GRIP_CLOSED
from battery_sim.policy import SkillPolicy, DOWN

OFF = np.array([0.0057, 0.0, -0.0025])

def run(retreat="up", seed=0, target=0.0038):
    env = BatteryRemovalEnv(); env.reset(seed); pol = SkillPolicy(env, verbose=False)
    pol.push_to_fence(); pol.slide_cover() or pol.slide_cover(1); pol.push_to_fence()
    d = env.d
    p, R = pol.device(); x = R[:, 0]; z = np.array([0, 0, 1.0])
    plus = d.site("remote_plus").xpos.copy()
    axes = {2: DOWN, 0: -x}
    def shift():
        p_, R_ = pol.device()
        return np.array([(R_.T @ (d.body(f"remote_cell{i}").xpos - p_))[0] for i in range(2)])
    def tilt():
        p_, R_ = pol.device()
        return np.degrees([np.arcsin((R_.T @ d.body(f"remote_cell{i}").xmat.reshape(3, 3)[:, 2])[2]) for i in range(2)])
    s0 = shift(); h = 0.005
    start = plus - x * 0.003 + z * h
    pol.goto(start + z * 0.035, axes, OFF, grip=GRIP_CLOSED)
    pol.move(start, axes, OFF, speed=0.02, settle=0.1)
    k = 0
    while k < 30:
        k += 1
        pol.move(plus + x * (-0.003 + 0.0005 * k) + z * h, axes, OFF, speed=0.005, settle=0.05)
        if (shift() - s0).min() > target:
            break
    print(f"[{retreat}] pushed {(-3+0.5*k):.1f} mm -> shift {np.round((shift()-s0)*1000,1)} tilt {np.round(tilt(),1)} latched {pol.cells_latched()}")
    tip = pol.tool(OFF)[0]
    if retreat == "up":
        pol.move(tip + z * 0.03, axes, OFF, speed=0.02, settle=0.5)
    elif retreat == "up_slow":
        pol.move(tip + z * 0.03, axes, OFF, speed=0.004, settle=0.5)
    elif retreat == "back":
        pol.move(tip - x * 0.008, axes, OFF, speed=0.01, settle=0.3)
        pol.move(pol.tool(OFF)[0] + z * 0.03, axes, OFF, speed=0.02, settle=0.5)
    print(f"      after retreat: shift {np.round((shift()-s0)*1000,1)} tilt(+ end up>0) {np.round(tilt(),1)} latched {pol.cells_latched()}")
    return env, pol

if __name__ == "__main__":
    for r in ("up", "up_slow", "back"):
        run(r)
