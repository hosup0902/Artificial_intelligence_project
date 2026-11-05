"""Kinematic-tool test of the compartment: mode = full | push | none, then invert+shake."""
import sys; sys.path.insert(0, '.'); sys.path.insert(0, sys.argv[3])
import numpy as np, mujoco
from battery_sim.env import BatteryRemovalEnv
from battery_sim.scene import FENCE_X
from view import views
dev, mode = sys.argv[1], sys.argv[2]
env = BatteryRemovalEnv(device=dev, randomize=False); env.reset(0)
m, d, dm = env.m, env.d, env.dims
d.eq_active[env.latch] = 0
a = m.joint("remote_cover_free").qposadr[0]; d.qpos[a:a+3] = [0.6, 0.6, 0.02]
# move device group to the fence
p, R = env.body_pose("remote_body")
dx = FENCE_X - dm["L"]/2 - 0.0003 - p[0]
for b in ("remote_body", "remote_cell0", "remote_cell1"):
    a = env.free[b]; d.qpos[a] += dx
# park both arms away
for k in ("R", "L"):
    env.set_ctrl(np.radians([90 if k == "R" else -90, -100, 40, 80, 0]), 0.0, arm=k)
mujoco.mj_forward(m, d); env.step(0.5)
p, R = env.body_pose("remote_body")
ta = m.joint("pry_tool_free").qposadr[0]; tv = m.joint("pry_tool_free").dofadr[0]
def W(xl, zl):  # device-local (x, z) of tip site -> world tool origin
    return p + R @ np.array([xl - 0.0006, 0.0, zl])
q_tool = np.array([1.0, 0, 0, 0])   # tool +x = world +x
cur = W(dm["cx0"] - 0.004, dm["T"] + 0.02)
sys.argv = sys.argv
tb = m.body("pry_tool").id
d.qpos[ta:ta+3] = cur; d.qpos[ta+3:ta+7] = q_tool; d.qvel[tv:tv+6] = 0; mujoco.mj_forward(m, d)
def pd_step(pt):
    """stiff 6-DoF PD 'hand' on the tool (physical forces, no teleporting)"""
    x = d.xpos[tb]; v = d.qvel[tv:tv+3]; w = d.qvel[tv+3:tv+6]
    Rt = d.xmat[tb].reshape(3, 3)
    err_r = 0.5 * np.cross(Rt, np.eye(3), axis=0).sum(axis=1)       # small-angle orientation error to identity
    F = 3000 * (pt - x) - 25 * v + np.array([0, 0, 1]) * m.body_subtreemass[tb] * (-m.opt.gravity[2])
    Tq = 3.0 * err_r - 0.03 * w
    d.xfrc_applied[tb, :3] = F; d.xfrc_applied[tb, 3:] = Tq
    env.step(0.002)
def drive(target, speed=0.01):
    global cur
    target = np.asarray(target, float)
    n = max(1, int(np.linalg.norm(target - cur) / speed / 0.002))
    for i in range(1, n + 1):
        pd_step(cur + (target - cur) * i / n)
    for _ in range(50):
        pd_step(target)
    cur = target
def cells():
    out = []
    for i in range(2):
        pc, Rc = env.body_pose(f"remote_cell{i}")
        ax = Rc[:, 2]                     # cylinder axis (+ end at local -z)
        plus = pc - ax * dm["cell_len"] / 2
        pl = R.T @ (plus - p)
        tilt = np.degrees(np.arcsin(np.clip(-(R.T @ ax)[2], -1, 1)))
        out.append((round(1000 * (pl[0] - dm["cx0"]), 1), round(1000 * pl[2], 1), round(tilt, 1)))
    return out
cx0, T, cz = dm["cx0"], dm["T"], dm["cov_z0"]
print("seated (+end x-cx0 mm, +end z mm, tilt deg):", cells(), "lip_z0", round(dm['lip_z0']*1000,1), "cov_z0", round(cz*1000,1))
if mode in ("full", "push"):
    drive(W(cx0 - 0.004, dm["slot_floor"] + 0.0006))
    drive(W(cx0 + 0.0052, dm["slot_floor"] + 0.0006), 0.005)
    print("pushed:", cells(), "tip", np.round(1000*(R.T@(d.site("pry_tip").xpos-p)),1), "cx0", round(1000*cx0,1)); print([ (m.geom(d.contact[i].geom1).name, m.geom(d.contact[i].geom2).name) for i in range(d.ncon) if m.geom_bodyid[d.contact[i].geom1]==m.body("pry_tool").id or m.geom_bodyid[d.contact[i].geom2]==m.body("pry_tool").id])
    if mode == "full":
        drive(W(cx0 + 0.0052, cz + 0.0005), 0.008)
        print("lifted:", cells())
        drive(W(cx0 + 0.001, cz + 0.0005), 0.005)
        drive(W(cx0 + 0.001, cz - 0.004), 0.005)
        drive(W(cx0 - 0.009, cz - 0.004), 0.005)
        print("released on ledge:", cells())
        drive(W(cx0 - 0.009, T + 0.03), 0.02)
    else:
        drive(W(cx0 - 0.004, dm["slot_floor"] + 0.0006), 0.005)
        drive(W(cx0 - 0.004, T + 0.03), 0.02)
drive(W(cx0 - 0.009, T + 0.08), 0.05); d.xfrc_applied[tb] = 0
d.qpos[ta:ta+3] = [0.6, -0.4, 0.05]; d.qvel[tv:tv+6] = 0
env.step(1.0)
print("after tool out:", cells())
views(env, sys.argv[3] + f"/mech_{dev}_{mode}.png", [(d.site("remote_plus").xpos, 0.10, 200, -40), (d.site("remote_plus").xpos, 0.08, 270, -10)])
# invert: rotate the device group 180 deg about its long axis above the table, then shake (gravity flip instead)
m.opt.gravity[:] = [0, 0, 9.81]
bid = m.body("remote_body").id
c0 = [d.body(f"remote_cell{i}").xpos.copy() for i in range(2)]
pb0 = d.body("remote_body").xpos.copy()
for k in range(150):          # pin the body with xfrc (hold) while shaking +-2g sideways/vertically
    d.xfrc_applied[bid, :3] = [0, 0, -(0.075 + 0.05) * 9.81 * 3]
    g = 9.81 * (1 + 2.0 * np.sin(k * 0.6))
    m.opt.gravity[:] = [3.0 * np.sin(k * 0.9), 2.0 * np.cos(k * 0.7), g]
    env.step(0.01)
print("device moved mm", np.round(1000*(d.body("remote_body").xpos-pb0),1))
moved = [round(1000 * np.linalg.norm(d.body(f"remote_cell{i}").xpos - c0[i]), 1) for i in range(2)]
print(f"INVERTED+SHAKE {dev} {mode}: cell displacement mm {moved} ->", "CELLS OUT" if min(moved) > 20 else ("one out" if max(moved) > 20 else "retained"))
