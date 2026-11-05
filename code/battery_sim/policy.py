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
from battery_sim.scene import BATTERY_BIN, BODY_CRATE, FENCE_X, TOOL_FOOT_ANGLE, TOOL_LEN, TOOL_RACK

DT = 0.02                                   # control period (50 Hz)
PRESS_OFF = np.array([0.012, 0.0, 0.004])   # contact point of the closed jaw tips (tool frame)
DOWN = np.array([0.0, 0.0, -1.0])
GRASP_DEPTH = 0.016                         # fingertips this far below the device top (device is 22 mm thick)
HANDLE_W = 0.011                            # pry-tool handle thickness across the jaws
UNLATCH_SHIFT = 0.0052                      # push the cells this far into their springs (lip overhang 4.5 mm)
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

    # -------------------------------------------------------------- helpers
    def tool(self, offset=(0, 0, 0)):
        return self.ik.fk(self.qcmd, offset)

    def tcp_actual(self):
        s = self.env.d.site(self.io.site)
        return s.xpos.copy(), s.xmat.reshape(3, 3).copy()

    def set(self, q, g=None):
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
        self.grip_cmd = value
        yield from self.wait(t)

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
        self.grasp_depth = GRASP_DEPTH if self.T >= 0.022 else self.T - 0.0071
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
        """A cell is free when its + end has been lifted onto the top of the retaining lip."""
        return [st[1] > self.dm["cov_z0"] - 0.0005 for st in self.cell_state()]

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
        for k in range(4):                                   # drag in segments, re-pressing each time
            tgt = ridge + x * (0.022 * (k + 1)) - [0, 0, press]
            yield from A.move(tgt, axes, PRESS_OFF, speed=0.025, settle=0.05)
        yield from A.move(A.tool(PRESS_OFF)[0] + [0, 0, 0.06], axes, PRESS_OFF, speed=0.08, settle=0.4)
        off, dz = self.cover_offset()
        self.say(f"[R] latch released: {self.env.log.latch_released_at is not None}, cover offset {1000*off:.1f} mm, "
                 f"dz {1000*dz:.1f} mm")
        return self.stage("slide_cover", off > 0.050 or dz < -0.005 or dz > 0.03)

    def hold_device(self):
        """Press the rear end of the device down onto the jig with the closed jaw tips (the other hand
        pries); the device is braced against the fence along +x."""
        A = self.R
        p, R = self.device()
        pt = p + R @ [-self.L_ / 2 + 0.011, 0, self.T]
        axes = {2: DOWN, 0: -R[:, 1]}            # wrist camera mount faces away from the tool arm
        yield from A.goto(pt + [0, 0, 0.03], axes, PRESS_OFF, grip=GRIP_CLOSED)
        e = yield from A.move(pt - [0, 0, 0.002], axes, PRESS_OFF, speed=0.03, settle=0.2)
        self.say(f"[R] holding the device down at its rear end (ik {1000*e:.1f} mm)")
        return self.stage("hold_device", e < 0.005)

    def release_hold(self):
        A = self.R
        yield from A.move(A.tool(PRESS_OFF)[0] + [0, 0, 0.05], {2: DOWN}, PRESS_OFF, speed=0.06, settle=0.05)

    def grasp_device(self):
        A = self.R
        p, R = self.device()
        x, y = R[:, 0], R[:, 1]
        c = p + R @ [self.grasp_x, 0, 0]                      # just behind the pocket, near the centre of mass
        top = p[2] + self.T
        axes = {2: DOWN, 0: y if y[1] < 0 else -y}           # jaw orientation nearer to the arm's natural roll
        yield from A.goto([c[0], c[1], top + 0.05], axes, self.grasp_off, grip=GRIP_OPEN)
        yield from A.move([c[0], c[1], top - self.grasp_depth], axes, self.grasp_off, speed=0.04, settle=0.1)
        yield from A.compliant_close("remote_body", 33.0)
        yield from A.move([c[0], c[1], 0.12], axes, self.grasp_off, speed=0.06, settle=0.3)
        pd, _ = self.device()
        lifted = pd[2] > 0.06
        pa, Ra = A.tcp_actual()
        self._grasp_rel = Ra.T @ (pd - pa)
        self.say(f"[R] device lifted to z={pd[2]:.3f}, squeeze {self.env.grip_force('R'):.1f} N, cells free {self.cells_free()}")
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

    def _roll_path(self, q_flip, rel, step_deg=10):
        """Joint path that rolls the device about its long axis (tool y = wrist-flex axis, roll ~ 0)
        with the TCP held fixed, from an upright pose (device up-axis z > 0.7) to q_flip. Both
        rotation directions are tried. Returns [q_upright, ..., q_flip] or None."""
        prel, Rrel, comp_off, corners = rel
        ik = self.R.ik
        bc = np.array(BATTERY_BIN["center"][:2])
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        hb = BATTERY_BIN["size"][0] / 2 + 0.015
        p, R = ik.fk(q_flip)
        pocket = p + R @ comp_off
        yv = R[:, 1]
        half = BATTERY_BIN["size"][0] / 2 - 0.02
        for sgn in (1, -1):
            path = [q_flip]
            q = q_flip
            ok = False
            for k in range(1, int(220 / step_deg) + 1):
                a_k = _rot(R[:, 2], yv, sgn * np.radians(step_deg * k))
                q, err, rerr = ik.solve(q, pocket, {2: a_k, 1: yv}, comp_off, iters=120)
                if err > 0.015 or rerr > 0.08:
                    break
                _, Rd, cw, comp = self._dev_geom(q, rel)
                over = np.all(np.abs(cw[:, :2] - bc) < hb, axis=1)
                if np.any(cw[:, 2] < np.where(over, top + 0.030, 0.015)):
                    break
                if Rd[2, 2] < 0.2 and np.abs(comp[:2] - bc).max() > half:
                    break
                if self.arm_collides(q) or np.abs(q - path[-1]).max() > np.radians(25):
                    break
                path.append(q)
                if Rd[2, 2] > self.upright_min:      # upright enough: freed cells stay in the pocket
                    ok = True
                    break
            if ok:
                return path[::-1]
        return None

    def _upright_path(self, q0, q1, rel, n=25):
        for t in np.linspace(0, 1, n):
            q = q0 + (q1 - q0) * t
            _, Rd_, cw_, _ = self._dev_geom(q, rel)
            if Rd_[2, 2] < self.upright_min - 0.05 or not self._clear_of_obstacles(cw_) or self.arm_collides(q):
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
        for r in routes:
            pts = [q0] + r
            if all(np.all(ik.lo <= w) and np.all(w <= ik.hi) for w in r) and \
                    all(self._upright_path(pts[i], pts[i + 1], rel) for i in range(len(pts) - 1)):
                return r
        return None

    def plan_flip(self, rel, n=60000, seed=0):
        """Sample arm poses with wrist roll ~ 0 (tool y = wrist-flex axis = device long axis) where the
        device is >= 120 deg upside-down, clears the bin rim and has its pocket above the bin; keep the
        closest-to-centre one for which the in-place roll path from upright exists."""
        prel, Rrel, comp_off, corners = rel
        ik = self.R.ik
        bc = np.array(BATTERY_BIN["center"][:2])
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        rng = np.random.default_rng(seed)
        lo, hi = ik.lo.copy(), ik.hi.copy()
        cands = []
        for _ in range(n):
            q = rng.uniform(lo, hi)
            q[4] = rng.uniform(-0.15, 0.15)
            pd, Rd, cw, comp = self._dev_geom(q, rel)
            if Rd[2, 2] > -0.5 or cw[:, 2].min() < top + 0.035 or comp[2] > top + 0.30:
                continue
            d = np.linalg.norm(comp[:2] - bc)
            if d < 0.04:
                cands.append((d, q))
        cands.sort(key=lambda c: c[0])
        for d, q in cands[:80]:
            if self.arm_collides(q):
                continue
            # refine: pocket exactly above the centre, keeping the tool y axis and device up-axis
            p, R = ik.fk(q)
            pd, Rd, cw, comp = self._dev_geom(q, rel)
            q2, err, rerr = ik.solve(q, [bc[0], bc[1], comp[2]], {1: R[:, 1]}, comp_off,
                                     vecs=[(Rrel[:, 2], Rd[:, 2])], iters=200)
            if err < 0.005 and rerr < 0.05:
                q = q2
            if self.arm_collides(q):
                continue
            path = self._roll_path(q, rel)
            if path is None:
                continue
            if self._transit_route(self.R.qcmd.copy(), path[0], rel) is None:
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
            self.say("[R] no reachable flip pose")
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
            yield from A.goto_q(qk, dur=0.35, settle=0.0)
        yield from A.wait(0.4)
        pd, Rd = self.device()
        self.say(f"[R] at flip pose: device up-axis z {Rd[2,2]:.2f}, grasp slip {1000*self.grasp_offset():.0f} mm")
        for _ in range(3):                                     # gentle shake about the flex axis
            for dd in (+0.10, -0.10):
                qs = q_flip.copy()
                qs[3] = np.clip(qs[3] + dd, A.ik.lo[3], A.ik.hi[3])
                yield from A.goto_q(qs, dur=0.25, settle=0.0)
        yield from A.goto_q(q_flip, dur=0.25, settle=1.0)
        moved = [np.linalg.norm(env.d.body(f"remote_cell{i}").xpos - cells_before[i]) for i in range(2)]
        rep = env.success()
        self.say(f"[R] cells moved {np.round(np.array(moved)*1000,0)} mm, in bin {rep.cells_in_battery_bin}")
        # cells are out: lift the (still inverted) device straight up and away from the bin rim
        q_l, _, _ = A.ik.solve(A.qcmd.copy(), A.tool()[0] + [0, 0, 0.08], {}, iters=200)
        yield from A.goto_q(q_l, dur=0.8, settle=0.1)
        return self.stage("flip_over_bin", all(rep.cells_in_battery_bin))

    def drop_in_crate(self):
        """Carry the empty device over the blue crate (long axis along the crate's long side) and release."""
        A = self.R
        cc = np.array(BODY_CRATE["center"][:2])
        ctop = BODY_CRATE["center"][2] + BODY_CRATE["size"][2]
        q_r = A.qcmd.copy()
        q_r[1] = max(A.ik.lo[1], q_r[1] - np.radians(30))     # raise first so the swing clears both bins
        yield from A.goto_q(q_r, dur=0.8)
        best = None
        for h in (0.05, 0.07, 0.09):
            for axes in ({2: DOWN, 1: (0, 1, 0)}, {2: DOWN, 1: (0, -1, 0)}, {2: DOWN}, {}):
                for seed in (A.qcmd, HOME):
                    q, err, rerr = A.ik.solve(seed, [cc[0], cc[1], ctop + h], axes, iters=300)
                    pen = 0.0 if len(axes) == 2 else (0.004 if len(axes) == 1 else 0.008)
                    sc = err + pen + 0.002 * (h - 0.05) / 0.02
                    if best is None or sc < best[0]:
                        best = (sc, q, err)
        _, q_c, err = best
        self.say(f"[R] crate pose ik err {1000*err:.1f} mm")
        q_swing = A.qcmd.copy()
        q_swing[0] = q_c[0]
        yield from A.goto_q(q_swing, dur=1.4)
        yield from A.goto_q(q_c, dur=1.2, settle=0.3)
        yield from A.grip(GRIP_OPEN, 0.8)
        yield from A.wait(0.6)
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
        hx = Rt[:, 0]                                          # handle thin axis (= foot direction)
        grasp_z = TOOL_RACK["plate_z"] + 0.013                 # fingertips 13 mm above the holder plate
        off = np.array([0.0205 - HANDLE_W / 2 - 0.002, 0.0, 0.0])   # handle centre, 2 mm off the fixed jaw
        best = None
        for ax in ({2: DOWN, 0: -hx}, {2: DOWN, 0: hx}):
            q, err, rerr = A.solve_best([pt[0], pt[1], grasp_z], ax, off)
            if best is None or err + 0.02 * rerr < best[0]:
                best = (err + 0.02 * rerr, ax)
        axes = best[1]
        c = pt[:2]
        # low sideways approach (the jaws straddle the handle across x and slide in along y): a high
        # approach is out of the SO-101's vertical-approach workspace and would sweep the tool over
        e0 = yield from A.goto([c[0], c[1] + 0.06, grasp_z + 0.004], axes, off, grip=GRIP_OPEN, dur=1.5)
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
                if np.linalg.norm(err) > 0.004:
                    self.say("[L] tip error too large to correct (blocked?)")
                    break
                if np.linalg.norm(err) < 0.0003:
                    break
                bias = bias + err
                yield from A.move(P(xb, z), axes, off, speed=0.01, min_time=0.1, settle=0.15)

        yield from A.goto(self.local(cx0 + 0.04, yoff, T + 0.012), axes, off, dur=1.2, settle=0.1)
        x_in = cx0 - 0.0060                                     # foot tip 1 mm short of the + end faces
        e0 = yield from A.move(P(x_in, T + 0.003), axes, off, speed=0.03, settle=0.1)
        yield from correct(x_in, T + 0.003)
        e1 = yield from A.move(P(x_in, z_low), axes, off, speed=0.03, settle=0.15)
        # stand the blade upright (pushing with the top edge of a leaning blade would tip the + ends up
        # into the lip), then re-aim
        yield from A.move(P(x_in, z_low), axes_v, off, speed=0.02, min_time=0.6, settle=0.1)
        axes_push = axes
        axes = axes_v
        yield from correct(x_in, z_low)
        self.phase("pry_inserted")
        # push both cells into their springs (feedback on the + end positions)
        xb = x_in
        while xb < cx0 + 0.0085:
            xb += 0.0005
            yield from A.move(P(xb, z_low), axes, off, speed=0.006, min_time=0.06, settle=0.03)
            if min(st[0] for st in self.cell_state()) > UNLATCH_SHIFT:
                break
        pushed = [st[0] for st in self.cell_state()]
        self.phase("pry_pushed")
        lifted = pushed
        if self.lift_cells:
            # lift the + ends above the lip top while the blade keeps the springs compressed; feedback on
            # the measured + end heights (the springs and cells load the tool, the servos sag)
            axes = axes_push                                    # lever back while lifting
            # lift in 1.5 mm steps; feedback on both + end heights: keep the foot centred in the notch
            # (measured tip) and shift it toward a cell that lags behind
            z = z_low
            ybal = 0.0
            for k in range(30):
                st = self.cell_state()
                b0, b1 = st[0][1], st[1][1]
                if min(b0, b1) > cz + 0.0015:
                    break
                if k > 2 and abs(b0 - b1) > 0.002:
                    ybal = float(np.clip(ybal + 0.0004 * np.sign(b0 - b1), -0.0015, 0.0015))  # cell1 is at +y
                z = min(z + 0.0015, cz + 0.006)
                yield from A.move(P(xb, z) + R[:, 1] * ybal, axes, off, speed=0.01, min_time=0.12, settle=0.1)
                err = self.local(xb, yoff, z) + R[:, 1] * ybal - self.env.d.site("pry_tip").xpos
                bias = bias + R[:, 1] * (R[:, 1] @ err) + R[:, 2] * np.clip(R[:, 2] @ err, -0.001, 0.003)
                self.phase("pry_lift_step")
            lifted = self.cell_state()
            self.phase("pry_lifted")
            # let the springs push the raised cells back over the lip top, set them down on it
            yield from A.move(P(cx0 + 0.001, z) + R[:, 1] * ybal, axes, off, speed=0.006, settle=0.1)
            yield from A.move(P(cx0 + 0.001, cz - 0.0035), axes, off, speed=0.006, settle=0.1)
            self.phase("pry_set_down")
            yield from A.move(P(cx0 - 0.011, cz - 0.0035), axes, off, speed=0.008, settle=0.1)
        else:                    # ablation: push only, then withdraw
            yield from A.move(P(x_in, z_low), axes, off, speed=0.006, settle=0.1)
            axes = axes_push
            yield from A.move(P(x_in, z_low), axes, off, speed=0.02, min_time=0.6, settle=0.1)
            yield from A.move(P(cx0 - 0.011, z_low), axes, off, speed=0.006, settle=0.1)
        yield from A.move(P(cx0 - 0.011, T + 0.004), axes, off, speed=0.02, settle=0.1)
        yield from A.move(self.local(cx0 + 0.04, 0, T + 0.012), axes, off, speed=0.04, settle=0.3)
        self.phase("pry_done")
        st = self.cell_state()
        free = self.cells_free()
        self.say(f"[L] pry: ik {1000*max(e0, e1):.1f} mm, pushed {np.round(np.array(pushed)*1000,1)} mm, "
                 f"lifted {[(round(1000*s[0],1), round(1000*s[1],1), round(s[2],1)) for s in lifted] if self.lift_cells else '-'}, "
                 f"final (+end x, z mm, tilt) {[(round(1000*s[0],1), round(1000*s[1],1), round(s[2],1)) for s in st]}, free {free}")
        return self.stage("pry_cells", all(free))

    def return_tool(self):
        """Slide the tool back into the fork holder (handle 4 mm above the plate), lower it, let go."""
        A = self.L
        Rt_des = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1.0]])   # foot -> world -x, as it was in the holder
        axes = self.tool_axes(Rt_des)
        off = self.tool_rel[0]
        cx, cy = TOOL_RACK["center"]
        tip_x = cx - 0.0006                                    # tip site sits 0.6 mm toward the foot side
        rest = TOOL_RACK["plate_z"] + 0.0005 - TOOL_LEN["tip_to_collar"]
        yield from A.goto([tip_x - 0.045, cy, 0.03], self.tool_axes(lean_frame(Rt_des, -LEAN)), off, dur=1.6,
                          settle=0.1)                          # clear of the jig fence (leaning: reachable)
        yield from A.move([tip_x - 0.045, cy, rest + 0.004], axes, off, speed=0.03, settle=0.1)
        yield from A.move([tip_x, cy, rest + 0.004], axes, off, speed=0.03, settle=0.1)
        yield from A.move([tip_x, cy, rest], axes, off, speed=0.01, settle=0.2)
        yield from A.grip(GRIP_OPEN, 0.6)
        yield from A.move(A.tool()[0] + [0, 0, 0.03], {}, speed=0.05, settle=0.2)
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

    def _after_pry(self):
        ok = yield from self.grasp_device()
        if not ok:
            yield from self.R.grip(GRIP_OPEN, 0.4)
            yield from self.R.move(self.R.tool()[0] + [0, 0, 0.05], {2: DOWN})
            ok = yield from self.grasp_device()
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
            if self.hold:
                self.run_par(self.hold_device())
            pried = False
            for k in range(3):
                pried = self.run_par(self.pry_cells(attempt=k))
                if pried:
                    break
            if self.hold:
                self.run_par(self.release_hold())
            self.run_par(self._after_pry(), self.return_tool())
        elif ok:                      # ablation without the tool: go straight to grasp + flip
            self.run_par(self._after_pry())
        else:
            self.run_par(self.R.home(), self.L.home())
        return env.success()
