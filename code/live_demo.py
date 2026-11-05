"""Live demo in the interactive MuJoCo viewer (for screen recording with your own narration).

  python live_demo.py --device tv_remote --seed 0                 # real time, starts paused
  python live_demo.py --device light_remote --seed 1 --speed 0.5  # half speed (slow motion)
  python live_demo.py --device ac_remote --seed 2 --pause-stages  # auto-pause after every stage
  python live_demo.py --device stb_remote --seed 3 --cam free --clean   # free mouse camera, no side panels
  python live_demo.py --device tv_remote --seed 0 --mode no_tool       # control: just turn it over (cells stay in)
  python live_demo.py --device tv_remote --seed 0 --mode push_only     # control: push into springs, no lift

Keys (in the viewer window):
  Space      pause / resume (the episode starts paused so you can set up the camera and the recorder)
  + / -      faster / slower (x2 / x0.5; between 0.125x and 4x)
  [ / ]      previous / next fixed camera (MuJoCo default keys); Esc = free camera
  mouse      left drag = rotate, right drag = move, scroll = zoom (free camera)
  Tab / Shift+Tab   show / hide the left / right UI panels

The policy is exactly the one used in the evaluation (run_episode.py); the viewer only watches the
simulation. Text output in the terminal shows every skill step. On macOS run it with `mjpython`
instead of `python` (MuJoCo's passive viewer requirement); Windows / Linux use plain python.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.devices import DEVICE_ORDER, DEVICES  # noqa: E402
from battery_sim.env import BatteryRemovalEnv  # noqa: E402
from battery_sim.policy import SkillPolicy  # noqa: E402

# what each evaluation stage is (overlay text; the MuJoCo overlay font is ASCII only)
STAGE_TEXT = {
    "push_to_fence": "R: push the remote against the jig fence",
    "pick_tool": "L: pick the pry tool from its holder",
    "slide_cover": "R: press + slide the latched cover off",
    "reseat_on_fence": "R: re-seat the remote on the fence",
    "hold_device": "R: hold the remote on the jig",
    "pry_cells": "L: push cells into springs, lever + ends over the lips",
    "grasp_device": "R: re-grasp and lift the remote",
    "flip_over_bin": "R: turn over the battery bin and shake",
    "return_tool": "L: put the tool back",
    "drop_in_crate": "R: drop the empty body into the crate",
}
PHASE_TEXT = {
    "pry_approach": "tool to the pry notch", "pry_above": "blade upright above the notch",
    "pry_inserted": "blade in the notch", "pry_pushed": "cells pushed past the lips",
    "pry_lift_step": "levering the + ends up", "pry_lifted": "+ ends above the lip tops",
    "pry_slid_back": "springs push cells back over the lips", "pry_set_down": "cells resting on the lips",
    "pry_done": "tool withdrawn",
}
KEY_SPACE, KEY_PLUS, KEY_MINUS, KEY_KP_ADD, KEY_KP_SUB, KEY_EQUAL = 32, 334, 333, 334, 333, 61


class LiveView:
    """Wraps env.step: draws the viewer at ~30 fps of wall time, paces the simulation to `speed`x real time,
    and blocks while paused."""

    def __init__(self, env, pol, speed=1.0, cam="hero", clean=False, pause_stages=False, start_paused=True,
                 viewer=None):
        self.env, self.pol = env, pol
        self.speed = speed
        self.paused = start_paused
        self.pause_stages = pause_stages
        self.phase = ""
        self.final = ""
        self._n_stages = 0
        if viewer is None:
            from mujoco import viewer as mjviewer
            viewer = mjviewer.launch_passive(env.m, env.d, key_callback=self._key,
                                                  show_left_ui=not clean, show_right_ui=not clean)
        self.v = viewer
        if cam != "free":
            self.v.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
            self.v.cam.fixedcamid = env.m.camera(cam).id
        self._orig_step = env.step
        env.step = self._step
        pol.on_phase = self._on_phase
        self._wall0 = time.perf_counter()
        self._sim0 = env.d.time
        self._next_draw = 0.0
        self._draw()

    # ---------------------------------------------------------------- input
    def _key(self, key):
        if key == KEY_SPACE:
            self.paused = not self.paused
        elif key in (KEY_PLUS, KEY_EQUAL, KEY_KP_ADD):
            self.speed = min(self.speed * 2, 4.0)
        elif key in (KEY_MINUS, KEY_KP_SUB, 45):
            self.speed = max(self.speed / 2, 0.125)
        self._resync()

    def _resync(self):
        self._wall0, self._sim0 = time.perf_counter(), self.env.d.time

    def _on_phase(self, name):
        self.phase = PHASE_TEXT.get(name, "")

    # ---------------------------------------------------------------- drawing / pacing
    def _texts(self):
        st = self.env.log.stages
        done = "\n".join(f"{'OK  ' if ok else 'FAIL'} {STAGE_TEXT.get(n, n)}" for n, _, ok in st[-7:])
        head = f"t = {self.env.d.time:5.1f} s   speed {self.speed:g}x" + ("   [PAUSED - Space]" if self.paused else "") + (
            "   " + self.final if self.final else "")
        now = self.phase if (st and st[-1][0] in ("hold_device", "pry_cells") and self.phase) else ""
        return [(mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_TOPLEFT, head, ""),
                (mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_BOTTOMLEFT,
                 done + ("\n> " + now if now else ""), "")]

    def _draw(self):
        try:
            self.v.set_texts(self._texts())
        except Exception:
            pass
        self.v.sync()

    def _wait_paused(self):
        while self.paused and self.v.is_running():
            self._draw()
            time.sleep(1 / 30)
        self._resync()

    def _step(self, seconds):
        if not self.v.is_running():
            raise SystemExit("viewer closed")
        self._orig_step(seconds)
        st = self.env.log.stages
        if len(st) != self._n_stages:
            self._n_stages = len(st)
            if self.pause_stages:
                self.paused = True
        if self.paused:
            self._wait_paused()
        # pace: sim time advances at `speed` x wall time
        target_wall = self._wall0 + (self.env.d.time - self._sim0) / self.speed
        lag = target_wall - time.perf_counter()
        if lag > 0:
            time.sleep(lag)
        if time.perf_counter() >= self._next_draw:
            self._next_draw = time.perf_counter() + 1 / 30
            self._draw()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", default="tv_remote", choices=DEVICE_ORDER)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0, help="playback speed (1 = real time, 0.5 = slow motion)")
    ap.add_argument("--cam", default="hero", help="fixed camera name (hero, overview, operator, wide, closeup, top, "
                                                  "side, bincam, slotcam) or 'free'")
    ap.add_argument("--clean", action="store_true", help="hide the viewer's side panels (clean recording)")
    ap.add_argument("--pause-stages", action="store_true", help="pause automatically after every stage")
    ap.add_argument("--no-start-paused", action="store_true", help="start running immediately")
    ap.add_argument("--mode", default="full", choices=("full", "no_tool", "push_only"),
                    help="full policy, or one of the control experiments of ablation.py")
    ap.add_argument("--hold", type=float, default=0.0, help="keep the window open N s after the end (0 = until closed)")
    args = ap.parse_args()

    env = BatteryRemovalEnv(device=args.device)
    env.reset(args.seed)
    pol = SkillPolicy(env, verbose=True, use_tool=args.mode != "no_tool", lift_cells=args.mode != "push_only")
    print(f"mode {args.mode}, device {args.device} ({DEVICES[args.device].label}), seed {args.seed}. "
          f"Viewer is {'running' if args.no_start_paused else 'PAUSED: press Space to start'}.")
    lv = LiveView(env, pol, speed=args.speed, cam=args.cam, clean=args.clean, pause_stages=args.pause_stages,
                  start_paused=not args.no_start_paused)
    try:
        rep = pol.run()
    except SystemExit as e:
        print(e)
        return
    env.step = lv._orig_step
    print(f"RESULT: success={rep.success}, cells in bin {list(map(bool, rep.cells_in_battery_bin))}, "
          f"body in crate {bool(rep.body_in_crate)}, peak force {env.log.peak_force:.1f} N")
    lv.final = f"DONE - {'SUCCESS' if rep.success else 'FAILED'}"
    t_end = time.perf_counter() + (args.hold if args.hold > 0 else 1e9)
    while lv.v.is_running() and time.perf_counter() < t_end:
        lv._draw()
        time.sleep(1 / 30)


if __name__ == "__main__":
    main()
