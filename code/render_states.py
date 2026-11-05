"""Render staged key states of the battery-removal task for the mid-term slide.

These are *staged* configurations (objects / arm placed by script and physics
settled), not policy rollouts. They illustrate the scenario and success check:

  1_start      device on the jig, arm at home
  2_press      gripper tip on the cover grip ridges (IK), latch about to release
  3_open       cover slid 40 mm toward +x, AA cells exposed
  4_goal       success state: cells in the battery bin, body + cover in the body crate
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.ik import solve_ik  # noqa: E402
from battery_sim.scene import load_model  # noqa: E402
from battery_sim.success import check_success  # noqa: E402

OUT = Path(__file__).resolve().parent / "renders"
HOME = np.radians([0.0, -100.0, 40.0, 80.0, 0.0])
ARM = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
CAMS = ("hero", "overview", "closeup", "top", "wide")


def set_arm(m, d, q5, grip):
    for j, v in zip(ARM, list(q5) + [grip]):
        d.qpos[m.joint(j).qposadr[0]] = v
        d.ctrl[m.actuator(j).id] = v


def place_free(m, d, joint, pos, quat=(1, 0, 0, 0)):
    a = m.joint(joint).qposadr[0]
    d.qpos[a:a + 3] = pos
    d.qpos[a + 3:a + 7] = quat
    v = m.joint(joint).dofadr[0]
    d.qvel[v:v + 6] = 0


def step(m, d, sec):
    for _ in range(int(sec / m.opt.timestep)):
        mujoco.mj_step(m, d)


def render(m, d, tag, cams=CAMS):
    r = mujoco.Renderer(m, 1080, 1920)
    for c in cams:
        r.update_scene(d, camera=c)
        Image.fromarray(r.render()).save(OUT / f"{tag}_{c}.png")
    r.close()


def cover_ridge_world(m, d):
    """World position of the cover's grip ridges (rear end of the cover, top surface)."""
    gid = m.geom("remote_cover_plate").id
    R = d.geom_xmat[gid].reshape(3, 3)
    hx, _, hz = m.geom_size[gid]
    return d.geom_xpos[gid] + R @ np.array([-hx + 0.011, 0, hz + 0.0012])


def main():
    OUT.mkdir(exist_ok=True)
    # 1) start
    m = load_model()
    d = mujoco.MjData(m)
    set_arm(m, d, HOME, 0.0)
    step(m, d, 1.5)
    render(m, d, "1_start")
    print("start success check:", check_success(m, d))

    # 2) press: closed gripper tip on the ridges, approach straight down
    tgt = cover_ridge_world(m, d)
    q, err = solve_ik(m, d, tgt, approach=(0, 0, -1), q_init=HOME)
    print(f"press IK error {err*1000:.2f} mm, q(deg)={np.degrees(q).round(1)}")
    set_arm(m, d, q, -0.15)
    step(m, d, 0.8)
    render(m, d, "2_press", ("hero", "closeup", "overview"))

    # 3) cover slid open 40 mm (no latch), arm following the ridges
    m = load_model(cover_offset=0.040)
    d = mujoco.MjData(m)
    set_arm(m, d, HOME, 0.0)
    mujoco.mj_forward(m, d)
    tgt = cover_ridge_world(m, d)
    q, err = solve_ik(m, d, tgt, approach=(0, 0, -1), q_init=HOME)
    print(f"open IK error {err*1000:.2f} mm")
    set_arm(m, d, q, -0.15)
    step(m, d, 0.8)
    render(m, d, "3_open", ("hero", "closeup", "overview", "top"))
    set_arm(m, d, HOME, 0.0)          # arm back home so the exposed cells are visible
    step(m, d, 1.0)
    render(m, d, "3_open_home", ("closeup", "hero"))

    # 4) goal: cells in the red battery bin, body + cover in the blue crate
    m = load_model(cover_offset=0.0)
    d = mujoco.MjData(m)
    m.eq("remote_latch").active0 = 0
    mujoco.mj_resetData(m, d)
    set_arm(m, d, HOME, 0.0)
    mujoco.mj_forward(m, d)
    bb = d.site("battery_bin_region").xpos.copy()
    cb = d.site("body_bin_region").xpos.copy()
    q_cell = (np.cos(np.pi / 4), 0, np.sin(np.pi / 4), 0)       # lying cell
    place_free(m, d, "remote_cell0_free", bb + [-0.015, 0.012, -0.02], q_cell)
    place_free(m, d, "remote_cell1_free", bb + [0.012, -0.01, 0.0], (0.6533, 0.2706, 0.6533, -0.2706))
    yaw = np.pi / 2 - 0.15
    place_free(m, d, "remote_free", cb + [0.0, 0.0, -0.025], (np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)))
    place_free(m, d, "remote_cover_free", cb + [0.03, 0.05, 0.0], (np.cos(0.4), 0, 0, np.sin(0.4)))
    step(m, d, 2.0)
    render(m, d, "4_goal", ("hero", "overview", "top"))
    print("goal success check:", check_success(m, d))
    print("saved staged renders to", OUT)


if __name__ == "__main__":
    main()
