"""Bimanual skill-based scripted policy (state machine) for the battery-removal task.

Two SO-101 arms:
  R  main arm   (base at the origin, facing +x): device handling.
  L  tool arm   (base across the jig, facing -x): holds a thin pry tool.

Skills are Cartesian motions solved with DLS IK each control tick (50 Hz) and sent to the
position servos. Every skill is a Python generator that sets its arm's servo targets for one
control tick and then yields, so a scheduler (``SkillPolicy.run_par``) can execute skills of
the two arms concurrently. Every stage ends with a state check; failed checks trigger a
bounded retry, otherwise the episode aborts with the failing stage recorded.

Stages
  L  pick_tool       top grasp of the pry-tool handle in its rack (force-limited), lift it out,
                     measure the tool pose in the hand.                       (parallel with 1-2)
  R  1 push_to_fence closed jaw tips press the device's rear top face and drag it +x until its
                     front end touches the jig's aluminium fence.
  R  2 slide_cover   press the cover grip ridges down and drag along device +x: the
                     press-and-slide latch releases (env), the cover slides off past the fence.
  R  3 hold_device   press the rear of the device down onto the jig (it is braced by the fence).
  L  4 pry_cells     tool tip into the pry notch behind the + ends, hooked foot under the cells;
                     push both cells ~5 mm into their springs (past the retaining lip), lift the
                     + ends above the lip top, let the springs push them back onto the lip top,
                     withdraw the tool. Feedback on the cell poses; retries shift the tool.
  L  5 return_tool   put the tool back into its rack and park.                (parallel with 6-8)
  R  6 grasp_device  top grasp of the solid rear section across the device width.
  R  7 flip_over_bin carry the pocket over the red bin, roll the device ~125-140 deg about its
                     long axis (= wrist-flex axis), shake: the freed cells drop into the bin.
  R  8 drop_in_crate carry the empty device over the blue crate and release it.
"""

from __future__ import annotations

import mujoco
import numpy as np

from battery_sim.env import GRIP_CLOSED, GRIP_OPEN, HOME, BatteryRemovalEnv
from battery_sim.ik import IK
from battery_sim.scene import BATTERY_BIN, BODY_CRATE, FENCE_X, FLIP_AIM, TOOL_FOOT_ANGLE, TOOL_LEN, TOOL_RACK

DT = 0.02                                   # control period (50 Hz)
PRESS_OFF = np.array([0.012, 0.0, 0.004])   # contact point of the closed jaw tips (tool frame)
DOWN = np.array([0.0, 0.0, -1.0])
GRASP_DEPTH = 0.016                         # fingertips this far below the device top (device is 22 mm thick)
HANDLE_D = 0.022                            # pry-tool handle width across the jaws
UNLATCH_SHIFT = 0.0062                      # push the cells this far into their springs (lip overhang 4.5 mm; the
                                            # tool's back face must clear the lip end before the lift)
FLIP_MIN_UPZ = -0.5                         # flip pose: device turned >= 120 deg
DROP_H_WEIGHT = 0.25                        # planner cost per metre of drop height (vs. metres off centre)
DROP_LEAD = 0.0                             # (measured: freed cells land ~7.5 cm from the pocket along the opening's
                                            # horizontal direction; the bin is long enough on that side instead)
R_LEAN = np.radians(20.0)                   # main arm grasp approach lean (keeps its wrist clear of the tool arm)
LEAN = TOOL_FOOT_ANGLE                      # the tool is held leaning back (handle toward arm L) by 10 deg: with a
                                            # vertical tool the SO-101 wrist-flex limit (95 deg) is hit near the jig


def lean_frame(R, ang=LEAN):
    """Tool orientation: frame R rotated about its y axis so that the tool's +z leans toward R's +x."""
    c, s = np.cos(ang), np.sin(ang)
    return R @ np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rot(v, axis, ang):
    axis = axis / np.linalg.norm(axis)
    return v * np.cos(ang) + np.cross(axis, v) * np.sin(ang) + axis * (axis @ v) * (1 - np.cos(ang))


def _slerp(a, b, s):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    dot = np.clip(a @ b, -1, 1)
    if dot > 0.9995:
        v = a + s * (b - a)
        return v / np.linalg.norm(v)
    th = np.arccos(dot)
    if abs(np.pi - th) < 1e-3:   # antiparallel: rotate about any perpendicular
        perp = np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0])
        return _rot(a, perp, th * s)
    return (np.sin((1 - s) * th) * a + np.sin(s * th) * b) / np.sin(th)


def _smooth(s):
    return s * s * (3 - 2 * s)


class Arm:
    """Command state + motion primitives (generators) of one SO-101."""

    def __init__(self, policy, key):
        self.p = policy
        self.env = policy.env
        self.key = key
        self.io = self.env.arms[key]
        self.ik = IK(self.env.m, self.io.prefix)
        self.qcmd = self.env.q_of(key)
        self.grip_cmd = 0.0
        self.force_limit = None              # (body, lo N, hi N) while holding something

    # -------------------------------------------------------------- helpers
    def tool(self, offset=(0, 0, 0)):
        return self.ik.fk(self.qcmd, offset)

    def tcp_actual(self):
        s = self.env.d.site(self.io.site)
        return s.xpos.copy(), s.xmat.reshape(3, 3).copy()

    def set(self, q, g=None):
        if self.force_limit is not None and g is not None:
            # servo torque limit (as configured on the STS3215): keep the squeeze on the held body in [lo, hi]
            body, lo, hi = self.force_limit
            f = self.env.grip_force(self.key, body)
            if f > hi:
                self.grip_cmd += 0.003
            elif f < lo:
                self.grip_cmd -= 0.0015
            g = self.grip_cmd
        self.env.set_ctrl(q, g, arm=self.key)

    def solve_best(self, target, axes=None, offset=(0, 0, 0), vecs=None, seeds=None, iters=300):
        best = None
        seeds = seeds or (self.qcmd, HOME, np.radians([0, -30, 40, 80, 0]), np.radians([0, 0, 20, 70, 0]))
        for seed in seeds:
            q, err, rerr = self.ik.solve(seed, target, axes or {}, offset, iters=iters, vecs=vecs)
            score = err + 0.02 * rerr
            if best is None or score < best[0]:
                best = (score, q, err, rerr)
        return best[1], best[2], best[3]

    # -------------------------------------------------------------- primitives (generators)
    def wait(self, t):
        for _ in range(max(1, int(round(t / DT)))):
            self.set(self.qcmd, self.grip_cmd)
            yield

    def move(self, target, axes=None, offset=(0, 0, 0), grip=None, speed=0.10, min_time=0.25, settle=0.1,
             iters=60, vecs=None):
        """Straight-line Cartesian move of the tool point ``offset`` to ``target``. Returns worst IK error."""
        offset = np.asarray(offset, float)
        p0, R0 = self.tool(offset)
        target = np.asarray(target, float)
        axes = axes or {}
        dur = max(min_time, np.linalg.norm(target - p0) / speed)
        n = max(1, int(dur / DT))
        g0 = self.grip_cmd
        q = self.qcmd
        worst = 0.0
        vecs0 = [(loc, R0 @ (np.asarray(loc, float) / np.linalg.norm(loc))) for loc, _ in (vecs or [])]
        for i in range(1, n + 1):
            s = _smooth(i / n)
            p = p0 + (target - p0) * s
            ax = {k: _slerp(R0[:, k], np.asarray(v, float), s) for k, v in axes.items()}
            vv = [(loc, _slerp(v0, np.asarray(v, float), s)) for (loc, v0), (_, v) in zip(vecs0, vecs or [])]
            q, err, _ = self.ik.solve(q, p, ax, offset, iters=iters, vecs=vv or None)
            worst = max(worst, err)
            g = g0 + (grip - g0) * s if grip is not None else g0
            self.qcmd = q
            self.set(q, g)
            yield
        if grip is not None:
            self.grip_cmd = grip
        yield from self.wait(settle)
        return worst

    def goto_q(self, q1, dur=1.0, settle=0.1, grip=None):
        q0 = self.qcmd.copy()
        g0 = self.grip_cmd
        n = max(1, int(dur / DT))
        for i in range(1, n + 1):
            s = _smooth(i / n)
            self.qcmd = q0 + (np.asarray(q1, float) - q0) * s
            self.set(self.qcmd, g0 + (grip - g0) * s if grip is not None else g0)
            yield
        self.qcmd = np.array(q1, float)
        if grip is not None:
            self.grip_cmd = grip
        yield from self.wait(settle)

    def goto(self, target, axes=None, offset=(0, 0, 0), grip=None, dur=1.2, settle=0.1, vecs=None):
        """Transit move: IK from several seeds, then smooth joint-space interpolation. Returns IK error."""
        q1, err, _ = self.solve_best(target, axes, offset, vecs)
        yield from self.goto_q(q1, dur, settle, grip)
        return err

    def grip(self, value, t=0.6):
        self.force_limit = None
        self.grip_cmd = value
        yield from self.wait(t)

    def regulate_grip(self, body, lo=18.0, hi=32.0, step=0.004, n=12):
        """Keep the squeeze inside [lo, hi] N (the servo keeps pushing toward its target after contact)."""
        for _ in range(n):
            f = self.env.grip_force(self.key, body)
            if lo <= f <= hi:
                return
            self.grip_cmd += step if f > hi else -step
            self.set(self.qcmd, self.grip_cmd)
            for _ in range(3):
                yield

    def compliant_close(self, body, target_force=30.0, step=0.006):
        """Force-limited grasp: close the jaw in small position steps until the jaw contact force on
        ``body`` reaches ``target_force`` (the STS3215 servo would otherwise squeeze with full torque)."""
        g = self.env.d.qpos[self.io.gq]
        while g > GRIP_CLOSED:
            g -= step
            self.grip_cmd = g
            self.set(self.qcmd, g)
            yield
            if self.env.grip_force(self.key, body) >= target_force:
                break
        yield from self.wait(0.3)
        self.p.say(f"[{self.key}] compliant grasp of {body}: jaw {g:.3f} rad, squeeze "
                   f"{self.env.grip_force(self.key, body):.1f} N")

    def home(self, dur=0.8):
        yield from self.goto_q(HOME, dur=dur, settle=0.2)


