"""Build the battery-removal scene, settle the physics, check stability and render all cameras.

Usage:  python render_scene.py [--settle 2.0] [--out renders]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.scene import load_model  # noqa: E402

REST_DEG = (0.0, -100.0, 40.0, 80.0, 0.0, 10.0)  # tucked home pose above/behind the jig
ARM_JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
TRACKED = ("remote_body", "remote_cover", "remote_cell0", "remote_cell1")


def set_arm(model, data, q_deg):
    q = np.radians(q_deg)
    for j, v in zip(ARM_JOINTS, q):
        data.qpos[model.joint(j).qposadr[0]] = v
        data.ctrl[model.actuator(j).id] = v


def settle(model, data, seconds):
    start = {b: data.body(b).xpos.copy() for b in TRACKED}
    for _ in range(int(seconds / model.opt.timestep)):
        mujoco.mj_step(model, data)
    drift = {b: float(np.linalg.norm(data.body(b).xpos - start[b])) * 1000 for b in TRACKED}
    return drift


def render_all(model, data, out: Path, tag: str, size=(1080, 1920)):
    r = mujoco.Renderer(model, *size)
    opt = mujoco.MjvOption()
    for cam in ("overview", "operator", "wide", "closeup", "top"):
        r.update_scene(data, camera=cam, scene_option=opt)
        Image.fromarray(r.render()).save(out / f"{tag}_{cam}.png")
    r.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "renders"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    model = load_model()
    data = mujoco.MjData(model)
    print(f"model: nbody={model.nbody} ngeom={model.ngeom} nq={model.nq} timestep={model.opt.timestep}")
    set_arm(model, data, REST_DEG)
    mujoco.mj_forward(model, data)
    drift = settle(model, data, args.settle)
    print("settle drift (mm):", {k: round(v, 2) for k, v in drift.items()})
    render_all(model, data, out, "initial")
    print("saved to", out)


if __name__ == "__main__":
    main()