class SkillPolicy:
    def __init__(self, env: BatteryRemovalEnv, verbose=True, use_tool=True, lift_cells=True, hold=True):
        self.env = env
        self.verbose = verbose
        self.use_tool, self.lift_cells, self.hold = use_tool, lift_cells, hold    # ablation switches
        self.R = Arm(self, "R")
        self.L = Arm(self, "L")
        dm = env.dims
        self.dm = dm
        self.L_, self.W, self.T = dm["L"], dm["W"], dm["T"]
        self.grasp_x = dm["grasp_x"]
        self.grasp_off = np.array([0.02 - self.W / 2, 0.0, 0.0])   # fixed jaw tip at tool x = +0.02
        # jaw bottom is 6.6 mm below the tool origin: keep it >= 0.5 mm above the tray for thinner devices
        # fingertips 3.5 mm above the jig: the jaw pads touch the housing over its full height (resists the
        # device pitching in the grasp; the cells make the device nose-heavy)
        self.grasp_depth = self.T - 0.0035
        p, R = env.body_pose("remote_body")
        pc, _ = env.body_pose("remote_cover")
        self.cover_seat = float(R[:, 0] @ (pc - p))
        self.cover_hx = float(env.m.geom_size[env.m.geom("remote_cover_plate").id][0])
        self.tool_rel = None
        self.on_phase = None                     # debugging hook: called with a phase name inside skills

    def phase(self, name):
        if self.on_phase is not None:
            self.on_phase(name)

    # ------------------------------------------------------------- infrastructure
    def say(self, *a):
        if self.verbose:
            print(f"  [{self.env.d.time:6.2f}s]", *a)

    def run_par(self, *gens):
        """Run skill generators concurrently (one control tick each, then DT of physics)."""
        gens = list(gens)
        res = [None] * len(gens)
        alive = [True] * len(gens)
        while any(alive):
            for i, g in enumerate(gens):
                if alive[i]:
                    try:
                        next(g)
                    except StopIteration as e:
                        alive[i] = False
                        res[i] = e.value
            self.env.step(DT)
        return res[0] if len(gens) == 1 else res

    def stage(self, name, ok):
        self.env.log.stages.append((name, float(self.env.d.time), bool(ok)))
        self.say(f"stage {name}: {'OK' if ok else 'FAIL'}  (peak contact force so far {self.env.log.peak_force:.1f} N)")
        return ok

    def device(self):
        return self.env.body_pose("remote_body")

    def local(self, x, y, z):
        p, R = self.device()
        return p + R @ np.array([x, y, z])

    # ------------------------------------------------------------- cell state
    def cell_state(self):
        """Per cell, in the device frame: (+ end x - cx0, + end bottom z, tilt deg (+ end up))."""
        p, R = self.device()
        out = []
        for i in range(2):
            pc, Rc = self.env.body_pose(f"remote_cell{i}")
            ax = R.T @ Rc[:, 2]                                  # cell axis, + end at local -z
            c = R.T @ (pc - p)
            plus = c - ax * self.dm["cell_len"] / 2
            tilt = float(np.degrees(np.arcsin(np.clip(ax[2], -1, 1))))
            bottom = plus[2] - self.dm["cell_r"] * np.cos(np.radians(tilt))
            out.append((float(plus[0] - self.dm["cx0"]), float(bottom), tilt))
        return out

    def cells_free(self):
        """A cell is free when its + end has been lifted onto the top of the retaining lip (and it is still
        in the pocket region)."""
        return [st[1] > self.dm["cov_z0"] - 0.0005 and -0.02 < st[0] < 0.03 and st[1] < self.T + 0.02
                for st in self.cell_state()]

    # ------------------------------------------------------------- R skills
    def push_to_fence(self, name="push_to_fence"):
        A = self.R
        p, R = self.device()
        x, y = R[:, 0], R[:, 1]
        front_x = max((p + R @ [self.L_ / 2, sy * self.W / 2, 0])[0] for sy in (-1, 1))
        gap = FENCE_X - front_x
        if gap < 0.002:
            return self.stage(name, True)
        # press the jaw tips on the solid rear section (top face) and drag toward the fence by friction
        pt = p + R @ [-self.L_ / 2 + 0.025, 0, self.T]
        axes = {2: DOWN, 0: y}
        e1 = yield from A.goto(pt + [0, 0, 0.04], axes, PRESS_OFF, grip=GRIP_CLOSED)
        e2 = yield from A.move(pt - [0, 0, 0.003], axes, PRESS_OFF, speed=0.03, settle=0.15)
        end = pt + x * (gap / max(x[0], 0.5) + 0.006) - [0, 0, 0.003]
        e3 = yield from A.move(end, axes, PRESS_OFF, speed=0.03, settle=0.2)
        self.say(f"[R] push ik err approach {1000*e1:.1f} / press {1000*e2:.1f} / drag {1000*e3:.1f} mm")
        yield from A.move(A.tool(PRESS_OFF)[0] + [0, 0, 0.05], axes, PRESS_OFF, speed=0.08)
        p, R = self.device()
        front_x = max((p + R @ [self.L_ / 2, sy * self.W / 2, 0])[0] for sy in (-1, 1))
        self.say(f"[R] front end gap to fence {1000 * (FENCE_X - front_x):.1f} mm, yaw "
                 f"{np.degrees(np.arctan2(R[1, 0], R[0, 0])):.1f} deg")
        return self.stage(name, FENCE_X - front_x < 0.004)

    def cover_offset(self):
        """Cover displacement along device +x relative to its seated position (m), and its height."""
        p, R = self.device()
        pc, _ = self.env.body_pose("remote_cover")
        return float(R[:, 0] @ (pc - p)) - self.cover_seat, float(R[:, 2] @ (pc - p))

    def slide_cover(self, attempt=0):
        A = self.R
        p, R = self.device()
        x, y = R[:, 0], R[:, 1]
        pc, Rc = self.env.body_pose("remote_cover")
        ridge = pc + Rc @ [-self.cover_hx + 0.011, 0, 0.0008 + 0.0008]
        axes = {2: DOWN, 0: y}
        press = 0.0025 + 0.0015 * attempt                    # how far below the ridge top we command
        yield from A.goto(ridge + [0, 0, 0.04], axes, PRESS_OFF, grip=GRIP_CLOSED)
        yield from A.move(ridge - [0, 0, press], axes, PRESS_OFF, speed=0.03, settle=0.15)
        self.phase("slide_pressed")
        for k in range(4):                                   # drag in segments, re-pressing each time
            tgt = ridge + x * (0.022 * (k + 1)) - [0, 0, press]
            yield from A.move(tgt, axes, PRESS_OFF, speed=0.025, settle=0.05)
            self.phase(f"slide_seg{k}")
        yield from A.move(A.tool(PRESS_OFF)[0] + [0, 0, 0.06], axes, PRESS_OFF, speed=0.08, settle=0.4)
        off, dz = self.cover_offset()
        self.say(f"[R] latch released: {self.env.log.latch_released_at is not None}, cover offset {1000*off:.1f} mm, "
                 f"dz {1000*dz:.1f} mm")
        if dz > self.T + 0.01:
            # the slid-off cover is wedged between the closed fingers: drop it on the mat beyond the fence
            yield from self.drop_cover()
        return self.stage("slide_cover", self.cover_clear())

    def cover_clear(self):
        """The cover is off the device: not lying on it / in the recess (it must not block the pry notch)."""
        p, R = self.device()
        pc, _ = self.env.body_pose("remote_cover")
        loc = R.T @ (pc - p)
        on_device = abs(loc[0]) < self.L_ / 2 + 0.01 and abs(loc[1]) < self.W / 2 + 0.01 and loc[2] > -0.005
        return not on_device

    def drop_cover(self):
        A = self.R
        p, R = self.device()
        drop = np.array([FENCE_X + 0.045, p[1] + 0.03, 0.07])
        yield from A.goto(drop, {2: DOWN}, PRESS_OFF, dur=1.0, settle=0.1)
        yield from A.grip(GRIP_OPEN, 0.5)
        yield from A.wait(0.4)
        yield from A.grip(GRIP_CLOSED, 0.4)
        self.say(f"[R] cover dropped beyond the fence at {np.round(self.env.body_pose('remote_cover')[0], 3)}")

    def hold_device(self):
        """Press the rear end of the device down onto the jig with the closed jaw tips (the other hand
        pries); the device is braced against the fence along +x."""
        A = self.R
        p, R = self.device()
        # press on the rear end (closer to the notch the two grippers would touch)
        hx = -self.L_ / 2 + 0.012
        pt = p + R @ [hx, 0, self.T]
        axes = {2: DOWN, 0: -R[:, 1]}            # wrist camera mount faces away from the tool arm
        yield from A.goto(pt + [0, 0, 0.03], axes, PRESS_OFF, grip=GRIP_CLOSED)
        e = yield from A.move(pt - [0, 0, 0.0045], axes, PRESS_OFF, speed=0.03, settle=0.2)
        self.say(f"[R] holding the device down at its rear end (ik {1000*e:.1f} mm)")
        return self.stage("hold_device", e < 0.005)

    def release_hold(self):
        A = self.R
        yield from A.move(A.tool(PRESS_OFF)[0] + [0, 0, 0.05], {2: DOWN}, PRESS_OFF, speed=0.06, settle=0.05)

    def grasp_device(self, lift=True, gx=None, lean=0.0):
        """Top grasp of the solid rear section across the device width (force-limited). With lift=False the
        device stays on the jig, held firmly while the tool arm pries (the second hand of a human worker)."""
        A = self.R
        if not getattr(self, "_holding", False):
            p, R = self.device()
            y = R[:, 1]
            gx = self.grasp_x if gx is None else gx
            c = p + R @ [gx, 0, 0]                            # default: behind the pocket, near the centre of mass
            top = p[2] + self.T
            # approach leaning back by 20 deg (wrist toward the main arm's base, away from the tool arm working
            # at the pry notch); jaws across the width, wrist camera mount facing away from the tool arm
            ap = R @ np.array([np.sin(lean), 0.0, -np.cos(lean)])
            if lift:
                # lifting grasp (tool arm is gone): jaw orientation nearer to the arm's natural wrist roll, which
                # also puts the pocket on the side the flip planner was validated for
                axes = {2: ap, 0: y if y[1] < 0 else -y}
            else:
                axes = {2: ap, 0: -y}
                # the SO-101 is 5-DoF: in some device poses the 20 deg lean + jaw direction is not reachable and
                # the IK error (up to 9 mm) lands the fixed jaw on the top edge. Pick the lean (preferring the
                # nominal one, then larger leans = wrist further from the tool arm) with an exact solution.
                bottom = np.array([c[0], c[1], top - self.grasp_depth])
                best = None
                for ln in (lean, lean + np.radians(10), lean - np.radians(10), lean + np.radians(20),
                           lean - np.radians(20)):
                    ax_ = {2: R @ np.array([np.sin(ln), 0.0, -np.cos(ln)]), 0: -y}
                    e_ = A.solve_best(bottom, ax_, self.grasp_off)[1]
                    if best is None or e_ < best[0] - 1e-4:
                        best = (e_, ln, ax_)
                    if e_ < 0.0015:
                        break
                if abs(best[1] - lean) > 1e-6:
                    self.say(f"[R] hold grasp: lean {np.degrees(lean):.0f} deg not reachable here -> "
                             f"{np.degrees(best[1]):.0f} deg (ik {1000*best[0]:.1f} mm)")
                axes = best[2]
                # 1 mm clearance between the fixed jaw and the side wall (the moving jaw closes the gap)
                c = c + 0.001 * np.asarray(axes[0], float)
            self._grasp_axes = axes
            yield from A.goto([c[0], c[1], top + 0.05], axes, self.grasp_off, grip=GRIP_OPEN)
            for k in range(3):
                e_g = yield from A.move([c[0], c[1], top - self.grasp_depth], axes, self.grasp_off, speed=0.04, settle=0.1)
                if self.on_phase is not None:
                    pa_, Ra_ = A.tcp_actual()
                    fj_w = pa_ + Ra_ @ np.array([0.02, 0, 0])       # fixed jaw tip (actual)
                    fj_c = A.tool(np.array([0.02, 0, 0]))[0]        # fixed jaw tip (commanded)
                    self.say(f"[R] grasp attempt {k}: ik {1000*e_g:.1f} mm, fixed jaw tip dev "
                             f"{np.round(1000*(R.T @ (fj_w - p)), 1)} (cmd {np.round(1000*(R.T @ (fj_c - p)), 1)}), W/2 {500*self.W:.1f}")
                yield from A.compliant_close("remote_body", 28.0 if not lift else 33.0)
                if self.env.jaw_force("R") > 3.0 or k == 2:
                    break                       # (last attempt: keep the press-down hold it ended in)
                # missed: the fixed jaw came down on the top edge instead of beside the side wall (the jaw is
                # placed with zero clearance) -> open, back up and come down again 2.5 mm further out
                self.say(f"[R] grasp missed (moving jaw {self.env.jaw_force('R'):.1f} N, jaw {self.env.d.qpos[A.io.gq]:.2f} rad)"
                         " -> re-grasp with clearance")
                yield from A.grip(GRIP_OPEN, t=0.3)
                yield from A.move([c[0], c[1], top + 0.01], axes, self.grasp_off, speed=0.04, settle=0.1)
                fj = np.asarray(axes[0], float)          # TCP x = toward the fixed jaw (grasp_off convention)
                c = c + 0.0025 * fj / np.linalg.norm(fj)
            A.force_limit = ("remote_body", 18.0, 30.0)
            self.phase("grasp_closed")
            self._holding = True
            if not lift:
                return self.stage("hold_device", self.env.grip_force("R") > 10.0)
        c = A.tool(self.grasp_off)[0]
        yield from A.move([c[0], c[1], 0.12], self._grasp_axes, self.grasp_off, speed=0.06, settle=0.3)
        yield from A.regulate_grip("remote_body", lo=20.0, hi=30.0)
        pd, _ = self.device()
        lifted = pd[2] > 0.06
        pa, Ra = A.tcp_actual()
        self._grasp_rel = Ra.T @ (pd - pa)
        self.say(f"[R] device lifted to z={pd[2]:.3f}, squeeze {self.env.grip_force('R'):.1f} N, cells free {self.cells_free()}")
        if not lifted:
            self._holding = False
        return self.stage("grasp_device", lifted)

    def grasp_offset(self):
        """Distance (m) between the device centre and where the rigid-grasp model says it should be."""
        if not hasattr(self, "_grasp_rel"):
            return 0.0
        pa, Ra = self.R.tcp_actual()
        pd, _ = self.device()
        return float(np.linalg.norm(pd - (pa + Ra @ self._grasp_rel)))

    # ------------------------------------------------------------- flip planning (arm R)
    def arm_collides(self, q, arm="R"):
        """True if the arm at joint config q penetrates anything except the device/cells (bench, jig,
        bins, decor, the other arm, the tool)."""
        m = self.env.m
        if not hasattr(self, "_scratch"):
            self._scratch = mujoco.MjData(m)
            dev = {m.body(b).id for b in ("remote_body", "remote_cover", "remote_cell0", "remote_cell1")}
            dev |= {m.body(f"remote_plunger{i}").id for i in range(2)}
            self._ignore = dev
        sd = self._scratch
        sd.qpos[:] = self.env.d.qpos
        A = self.R if arm == "R" else self.L
        sd.qpos[A.io.qadr] = q
        mujoco.mj_kinematics(m, sd)
        mujoco.mj_collision(m, sd)
        rb = self.env.arm_bodies[arm]
        for i in range(sd.ncon):
            c = sd.contact[i]
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            r1, r2 = b1 in rb, b2 in rb
            if r1 == r2:
                continue
            other = b2 if r1 else b1
            if other in self._ignore:
                continue
            if c.dist < -0.001:
                return True
        return False

    @staticmethod
    def _clear_of_obstacles(cw, margin=0.02):
        """Device corners must stay above the table and above the rims of both bins."""
        if cw[:, 2].min() < 0.02:
            return False
        for box in (BATTERY_BIN, BODY_CRATE):
            c = np.array(box["center"][:2])
            half = np.array(box["size"][:2]) / 2 + margin
            over = np.all(np.abs(cw[:, :2] - c) < half, axis=1)
            if np.any(cw[over, 2] < box["size"][2] + margin):
                return False
        return True

    def _dev_geom(self, q, rel):
        """Device pose / corners / pocket for arm config q, given the grasp transform rel."""
        prel, Rrel, comp_off, corners = rel
        p, R = self.R.ik.fk(q)
        Rd = R @ Rrel
        pd = p + R @ prel
        return pd, Rd, pd[None, :] + corners @ Rd.T, p + R @ comp_off

    def _roll_path(self, q_flip, rel, step_deg=5):
        """Joint path that rolls the device about its long axis (tool y = wrist-flex axis, roll ~ 0)
        with the TCP held fixed, from an upright pose (device up-axis z > 0.7) to q_flip. Both
        rotation directions are tried. Returns [q_upright, ..., q_flip] or None."""
        prel, Rrel, comp_off, corners = rel
        ik = self.R.ik
        bc = np.array(FLIP_AIM)
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        hb = BATTERY_BIN["size"][0] / 2 + 0.015
        p, R = ik.fk(q_flip)
        pocket = p + R @ comp_off
        yv = R[:, 1]
        half = 0.055 - 0.008                                       # pocket stays over the bin opening
        for sgn in (1, -1):
            path = [q_flip]
            q = q_flip
            ok = False
            for k in range(1, int(220 / step_deg) + 1):
                a_k = _rot(R[:, 2], yv, sgn * np.radians(step_deg * k))
                q, err, rerr = ik.solve(q, pocket, {2: a_k, 1: yv}, comp_off, iters=120)
                if err > 0.015 or rerr > 0.15:
                    break
                _, Rd, cw, comp = self._dev_geom(q, rel)
                over = np.all(np.abs(cw[:, :2] - bc) < hb, axis=1)
                if np.any(cw[:, 2] < np.where(over, top + 0.030, 0.015)):
                    break
                if Rd[2, 2] < 0.2 and np.abs(comp[:2] - bc).max() > half:
                    break
                if self.arm_collides(q) or np.abs(q - path[-1]).max() > np.radians(30):
                    break
                path.append(q)
                if Rd[2, 2] > self.upright_min:      # upright enough: freed cells stay in the pocket
                    ok = True
                    break
            if ok:
                return path[::-1]
        return None

    @staticmethod
    def cells_safe(Rd):
        """Freed cells rest loosely in the pocket with their + ends on the lip tops: they stay in while the
        device rolls <= 30 deg, tips rear-down <= 30 deg or front-down <= 20 deg (more and a loose cell slides off
        the lip top toward its spring and drops back under the lip)."""
        g = Rd.T @ np.array([0.0, 0.0, -1.0])               # gravity in the device frame
        if g[2] > -0.3:
            return False
        roll = np.degrees(np.arctan2(abs(g[1]), -g[2]))
        pitch = np.degrees(np.arctan2(g[0], -g[2]))          # > 0: front (spring end) down
        return roll <= 30.0 and -30.0 <= pitch <= 20.0

    def _upright_path(self, q0, q1, rel, n=25):
        """Joint-space segment check: the freed cells only rest loosely on the lip tops, so the device must stay
        within 30 deg of upright unless its pocket is already above the battery bin."""
        bc = np.array(FLIP_AIM)
        half = 0.055 - 0.025
        for t in np.linspace(0, 1, n):
            q = q0 + (q1 - q0) * t
            _, Rd_, cw_, comp = self._dev_geom(q, rel)
            over_bin = np.all(np.abs(comp[:2] - bc) < half)
            if over_bin:
                if Rd_[2, 2] < self.upright_min - 0.05:
                    return False
            elif not self.cells_safe(Rd_):
                return False
            if not self._clear_of_obstacles(cw_) or self.arm_collides(q):
                return False
        return True

    def _transit_route(self, q0, q_up, rel):
        """Waypoints from the lifted grasp pose to the roll start keeping the device upright and
        collision-free (direct, raised, swing-first variants). Returns list ending in q_up, or None."""
        ik = self.R.ik
        routes = [[q_up]]
        for rd in (15, 30, 45):
            raised0 = q0.copy(); raised0[1] -= np.radians(rd); raised0[3] += np.radians(rd)
            raised1 = q_up.copy(); raised1[1] -= np.radians(rd); raised1[3] += np.radians(rd)
            sw = raised0.copy(); sw[0] = q_up[0]
            routes += [[raised1, q_up], [raised0, sw, raised1, q_up], [raised0, raised1, q_up]]
        swing_first = q0.copy(); swing_first[0] = q_up[0]
        routes.append([swing_first, q_up])
        # carry poses: device kept upright (same approach as when lifted) with the pocket right above the bin
        prel, Rrel, comp_off, corners = rel
        bc = np.array(FLIP_AIM)
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        _, R0 = ik.fk(q0)
        for h in (0.06, 0.09, 0.12):
            for seed in (q0, q_up):
                qc, err, rerr = ik.solve(seed, [bc[0], bc[1], top + h], {2: R0[:, 2]}, comp_off, iters=300)
                if err > 0.004 or rerr > 0.05:
                    continue
                qr = qc.copy(); qr[1] -= np.radians(20); qr[3] += np.radians(20)
                r0 = q0.copy(); r0[1] -= np.radians(20); r0[3] += np.radians(20)
                routes += [[qc, q_up], [r0, qc, q_up], [r0, qr, qc, q_up]]
        for r in routes:
            pts = [q0] + r
            if all(np.all(ik.lo <= w) and np.all(w <= ik.hi) for w in r) and \
                    all(self._upright_path(pts[i], pts[i + 1], rel) for i in range(len(pts) - 1)):
                return r
        return None

    def plan_flip(self, rel, n=120000, seed=0):
        """Sample arm poses with wrist roll ~ 0 (tool y = wrist-flex axis = device long axis) where the
        device is >= 120 deg upside-down, clears the bin rim and has its pocket above the bin; keep the
        closest-to-centre one for which the in-place roll path from upright and an upright transit exist."""
        prel, Rrel, comp_off, corners = rel
        ik = self.R.ik
        bc = np.array(FLIP_AIM)
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        rng = np.random.default_rng(seed)
        lo, hi = ik.lo.copy(), ik.hi.copy()
        cands = []
        for _ in range(n):
            q = rng.uniform(lo, hi)
            q[4] = rng.uniform(-0.15, 0.15)
            pd, Rd, cw, comp = self._dev_geom(q, rel)
            if Rd[2, 2] > FLIP_MIN_UPZ or cw[:, 2].min() < top + 0.035 or comp[2] > top + 0.30:
                continue
            # the freed cells slide out through the pocket opening at ~90 deg of roll and keep some sideways
            # speed: aim the expected landing point (pocket + 4 cm along the opening's horizontal direction)
            # at the bin centre, and prefer low drops
            uh = Rd[:2, 2] / max(np.linalg.norm(Rd[:2, 2]), 1e-6)
            d = np.linalg.norm(comp[:2] + DROP_LEAD * uh - bc)
            if d < 0.045 and np.linalg.norm(comp[:2] - bc) < 0.05:
                cands.append((d + DROP_H_WEIGHT * (comp[2] - top), q))
        cands.sort(key=lambda c: c[0])
        stats = dict(n=len(cands), collide=0, roll=0, transit=0)
        self._plan_stats = stats
        for d, q0 in cands[:200]:
            if self.arm_collides(q0):
                stats["collide"] += 1
                continue
            # refined variant: pocket exactly above the centre, keeping the tool y axis and device up-axis
            p, R = ik.fk(q0)
            pd, Rd, cw, comp = self._dev_geom(q0, rel)
            uh = Rd[:2, 2] / max(np.linalg.norm(Rd[:2, 2]), 1e-6)
            aim = bc - DROP_LEAD * uh
            q2, err, rerr = ik.solve(q0, [aim[0], aim[1], comp[2]], {1: R[:, 1]}, comp_off,
                                     vecs=[(Rrel[:, 2], Rd[:, 2])], iters=200)
            variants = ([q2] if err < 0.005 and rerr < 0.05 else []) + [q0]
            for q in variants:
                if self.arm_collides(q):
                    continue
                path = self._roll_path(q, rel)
                if path is None:
                    stats["roll"] += 1
                    continue
                if self._transit_route(self.R.qcmd.copy(), path[0], rel) is None:
                    stats["transit"] += 1
                    continue
                pd, Rd, cw, comp = self._dev_geom(q, rel)
                return np.linalg.norm(comp[:2] - bc), path, comp, -np.degrees(np.arccos(np.clip(Rd[2, 2], -1, 1)))
        return None

    upright_min = 0.5

    def flip_over_bin(self):
        A, env = self.R, self.env
        p_tcp, R_tcp = A.tool((0, 0, 0))
        pd, Rd = self.device()
        comp = env.d.site("remote_comp").xpos.copy()
        corners = np.array([[sx * self.L_ / 2, sy * self.W / 2, z] for sx in (-1, 1) for sy in (-1, 1)
                            for z in (0.0, self.T)])
        rel = (R_tcp.T @ (pd - p_tcp), R_tcp.T @ Rd, R_tcp.T @ (comp - p_tcp), corners)
        plan = self.plan_flip(rel)
        if plan is None:
            self.say(f"[R] no reachable flip pose {getattr(self, '_plan_stats', '')}")
            return self.stage("flip_over_bin", False)
        sc, path, comp_w, ang = plan
        q_up, q_flip = path[0], path[-1]
        self.say(f"[R] flip plan: device turned {-ang:.0f} deg, pocket {1000*sc:.0f} mm from bin centre, z {comp_w[2]:.3f}")
        chosen = self._transit_route(A.qcmd.copy(), q_up, rel)
        self.say(f"[R] transit via {len(chosen) - 1} waypoint(s)")
        for w in chosen[:-1]:
            yield from A.goto_q(w, dur=1.4, settle=0.1)
        yield from A.goto_q(q_up, dur=2.0, settle=0.3)
        self.say(f"[R] after transit: grasp slip {1000*self.grasp_offset():.0f} mm, cells free {self.cells_free()}")
        cells_before = [env.d.body(f"remote_cell{i}").xpos.copy() for i in range(2)]
        for qk in path[1:]:                                    # roll the device about its long axis
            yield from A.goto_q(qk, dur=0.2, settle=0.0)
        yield from A.wait(0.4)
        pd, Rd = self.device()
        self.say(f"[R] at flip pose: device up-axis z {Rd[2,2]:.2f}, grasp slip {1000*self.grasp_offset():.0f} mm")
        for _ in range(3):                                     # gentle shake about the flex axis
            for dd in (+0.08, -0.08):
                qs = q_flip.copy()
                qs[3] = np.clip(qs[3] + dd, A.ik.lo[3], A.ik.hi[3])
                yield from A.goto_q(qs, dur=0.35, settle=0.0)
        yield from A.goto_q(q_flip, dur=0.35, settle=1.0)
        moved = [np.linalg.norm(env.d.body(f"remote_cell{i}").xpos - cells_before[i]) for i in range(2)]
        rep = env.success()
        self.say(f"[R] cells moved {np.round(np.array(moved)*1000,0)} mm, in bin {rep.cells_in_battery_bin}")
        # cells are out: lift the (still inverted) device straight up and away from the bin rim
        q_l, _, _ = A.ik.solve(A.qcmd.copy(), A.tool()[0] + [0, 0, 0.08], {}, iters=200)
        yield from A.goto_q(q_l, dur=1.3, settle=0.1)
        return self.stage("flip_over_bin", all(rep.cells_in_battery_bin))

    def drop_in_crate(self):
        """Carry the empty device over the blue crate (long axis along the crate's long side) and release."""
        A = self.R
        cc = np.array(BODY_CRATE["center"][:2])
        ctop = BODY_CRATE["center"][2] + BODY_CRATE["size"][2]
        self.say(f"[R] start crate transfer: device x-axis {np.round(self.device()[1][:, 0], 2)}, grip {self.env.grip_force('R'):.0f} N")
        yield from A.regulate_grip("remote_body", lo=20.0, hi=30.0)   # firm grip for the swing (cells are out)
        q_r = A.qcmd.copy()
        q_r[1] = max(A.ik.lo[1], q_r[1] - np.radians(30))     # raise first so the swing clears both bins
        yield from A.goto_q(q_r, dur=1.2)
        # drop point: search the crate interior (closer to the arm = reachable with the device level) for a pose
        # with the device's long axis (= tool y) horizontal along the crate's long side, low over the floor
        cx0_, cy0_ = BODY_CRATE["center"][:2]
        hx_, hy_ = BODY_CRATE["size"][0] / 2 - 0.02, BODY_CRATE["size"][1] / 2 - 0.01 - self.L_ / 2
        best = None
        for h in (0.025, 0.045, 0.07):
            for xx in np.linspace(cx0_ - hx_, cx0_ + hx_, 4):
                for yy in np.linspace(cy0_ - hy_, cy0_ + hy_, 3):
                    for axes, pen in (({2: DOWN, 1: (0, 1, 0)}, 0.0), ({2: DOWN, 1: (0, -1, 0)}, 0.0),
                                      ({1: (0, 1, 0)}, 0.002), ({1: (0, -1, 0)}, 0.002)):
                        for seed in (A.qcmd, HOME):
                            q, err, rerr = A.ik.solve(seed, [xx, yy, ctop + h], axes, iters=200)
                            _, Rq = A.ik.fk(q)
                            level = abs(Rq[2, 1])                     # device long axis must stay level
                            sc = err + pen + 0.03 * level + 0.002 * (h - 0.025) / 0.02
                            if best is None or sc < best[0]:
                                best = (sc, q, err)
        _, q_c, err = best
        self.say(f"[R] crate pose ik err {1000*err:.1f} mm")
        q_swing = A.qcmd.copy()
        q_swing[0] = q_c[0]
        yield from A.goto_q(q_swing, dur=2.2)
        self.say(f"[R] after swing: device x-axis {np.round(self.device()[1][:, 0], 2)}")
        yield from A.goto_q(q_c, dur=1.6, settle=0.3)
        self.say(f"[R] at crate pose: device x-axis {np.round(self.device()[1][:, 0], 2)}")
        yield from A.grip(GRIP_OPEN, 0.8)
        yield from A.wait(0.6)
        self.say(f"[R] released over the crate: device x-axis {np.round(self.device()[1][:, 0], 2)} at {np.round(self.device()[0], 3)}, jaw "
                 f"{self.env.d.qpos[A.io.gq]:.2f} rad, contact {self.env.grip_force('R'):.1f} N")
        q_up = A.qcmd.copy()
        q_up[1] = max(A.ik.lo[1], q_up[1] - np.radians(25))
        yield from A.goto_q(q_up, dur=0.8, settle=0.5)
        rep = self.env.success()
        self.say(f"[R] device at {np.round(self.device()[0],3)}, in crate: {rep.body_in_crate}")
        return self.stage("drop_in_crate", rep.body_in_crate)

    # ------------------------------------------------------------- L skills (pry tool)
    def tool_pose(self):
        return self.env.body_pose("pry_tool")

    def calibrate_tool(self):
        """Measure the tool pose in the hand (from the simulator state, like the device pose)."""
        pa, Ra = self.L.tcp_actual()
        pt, Rt = self.tool_pose()
        tip = self.env.d.site("pry_tip").xpos.copy()
        self.tool_rel = (Ra.T @ (tip - pa), Ra.T @ Rt)

    def tool_axes(self, Rt_des):
        """TCP axis targets that give the tool the world orientation Rt_des (given the measured grasp)."""
        _, Rrel = self.tool_rel
        Rtcp = Rt_des @ Rrel.T
        return {2: Rtcp[:, 2], 0: Rtcp[:, 0]}

    def pick_tool(self):
        """Grasp the handle just above its lower face, lift 4 mm and slide the tool out of the fork."""
        A = self.L
        pt, Rt = self.tool_pose()
        hy = Rt[:, 1]                                          # handle wide axis (across the foot direction)
        grasp_z = TOOL_RACK["plate_z"] + 0.013                 # fingertips 13 mm above the holder plate
        # jaws close across the 22 mm handle width: the bulky upper part of the fixed jaw then points sideways
        # (along y) and cannot hit the main arm, which holds the device just behind the pry notch
        off = np.array([0.0205 - HANDLE_D / 2 - 0.002, 0.0, 0.0])   # handle centre, 2 mm off the fixed jaw
        # TCP x = tool +y: while prying (tool y = device y) the wrist camera mount then faces +x, i.e. toward the
        # tool arm's own base and away from the main arm
        axes = {2: DOWN, 0: hy}
        c = pt[:2]
        # low approach from the open (-x) side of the fork: the jaws straddle the handle across y and slide in
        # along x (a high approach is out of the SO-101's vertical-approach workspace)
        e0 = yield from A.goto([c[0] - 0.06, c[1], grasp_z + 0.004], axes, off, grip=GRIP_OPEN, dur=1.5)
        e1 = yield from A.move([c[0], c[1], grasp_z], axes, off, speed=0.03, settle=0.1)
        self.say(f"[L] tool grasp ik err {1000*e0:.1f} / {1000*e1:.1f} mm")
        yield from A.compliant_close("pry_tool", 24.0)
        yield from A.move([c[0], c[1], grasp_z + 0.004], axes, off, speed=0.02, settle=0.1)
        yield from A.move([c[0] - 0.045, c[1], grasp_z + 0.004], axes, off, speed=0.04, settle=0.1)
        self.calibrate_tool()
        pt2, _ = self.tool_pose()
        ok = pt2[0] < TOOL_RACK["center"][0] - 0.035 and self.env.grip_force("L", "pry_tool") > 5.0
        self.say(f"[L] tool picked: tool at {np.round(pt2, 3)}, squeeze {self.env.grip_force('L', 'pry_tool'):.1f} N")
        return self.stage("pick_tool", ok)

    def tool_standby(self):
        """Hold the tool beside the jig (low, the SO-101 cannot point straight down when high) while the
        main arm prepares the device."""
        A = self.L
        Rt_des = lean_frame(np.eye(3))
        p = np.array([0.30, -0.10, 0.035])
        yield from A.goto(p, self.tool_axes(Rt_des), self.tool_rel[0], dur=1.5, settle=0.1)

    def pry_cells(self, attempt=0):
        """Pry tool skill (arm L): see module docstring, stage 4."""
        A, dm = self.L, self.dm
        self.calibrate_tool()
        p, R = self.device()
        axes = self.tool_axes(lean_frame(R))                   # foot -> device +x (level), handle leaning back
        axes_v = self.tool_axes(lean_frame(R, 0.0))            # upright blade: pushes the whole + end face
        off = self.tool_rel[0]
        cx0, cz, T = dm["cx0"], dm["cov_z0"], self.T
        # retries: shift sideways toward a cell that did not come free (the notch leaves +-1.5 mm of play)
        free0 = self.cells_free()
        yoff = 0.0
        if attempt > 0 and any(free0) and not all(free0):
            yoff = 0.0011 * (1 if not free0[1] else -1)          # cell1 at +y, cell0 at -y
        z_low = dm["slot_floor"] + 0.0011 + 0.0003 * attempt     # foot bottom 0.6 mm above the notch floor
        # push target: AA 6.2 mm; the light AAA cells only as far as needed (blade back face 0.3 mm past the lip end)
        # so that less spring energy is stored when their + ends come up
        unlatch = UNLATCH_SHIFT if dm["cell_r"] > 0.006 else dm["lip_len"] + 0.0011

        bias = np.zeros(3)      # commanded-vs-measured tip offset (servo sag, grasp compliance)

        def P(xb, z):           # device-local blade face x / tip-site z -> world target of the tip site
            return self.local(xb, yoff, z) + bias

        def correct(xb, z, n=3):
            """Closed-loop: measure the real tip (tool tracking) and re-aim until it is within 0.3 mm."""
            nonlocal bias
            for _ in range(n):
                err = self.local(xb, yoff, z) - self.env.d.site("pry_tip").xpos
                pa, Ra = A.tcp_actual(); pt_, Rt_ = self.tool_pose()
                cmd_tip = A.tool(off)[0]
                self.say(f"[L] tip correction {np.round(1000*err, 2)} mm; cmd tip - desired "
                         f"{np.round(1000*(cmd_tip - self.local(xb, yoff, z) - bias), 2)}; tool-in-hand rot change "
                         f"{np.degrees(np.arccos(np.clip((np.trace((Ra.T @ Rt_).T @ self.tool_rel[1]) - 1) / 2, -1, 1))):.1f} deg, "
                         f"tcp track err {1000*np.linalg.norm(pa - A.tool()[0]):.1f} mm")
                m_, d_ = self.env.m, self.env.d
                rb = self.env.arm_bodies["L"]
                for i in range(d_.ncon):
                    c = d_.contact[i]
                    b1, b2 = m_.geom_bodyid[c.geom1], m_.geom_bodyid[c.geom2]
                    if (b1 in rb) != (b2 in rb) and self.env.tool_bid not in (b1, b2):
                        self.say("      L contact:", m_.geom(c.geom1).name or m_.body(b1).name, "|",
                                 m_.geom(c.geom2).name or m_.body(b2).name, round(c.dist * 1000, 2))
                    if self.env.tool_bid in (b1, b2) and not ((b1 in rb) or (b2 in rb)):
                        self.say("      tool contact:", m_.geom(c.geom1).name or m_.body(b1).name, "|",
                                 m_.geom(c.geom2).name or m_.body(b2).name, round(c.dist * 1000, 2))
                if np.linalg.norm(pa - A.tool()[0]) > 0.003:
                    self.say("[L] arm is blocked: no tip correction")
                    break
                err = err * min(1.0, 0.008 / max(np.linalg.norm(err), 1e-9))
                if np.linalg.norm(err) < 0.0003:
                    break
                bias = bias + err
                yield from A.move(P(xb, z), axes, off, speed=0.01, min_time=0.1, settle=0.15)

        yield from A.goto(self.local(cx0 + 0.04, yoff, T + 0.012), axes, off, dur=1.2, settle=0.1)
        self.phase("pry_approach")
        x_in = cx0 - 0.0060                                     # foot tip 1 mm short of the + end faces
        if any(free0):
            # retry with one cell already free: its raised + end rests over the front of the notch, so enter at
            # the back of the notch (foot tip ~4.4 mm behind the stop) and push from there
            x_in = cx0 - 0.0090
        e0 = yield from A.move(P(x_in, T + 0.003), axes, off, speed=0.03, settle=0.1)
        # stand the blade upright ABOVE the notch (pushing with the top edge of a leaning blade would tip the
        # + ends up into the lip; re-orienting inside the 2 mm-wider notch would sweep the blade edge into its
        # side wall and shove the device), re-aim, then go straight down
        axes_push = axes
        yield from A.move(P(x_in, T + 0.003), axes_v, off, speed=0.02, min_time=0.6, settle=0.1)
        axes = axes_v
        yield from correct(x_in, T + 0.003)
        self.phase("pry_above")
        e1 = yield from A.move(P(x_in, z_low + 0.004), axes, off, speed=0.02, settle=0.15)
        yield from correct(x_in, z_low + 0.004)
        yield from A.move(P(x_in, z_low), axes, off, speed=0.01, settle=0.15)
        yield from correct(x_in, z_low)
        _, Rt_now = self.tool_pose()
        bx = R.T @ Rt_now[:, 0]
        self._blade_yaw = float(np.degrees(np.arctan2(bx[1], bx[0])))
        self.say(f"[L] blade yaw error {self._blade_yaw:+.1f} deg, tilt {np.degrees(np.arcsin(np.clip(bx[2], -1, 1))):+.1f} deg")
        self.phase("pry_inserted")
        # blade yaw feedback (wrist roll): unequal cell resistance twists the tool in the hand; a skewed blade
        # leaves the lagging cell's lip end over the blade's back face, which would then hook the lip on lifting
        ycorr = 0.0

        def blade_yaw():
            _, Rt_ = self.tool_pose()
            bx_ = R.T @ Rt_[:, 0]
            return float(np.arctan2(bx_[1], bx_[0]))

        def yaw_axes(lean_ang):
            nonlocal ycorr
            ycorr = float(np.clip(ycorr - 0.7 * blade_yaw(), -0.25, 0.25))
            c_, s_ = np.cos(ycorr), np.sin(ycorr)
            return self.tool_axes(lean_frame(R @ np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1]]), lean_ang))

        # push both cells into their springs (feedback on the + end positions)
        xb = x_in
        clear = dm["lip_len"] + 0.0012          # + end shift at which the blade's back face is past the lip end
        for _ in range(70):
            # stop on the measured cell shift; limit on the MEASURED tip (it lags the command under spring load)
            tip_x = float(R[:, 0] @ (self.env.d.site("pry_tip").xpos - p)) - cx0
            sh = [st[0] for st in self.cell_state()]
            if min(sh) > unlatch or tip_x > 0.0095:
                break
            if max(sh) > unlatch + 0.0015 and min(sh) > clear:
                break                     # slightly skewed blade: do not drive the leading cell to the stroke end
            if max(sh) > unlatch + 0.0035:
                break
            xb += 0.0005
            axes = yaw_axes(0.0)
            yield from A.move(P(xb, z_low), axes, off, speed=0.006, min_time=0.06, settle=0.03)
        self.say(f"[L] pushed, blade yaw {np.degrees(blade_yaw()):+.1f} deg (roll corr {np.degrees(ycorr):+.1f})")
        pushed = [st[0] for st in self.cell_state()]
        self.phase("pry_pushed")
        lifted = pushed
        if self.lift_cells:
            # lift the + ends above the lip top while the blade keeps the springs compressed; feedback on
            # the measured + end heights (the springs and cells load the tool, the servos sag)
            # lift in 1.5 mm steps (absolute heights) with feedback on both + end heights. Lateral: damped,
            # clamped correction of the measured tip y (keeps the foot centred under both cells) plus a small
            # shift toward a cell that lags behind.
            z = z_low
            ybal = 0.0
            lat = 0.0
            yd = R[:, 1]
            snags = 0
            p_ref, _ = self.device()          # device height with the cells pushed (reference for snag detection)
            for k in range(45):
                st = self.cell_state()
                b0, b1 = st[0][1], st[1][1]
                pn, Rn = self.device()
                if (pn - p_ref)[2] > 0.0008 or Rn[2, 2] < 0.998:
                    # the blade lifts the housing (caught under a lip): back down to the floor, push on, lift again
                    snags += 1
                    self.say(f"[L] snag {snags}: device raised {1000*(pn - p_ref)[2]:.1f} mm -> lower and push further")
                    if snags > 3:
                        break
                    z = z_low
                    if min(st[0][0], st[1][0]) < clear + 0.0005:
                        xb = min(xb + 0.001, cx0 + 0.0095)
                    yield from A.move(P(xb, z) + yd * ybal, yaw_axes(0.0), off, speed=0.01, min_time=0.3, settle=0.3)
                    continue
                if min(b0, b1) > cz + 0.0015:
                    break
                if max(b0, b1) > cz + 0.003:
                    # one cell is well above the lip top while the other lags: lifting (or waiting) further lets
                    # the high one slip over the blade; set the free one down now, the retry takes the other
                    break
                # the leaning blade pushes a rising + end further into its spring: do not let the cells go much
                # past the unlatch shift (spring stroke limit -> the - end would see-saw up); the blade's back face
                # must stay beyond the lip end (cx0 + lip + 0.3 mm)
                if min(st[0][0], st[1][0]) > unlatch and max(st[0][0], st[1][0]) > unlatch + 0.0012:
                    xb = max(xb - 0.0005, cx0 + dm["lip_len"] + 0.0003 + 0.0008)
                if abs(b0 - b1) > 0.002 and z > dm["floor"] + 0.004:
                    # one + end lags: hold the height and shift the foot toward it (cell1 is at +y) until level
                    ybal = float(np.clip(ybal + 0.0005 * np.sign(b0 - b1), -0.0025, 0.0025))
                else:
                    z = min(z + 0.0015, cz + 0.007)
                # lever back gradually (0 deg near the floor -> LEAN at the lip top): keeps the wrist inside its
                # flex range as the tool rises, without a sudden re-orientation under load
                frac = float(np.clip((z - dm["floor"] - 0.004) / max(cz - dm["floor"] - 0.004, 1e-3), 0, 1))
                axes = yaw_axes(LEAN * frac)
                tgt = self.local(xb, yoff, z) + yd * ybal
                eik = yield from A.move(tgt + bias + yd * lat, axes, off, speed=0.01, min_time=0.12, settle=0.1)
                ey = float(yd @ (tgt - self.env.d.site("pry_tip").xpos))
                # keep the foot centred: damped, clamped integral of the measured tip y error. The cells' curved
                # undersides push the foot sideways while it lifts them; a large wound-up correction would fling
                # the tool sideways when a cell pops free, so the integral is limited to 2 mm and bleeds off
                lat = float(np.clip(0.9 * lat + 0.4 * np.clip(ey, -0.0015, 0.0015), -0.002, 0.002))
                if self.verbose and self.on_phase is not None:
                    pa, _ = A.tcp_actual()
                    pa, Ra = A.tcp_actual(); _, Rt_ = self.tool_pose()
                    slip = np.degrees(np.arccos(np.clip((np.trace((Ra.T @ Rt_).T @ self.tool_rel[1]) - 1) / 2, -1, 1)))
                    tip_rel = Ra.T @ (self.env.d.site("pry_tip").xpos - pa)
                    self.say(f"      lift z {1000*z:.1f}: ik {1000*eik:.2f} mm, track {1000*np.linalg.norm(pa - A.tool()[0]):.2f} mm, "
                             f"tool slip {slip:.1f} deg / {1000*np.linalg.norm(tip_rel - off):.1f} mm, squeeze "
                             f"{self.env.grip_force('L', 'pry_tool'):.0f} N, springs "
                             f"{[round(1000*self.env.d.qpos[self.env.m.joint(f'remote_spring{i}').qposadr[0]],1) for i in range(2)]} mm, "
                             f"device {np.round(1000*self.device()[0],1)} up {np.round(self.device()[1][:, 2], 3)} tip {np.round(1000*self.env.d.site('pry_tip').xpos,1)}")
                    m_, d_ = self.env.m, self.env.d
                    f6 = np.zeros(6)
                    dev_ids = {m_.body(n).id for n in ("remote_body", "remote_plunger0", "remote_plunger1")}
                    fz = {}
                    for i in range(d_.ncon):
                        c = d_.contact[i]
                        b1, b2 = m_.geom_bodyid[c.geom1], m_.geom_bodyid[c.geom2]
                        if (b1 in dev_ids) == (b2 in dev_ids):
                            continue
                        mujoco.mj_contactForce(m_, d_, i, f6)
                        fw = c.frame.reshape(3, 3).T @ f6[:3]          # force on geom2's body, world frame
                        sign = 1.0 if b2 in dev_ids else -1.0
                        other = m_.body(b1 if b2 in dev_ids else b2).name
                        fz[other] = fz.get(other, 0.0) + sign * fw[2]
                        if other.startswith("remote_cell") and sign * fw[2] > 0.03:
                            gh = m_.geom(c.geom2 if b2 in dev_ids else c.geom1).name or "?"
                            pl_ = self.device()[1].T @ (c.pos - self.device()[0])
                            self.say(f"            {other} pushes {gh} up {sign*fw[2]:.2f} N at dev {np.round(1000*pl_,1)} mm")
                    self.say("         Fz on housing by: " + ", ".join(f"{k} {v:+.2f}" for k, v in fz.items() if abs(v) > 0.05))
                    rbL = self.env.arm_bodies["L"]
                    for i in range(d_.ncon):
                        c = d_.contact[i]
                        b1, b2 = m_.geom_bodyid[c.geom1], m_.geom_bodyid[c.geom2]
                        if (b1 in rbL) != (b2 in rbL) and self.env.tool_bid not in (b1, b2):
                            self.say(f"         armL contact: {m_.geom(c.geom1).name or m_.body(b1).name} | {m_.geom(c.geom2).name or m_.body(b2).name}")
                self.phase("pry_lift_step")
            bias = bias + yd * lat
            lifted = self.cell_state()
            self.phase("pry_lifted")
            # let the springs push the raised cells back over the lip top, set them down on it
            # the foot (bottom 0.5 mm below the tip site) must pass over the lip end: >= 1 mm above the lip top
            z = max(z, cz + 0.0015)
            yield from A.move(P(xb, z) + yd * ybal, axes, off, speed=0.006, min_time=0.1, settle=0.05)
            e_sb = yield from A.move(P(cx0 + 0.001, z) + yd * ybal, axes, off, speed=0.006, settle=0.1)
            if self.on_phase is not None:
                pa, _ = A.tcp_actual()
                self.say(f"      slide back: ik {1000*e_sb:.1f} mm, track {1000*np.linalg.norm(pa - A.tool()[0]):.1f} mm, "
                         f"cmd tip {np.round(1000*(R.T @ (A.tool(off)[0] - p)) - [1000*cx0, 0, 0], 1)}")
            self.phase("pry_slid_back")
            yield from A.move(P(cx0 + 0.001, cz - 0.0035), axes, off, speed=0.006, settle=0.1)
            self.phase("pry_set_down")
            yield from A.move(P(cx0 - 0.0088, cz - 0.0035), axes, off, speed=0.008, settle=0.1)
            axes = axes_push
        else:                    # ablation: push only, then withdraw
            yield from A.move(P(x_in, z_low), axes, off, speed=0.006, settle=0.1)
            axes = axes_push
            yield from A.move(P(x_in, z_low), axes, off, speed=0.02, min_time=0.6, settle=0.1)
            yield from A.move(P(cx0 - 0.0088, z_low), axes, off, speed=0.006, settle=0.1)
        yield from A.move(P(cx0 - 0.0088, T + 0.004), axes, off, speed=0.02, settle=0.1)
        # leave sideways (-y, toward the tool holder): the raised + ends now stick up above the device top
        yield from A.move(self.local(cx0 - 0.0088, -(self.W / 2 + 0.02), T + 0.006), axes, off, speed=0.03, settle=0.3)
        self.phase("pry_done")
        st = self.cell_state()
        free = self.cells_free()
        self.say(f"[L] pry: ik {1000*max(e0, e1):.1f} mm, pushed {np.round(np.array(pushed)*1000,1)} mm, "
                 f"lifted {[(round(1000*s[0],1), round(1000*s[1],1), round(s[2],1)) for s in lifted] if self.lift_cells else '-'}, "
                 f"final (+end x, z mm, tilt) {[(round(1000*s[0],1), round(1000*s[1],1), round(s[2],1)) for s in st]}, free {free}")
        return self.stage("pry_cells", all(free))

    def tool_retreat(self):
        """Move the tool away from the device to the holder's entry side (clears the main arm's re-grasp)."""
        A = self.L
        self.calibrate_tool()
        Rt_des = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1.0]])
        cx, cy = TOOL_RACK["center"]
        yield from A.goto([cx - 0.0004 - 0.045, cy, 0.03], self.tool_axes(lean_frame(Rt_des, -LEAN)), self.tool_rel[0],
                          dur=1.6, settle=0.1)               # clear of the jig fence (leaning: reachable)
        self._tool_retreated = True

    def return_tool(self):
        """Slide the tool back into the fork holder (handle 4 mm above the plate), lower it, let go."""
        A = self.L
        self.calibrate_tool()                                 # the tool may have turned a little in the hand
        Rt_des = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1.0]])   # foot -> world -x, as it was in the holder
        axes = self.tool_axes(Rt_des)
        off = self.tool_rel[0]
        cx, cy = TOOL_RACK["center"]
        tip_x = cx - 0.0004                                    # tip site sits 0.4 mm toward the foot side
        rest = TOOL_RACK["plate_z"] + 0.0005 - TOOL_LEN["tip_to_collar"]
        if not getattr(self, "_tool_retreated", False):
            yield from self.tool_retreat()
        entry = np.array([tip_x - 0.045, cy, rest + 0.004])
        yield from A.move(entry, axes, off, speed=0.03, settle=0.1)
        self.phase("ret_entry")
        bias = np.zeros(3)
        for _ in range(3):                                    # closed loop on the measured tip before sliding in
            err = entry - self.env.d.site("pry_tip").xpos
            if np.linalg.norm(err) < 0.0004:
                break
            bias += np.clip(err, -0.008, 0.008)
            yield from A.move(entry + bias, axes, off, speed=0.01, min_time=0.1, settle=0.15)
        yield from A.move([tip_x, cy, rest + 0.004] + bias, axes, off, speed=0.03, settle=0.1)
        self.phase("ret_slid_in")
        yield from A.move([tip_x, cy, rest] + bias, axes, off, speed=0.01, settle=0.2)
        self.phase("ret_lowered")
        yield from A.grip(GRIP_OPEN, 0.6)
        self.phase("ret_released")
        yield from A.move(A.tool()[0] + [0, 0, 0.03], {}, speed=0.05, settle=0.2)
        self.phase("ret_up")
        pt, _ = self.tool_pose()
        ok = abs(pt[0] - cx) < 0.006 and abs(pt[1] - cy) < 0.006 and pt[2] < TOOL_RACK["plate_z"]
        self.say(f"[L] tool returned to the holder: {ok} (tool at {np.round(pt, 3)})")
        yield from A.home(1.2)
        return self.stage("return_tool", ok)

    # ------------------------------------------------------------- run
    def _main_prep(self):
        ok = yield from self.push_to_fence()
        if ok:
            ok = yield from self.slide_cover()
            if not ok:
                ok = yield from self.slide_cover(attempt=1)
        if ok:
            yield from self.push_to_fence(name="reseat_on_fence")   # the device must be braced by the fence
        return ok

    def _tool_prep(self):
        ok = yield from self.pick_tool()
        if not ok:
            yield from self.L.grip(GRIP_OPEN, 0.4)
            yield from self.L.move(self.L.tool()[0] + [0, 0, 0.05], {2: DOWN})
            ok = yield from self.pick_tool()
        if ok:
            yield from self.L.wait(0.5)
        return ok

    def release_device(self):
        """Open the hold grasp and back off upward (before re-grasping at the centre of mass)."""
        A = self.R
        yield from A.grip(GRIP_OPEN, 0.5)
        yield from A.move(A.tool(self.grasp_off)[0] + [0, 0, 0.04], self._grasp_axes, self.grasp_off, speed=0.06,
                          settle=0.1)
        self._holding = False

    def _regrasp_lift(self):
        if getattr(self, "_holding", False):
            yield from self.release_device()
        ok = yield from self.grasp_device()
        if not ok:
            yield from self.R.grip(GRIP_OPEN, 0.4)
            yield from self.R.move(self.R.tool()[0] + [0, 0, 0.05], {2: DOWN})
            ok = yield from self.grasp_device()
        return ok

    def _after_pry(self, lifted=None):
        ok = (yield from self._regrasp_lift()) if lifted is None else lifted
        if ok:
            ok = yield from self.flip_over_bin()
        if ok or self.env.success().cells_in_battery_bin.count(True) > 0:
            yield from self.drop_in_crate()
        yield from self.R.home()
        return ok

    def run(self):
        env = self.env
        if self.use_tool:
            ok, tool_ok = self.run_par(self._main_prep(), self._tool_prep())
        else:
            ok, tool_ok = self.run_par(self._main_prep()), False
        if ok and tool_ok:
            self.run_par(self.tool_standby())
            if self.hold:                                       # hold the device firmly on the jig by its rear end
                self.run_par(self.grasp_device(lift=False, gx=self.dm["hold_x"], lean=R_LEAN))
            pried = False
            for k in range(3):
                pried = self.run_par(self.pry_cells(attempt=k))
                if pried:
                    break
            self.run_par(self.tool_retreat())                     # tool arm leaves before the main arm re-grasps
            lifted = self.run_par(self._regrasp_lift())
            self.run_par(self._after_pry(lifted), self.return_tool())
        elif ok:                      # ablation without the tool: go straight to grasp + flip
            self.run_par(self._after_pry())
        else:
            self.run_par(self.R.home(), self.L.home())
        return env.success()
