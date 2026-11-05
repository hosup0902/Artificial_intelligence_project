"""Skill-based scripted policy (state machine) for the battery-removal task.

Skills are Cartesian motions solved with DLS IK each control tick (50 Hz) and sent to the
SO-101 position servos. Every stage ends with a state check; failed checks trigger a
bounded retry, otherwise the episode aborts with the failing stage recorded.

Stages
  1. push_to_fence   closed gripper behind the device's rear face, push +x until the
                     device's front end touches the jig's aluminium fence.
  2. slide_cover     press the cover grip ridges and drag along device +x: the latch
                     releases (env), the cover slides out and drops off past the fence.
  3. grasp_device    top grasp of the solid rear section across the device width.
  4. flip_over_bin   carry the battery pocket over the red bin, keep the device's long
                     axis tangential (= wrist-flex axis), tilt the approach ~125 deg so the
                     device rolls over about its long axis, shake: cells drop into the bin.
  5. drop_in_crate   carry the empty device over the blue crate and release it.
"""

from __future__ import annotations

import mujoco
import numpy as np

from battery_sim.env import GRIP_CLOSED, GRIP_OPEN, HOME, BatteryRemovalEnv
from battery_sim.ik import IK
from battery_sim.scene import BATTERY_BIN, BODY_CRATE, FENCE_X, JIG_TOP

L, W, T = 0.180, 0.050, 0.022           # remote dimensions (devices.RemoteSpec)
DT = 0.02                               # control period (50 Hz)
PRESS_OFF = np.array([0.012, 0.0, 0.004])   # contact point of the closed jaw tips (tool frame)
GRASP_OFF = np.array([-0.005, 0.0, 0.0])    # centre between the jaws for a 50 mm-wide object
DOWN = np.array([0.0, 0.0, -1.0])
GRASP_X = -0.030            # device-local x of the grasp: solid rear section, clear of the finger slot (starts at -0.0075)
# Closed-jaw collision meshes, tool x -> -x_dev (moving jaw leads into the finger slot). This tool-frame
# point is on the moving jaw 2.5 mm above the tool origin; with the point 5 mm above the cell axis the
# jaw bottom clears the slot floor and the jaw pushes the upper half of both + end faces.
PUSH_OFF = np.array([0.0057, 0.0, -0.0025])
PUSH_H = 0.005
UNLATCH_SHIFT = 0.0053      # push the cells this far into their springs (lip overhang is 4.5 mm)
LIP_LEN = 0.0045            # retaining lip overhang (devices.LIP_LEN)
LIP_Z0 = 0.019              # lip underside, device-local z
GRASP_DEPTH = 0.016         # fingertips this far below the device top (device is 22 mm thick)


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


class SkillPolicy:
    def __init__(self, env: BatteryRemovalEnv, verbose=True):
        self.env = env
        self.ik = IK(env.m)
        self.verbose = verbose
        self.qcmd = env.q
        self.grip_cmd = 0.0
        dm = env.dims
        self.L, self.W, self.T = dm["L"], dm["W"], dm["T"]
        self.grasp_x = dm["grasp_x"]
        self.grasp_off = np.array([0.02 - self.W / 2, 0.0, 0.0])   # fixed jaw tip at tool x = +0.02
        # jaw bottom is 6.6 mm below the tool origin: keep it >= 0.5 mm above the tray for thinner devices
        self.grasp_depth = GRASP_DEPTH if self.T >= 0.022 else self.T - 0.0071
        self.push_h = dm["push_h"]
        # seated cover position along the device x axis and its half length (from the model)
        p, R = env.body_pose("remote_body")
        pc, _ = env.body_pose("remote_cover")
        self.cover_seat = float(R[:, 0] @ (pc - p))
        self.cover_hx = float(env.m.geom_size[env.m.geom("remote_cover_plate").id][0])
        self._cell_seat = [float(R[:, 0] @ (env.body_pose(f"remote_cell{i}")[0] - p)) for i in range(2)]
        self._cell_tilt0 = [0.0, 0.0]
        self._cell_tilt0 = [c[1] for c in self._cell_state()]

    # ------------------------------------------------------------- primitives
    def say(self, *a):
        if self.verbose:
            print(f"  [{self.env.d.time:6.2f}s]", *a)

    def tool(self, offset):
        return self.ik.fk(self.qcmd, offset)

    def move(self, target, axes=None, offset=(0, 0, 0), grip=None, speed=0.10, min_time=0.25, settle=0.1,
             iters=60, vecs=None):
        """Straight-line Cartesian move of the tool point ``offset`` to ``target``."""
        offset = np.asarray(offset, float)
        p0, R0 = self.tool(offset)
        target = np.asarray(target, float)
        axes = axes or {}
        dur = max(min_time, np.linalg.norm(target - p0) / speed)
        n = max(1, int(dur / DT))
        g0 = self.grip_cmd
        q = self.qcmd
        worst = 0.0
        for i in range(1, n + 1):
            s = i / n
            s = s * s * (3 - 2 * s)                                   # smoothstep
            p = p0 + (target - p0) * s
            ax = {k: _slerp(R0[:, k], np.asarray(v, float), s) for k, v in axes.items()}
            q, err, _ = self.ik.solve(q, p, ax, offset, iters=iters, vecs=vecs)
            worst = max(worst, err)
            g = g0 + (grip - g0) * s if grip is not None else g0
            self.env.set_ctrl(q, g)
            self.env.step(DT)
        self.qcmd = q
        if grip is not None:
            self.grip_cmd = grip
        self.env.step(settle)
        return worst

    def goto(self, target, axes=None, offset=(0, 0, 0), grip=None, dur=1.2, settle=0.1):
        """Transit move: IK from several seeds, then smooth joint-space interpolation."""
        best = None
        for seed in (self.qcmd, HOME, np.radians([0, -30, 40, 80, 0]), np.radians([0, 0, 20, 70, 0])):
            q, err, rerr = self.ik.solve(seed, target, axes or {}, offset, iters=300)
            score = err + 0.02 * rerr
            if best is None or score < best[0]:
                best = (score, q, err)
        _, q1, err = best
        q0 = self.qcmd
        g0 = self.grip_cmd
        n = max(1, int(dur / DT))
        for i in range(1, n + 1):
            s = i / n
            s = s * s * (3 - 2 * s)
            g = g0 + (grip - g0) * s if grip is not None else g0
            self.env.set_ctrl(q0 + (q1 - q0) * s, g)
            self.env.step(DT)
        self.qcmd = q1
        if grip is not None:
            self.grip_cmd = grip
        self.env.step(settle)
        return err

    def compliant_close(self, target_force=33.0, step=0.004):
        """Force-limited grasp: close the jaw in small position steps until the jaw-device contact
        force reaches ``target_force`` (the STS3215 servo would otherwise squeeze with full torque)."""
        g = self.env.d.qpos[self.env.gq]
        while g > GRIP_CLOSED:
            g -= step
            self.grip_cmd = g
            self.env.set_ctrl(self.qcmd, g)
            self.env.step(0.03)
            if self.env.grip_force() >= target_force:
                break
        self.env.step(0.3)
        self.say(f"compliant grasp: jaw cmd {g:.3f} rad, squeeze {self.env.grip_force():.1f} N")

    def grip(self, value, t=0.6):
        self.grip_cmd = value
        self.env.set_ctrl(self.qcmd, value)
        self.env.step(t)

    def home(self):
        q0 = self.qcmd
        n = 40
        for i in range(1, n + 1):
            s = i / n
            self.env.set_ctrl(q0 + (HOME - q0) * s * s * (3 - 2 * s), self.grip_cmd)
            self.env.step(DT)
        self.qcmd = HOME.copy()
        self.env.step(0.2)

    def device(self):
        p, R = self.env.body_pose("remote_body")
        return p, R

    def grasp_offset(self):
        """Distance (m) between the device centre and where the rigid-grasp model says it should be."""
        if not hasattr(self, "_grasp_rel"):
            return 0.0
        p, R = self.tool((0, 0, 0))
        p_act = self.env.d.site("gripperframe").xpos
        R_act = self.env.d.site("gripperframe").xmat.reshape(3, 3)
        pd, _ = self.device()
        return float(np.linalg.norm(pd - (p_act + R_act @ self._grasp_rel)))

    def stage(self, name, ok):
        self.env.log.stages.append((name, float(self.env.d.time), bool(ok)))
        self.say(f"stage {name}: {'OK' if ok else 'FAIL'}  (peak contact force so far {self.env.log.peak_force:.1f} N)")
        return ok

    # ------------------------------------------------------------- skills
    def push_to_fence(self, name="push_to_fence"):
        p, R = self.device()
        x, y = R[:, 0], R[:, 1]
        front_x = max((p + R @ [self.L / 2, sy * self.W / 2, 0])[0] for sy in (-1, 1))
        gap = FENCE_X - front_x
        if gap < 0.002:
            return self.stage(name, True)
        # press the jaw tips on the solid rear section (top face) and drag toward the fence by friction
        pt = p + R @ [-self.L / 2 + 0.035, 0, self.T]
        axes = {2: DOWN, 0: y}
        e1 = self.goto(pt + [0, 0, 0.04], axes, PRESS_OFF, grip=GRIP_CLOSED)
        e2 = self.move(pt - [0, 0, 0.003], axes, PRESS_OFF, speed=0.03, settle=0.15)
        end = pt + x * (gap / max(x[0], 0.5) + 0.006) - [0, 0, 0.003]
        e3 = self.move(end, axes, PRESS_OFF, speed=0.03, settle=0.2)
        self.say(f"push ik err approach {1000*e1:.1f} / press {1000*e2:.1f} / drag {1000*e3:.1f} mm")
        self.move(self.tool(PRESS_OFF)[0] + [0, 0, 0.05], axes, PRESS_OFF, speed=0.08)
        p, R = self.device()
        front_x = max((p + R @ [self.L / 2, sy * self.W / 2, 0])[0] for sy in (-1, 1))
        self.say(f"front end gap to fence {1000 * (FENCE_X - front_x):.1f} mm, yaw {np.degrees(np.arctan2(R[1, 0], R[0, 0])):.1f} deg")
        return self.stage(name, FENCE_X - front_x < 0.004)

    def cover_offset(self):
        """Cover displacement along device +x relative to its seated position (m)."""
        p, R = self.device()
        pc, _ = self.env.body_pose("remote_cover")
        return float(R[:, 0] @ (pc - p)) - self.cover_seat, float(R[:, 2] @ (pc - p))

    def slide_cover(self, attempt=0):
        p, R = self.device()
        x, y = R[:, 0], R[:, 1]
        pc, Rc = self.env.body_pose("remote_cover")
        ridge = pc + Rc @ [-self.cover_hx + 0.011, 0, 0.0008 + 0.0008]
        axes = {2: DOWN, 0: y}
        press = 0.0025 + 0.0015 * attempt                    # how far below the ridge top we command
        self.goto(ridge + [0, 0, 0.04], axes, PRESS_OFF, grip=GRIP_CLOSED)
        self.move(ridge - [0, 0, press], axes, PRESS_OFF, speed=0.03, settle=0.15)
        for k in range(4):                                   # drag in segments, re-pressing each time
            tgt = ridge + x * (0.022 * (k + 1)) - [0, 0, press]
            self.move(tgt, axes, PRESS_OFF, speed=0.025, settle=0.05)
        self.move(self.tool(PRESS_OFF)[0] + [0, 0, 0.06], axes, PRESS_OFF, speed=0.08, settle=0.4)
        off, dz = self.cover_offset()
        self.say(f"latch released: {self.env.log.latch_released_at is not None}, cover offset {1000*off:.1f} mm, dz {1000*dz:.1f} mm")
        return self.stage("slide_cover", off > 0.050 or dz < -0.005 or dz > 0.03)

    def _cell_state(self):
        """Per cell: (shift along +x_dev since reset in m, + end tilt-up in deg)."""
        p, R = self.device()
        out = []
        for i in range(2):
            pc, Rc = self.env.body_pose(f"remote_cell{i}")
            shift = float(R[:, 0] @ (pc - p)) - self._cell_seat[i]
            tilt_up = -np.degrees(np.arcsin(np.clip((R.T @ Rc[:, 2])[2], -1, 1)))   # + end is at local -z
            out.append((shift, tilt_up))
        return out

    def cells_latched(self):
        """A cell is latched while its + end is still down under the retaining lip; after a successful
        unlatch it sits pushed toward the spring with its + end tipped up against the lip's outer edge."""
        return [not (sh > 0.0015 and tu > self._cell_tilt0[i] + 1.5) for i, (sh, tu) in enumerate(self._cell_state())]

    def unlatch_cells(self, attempt=0):
        """Finger-slot skill: lower the closed jaw tip into the slot behind the + ends and push both
        cells ~4 mm into their springs (with feedback on the cell positions). Past the 3 mm lip the + ends
        are free and tip up on the floor rib (pop-up); the tip is then withdrawn straight up so the springs
        press the raised + ends against the lip's outer edge instead of back under it."""
        p, R = self.device()
        x = R[:, 0]
        z = np.array([0.0, 0.0, 1.0])
        plus = self.env.d.site("remote_plus").xpos.copy()
        axes = {2: DOWN, 0: -x}
        h = self.push_h
        # retries: shift the jaw sideways (the slot leaves ~1 mm of play) toward a cell that is still latched,
        # so that its + end face gets more of the jaw (AAA faces overlap the jaw by only ~3.5 mm)
        lat0 = self.cells_latched()
        yoff = 0.0
        if attempt > 0 and any(lat0) and not all(lat0):
            yoff = 0.0009 * (1 if lat0[1] else -1)                     # cell1 at +y, cell0 at -y
        elif attempt > 0:
            yoff = 0.0009 * (1 if attempt % 2 else -1)
        y = R[:, 1]
        plus = plus + y * yoff
        start = plus - x * 0.003 + z * h
        e0 = self.goto(start + z * 0.035, axes, PUSH_OFF, grip=GRIP_CLOSED)
        e1 = self.move(start, axes, PUSH_OFF, speed=0.02, settle=0.1)
        s0 = np.array([c[0] for c in self._cell_state()])
        k = 0
        while k < 34:
            k += 1
            self.move(plus + x * (-0.003 + 0.0005 * k) + z * h, axes, PUSH_OFF, speed=0.005, settle=0.05)
            if min(c[0] for c in self._cell_state()) > UNLATCH_SHIFT:
                break
        pushed = [c[0] for c in self._cell_state()]
        self.move(self.tool(PUSH_OFF)[0] + z * 0.03, axes, PUSH_OFF, speed=0.02, settle=0.5)
        st = self._cell_state()
        lat = self.cells_latched()
        self.say(f"unlatch: ik {1000*max(e0, e1):.1f} mm, pushed {np.round(np.array(pushed)*1000,1)} mm, "
                 f"after: shift {[round(c[0]*1000,1) for c in st]} mm, + end tilt {[round(c[1],1) for c in st]} deg, latched {lat}")
        return self.stage("unlatch_cells", not any(lat))

    def grasp_device(self):
        p, R = self.device()
        x, y = R[:, 0], R[:, 1]
        c = p + R @ [self.grasp_x, 0, 0]                      # just behind the pocket, near the centre of mass
        top = p[2] + self.T
        axes = {2: DOWN, 0: y if y[1] < 0 else -y}       # pick the jaw orientation nearer to the arm's natural roll
        self.goto([c[0], c[1], top + 0.05], axes, self.grasp_off, grip=GRIP_OPEN)
        self.move([c[0], c[1], top - self.grasp_depth], axes, self.grasp_off, speed=0.04, settle=0.1)
        self.compliant_close()
        self.move([c[0], c[1], 0.12], axes, self.grasp_off, speed=0.06, settle=0.3)
        pd, _ = self.device()
        lifted = pd[2] > 0.06
        pa = self.env.d.site("gripperframe").xpos
        Ra = self.env.d.site("gripperframe").xmat.reshape(3, 3)
        self._grasp_rel = Ra.T @ (pd - pa)
        self.say(f"device lifted to z={pd[2]:.3f}, squeeze {self.env.grip_force():.1f} N")
        return self.stage("grasp_device", lifted)

    def arm_collides(self, q):
        """True if the arm at joint config q penetrates the environment (bench, jig, bins, decor).
        Contacts with the device/cells are ignored (the device is in hand)."""
        m = self.env.m
        if not hasattr(self, "_scratch"):
            self._scratch = mujoco.MjData(m)
            dev = {m.body(b).id for b in ("remote_body", "remote_cover", "remote_cell0", "remote_cell1")}
            dev |= {m.body(f"remote_plunger{i}").id for i in range(2)}
            self._ignore = dev
        sd = self._scratch
        sd.qpos[:] = self.env.d.qpos
        sd.qpos[self.env.qadr] = q
        mujoco.mj_kinematics(m, sd)
        mujoco.mj_collision(m, sd)
        rb = self.env.robot_bodies
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
        p, R = self.ik.fk(q)
        Rd = R @ Rrel
        pd = p + R @ prel
        return pd, Rd, pd[None, :] + corners @ Rd.T, p + R @ comp_off

    def _roll_path(self, q_flip, rel, step_deg=10):
        """Joint path that rolls the device about its long axis (tool y = wrist-flex axis, roll ~ 0)
        with the TCP held fixed, from an upright pose (device up-axis z > 0.7) to q_flip. Both
        rotation directions are tried. Returns [q_upright, ..., q_flip] or None."""
        prel, Rrel, comp_off, corners = rel
        bc = np.array(BATTERY_BIN["center"][:2])
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        hb = BATTERY_BIN["size"][0] / 2 + 0.015
        p, R = self.ik.fk(q_flip)
        pocket = p + R @ comp_off
        yv = R[:, 1]
        half = BATTERY_BIN["size"][0] / 2 - 0.02
        for sgn in (1, -1):
            path = [q_flip]
            q = q_flip
            ok = False
            for k in range(1, int(220 / step_deg) + 1):
                a_k = _rot(R[:, 2], yv, sgn * np.radians(step_deg * k))
                q, err, rerr = self.ik.solve(q, pocket, {2: a_k, 1: yv}, comp_off, iters=120)
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
                if Rd[2, 2] > 0.5:          # within 60 deg of upright: cells cannot leave the 16 mm-deep pocket
                    ok = True
                    break
            if ok:
                return path[::-1]
        return None

    def _upright_path(self, q0, q1, rel, n=25):
        for t in np.linspace(0, 1, n):
            q = q0 + (q1 - q0) * t
            _, Rd_, cw_, _ = self._dev_geom(q, rel)
            if Rd_[2, 2] < 0.45 or not self._clear_of_obstacles(cw_) or self.arm_collides(q):
                return False
        return True

    def _transit_route(self, q0, q_up, rel):
        """Waypoints from the lifted grasp pose to the roll start keeping the device upright and
        collision-free (direct, raised, swing-first variants). Returns list ending in q_up, or None."""
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
            if all(np.all(self.ik.lo <= w) and np.all(w <= self.ik.hi) for w in r) and                     all(self._upright_path(pts[i], pts[i + 1], rel) for i in range(len(pts) - 1)):
                return r
        return None

    def plan_flip(self, rel, n=60000, seed=0):
        """Sample arm poses with wrist roll ~ 0 (tool y = wrist-flex axis = device long axis) where the
        device is >= 120 deg upside-down, clears the bin rim and has its pocket above the bin; keep the
        closest-to-centre one for which the in-place roll path from upright exists."""
        prel, Rrel, comp_off, corners = rel
        bc = np.array(BATTERY_BIN["center"][:2])
        top = BATTERY_BIN["center"][2] + BATTERY_BIN["size"][2]
        rng = np.random.default_rng(seed)
        lo, hi = self.ik.lo.copy(), self.ik.hi.copy()
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
        for d, q in cands[:60]:
            if self.arm_collides(q):
                continue
            # refine: pocket exactly above the centre, keeping the tool y axis and device up-axis
            p, R = self.ik.fk(q)
            pd, Rd, cw, comp = self._dev_geom(q, rel)
            q2, err, rerr = self.ik.solve(q, [bc[0], bc[1], comp[2]], {1: R[:, 1]}, comp_off,
                                          vecs=[(Rrel[:, 2], Rd[:, 2])], iters=200)
            if err < 0.005 and rerr < 0.05:
                q = q2
            if self.arm_collides(q):
                continue
            path = self._roll_path(q, rel)
            if path is None:
                continue
            if self._transit_route(self.qcmd.copy(), path[0], rel) is None:
                continue
            pd, Rd, cw, comp = self._dev_geom(q, rel)
            return np.linalg.norm(comp[:2] - bc), path, comp, -np.degrees(np.arccos(np.clip(Rd[2, 2], -1, 1)))
        return None

    def flip_over_bin(self):
        env = self.env
        p_tcp, R_tcp = self.tool((0, 0, 0))
        pd, Rd = self.device()
        comp = env.d.site("remote_comp").xpos.copy()
        corners = np.array([[sx * self.L / 2, sy * self.W / 2, z] for sx in (-1, 1) for sy in (-1, 1)
                            for z in (0.0, self.T)])
        rel = (R_tcp.T @ (pd - p_tcp), R_tcp.T @ Rd, R_tcp.T @ (comp - p_tcp), corners)
        plan = self.plan_flip(rel)
        if plan is None:
            self.say("no reachable flip pose")
            return self.stage("flip_over_bin", False)
        sc, path, comp_w, ang = plan
        q_up, q_flip = path[0], path[-1]
        self.say(f"flip plan: device turned {-ang:.0f} deg, pocket {1000*sc:.0f} mm from bin centre, z {comp_w[2]:.3f}")
        # transit: direct joint-space path to the roll start pose, checked in advance to keep the
        # device upright (cells stay in the pocket) and clear of the table; otherwise go via a raised pose
        chosen = self._transit_route(self.qcmd.copy(), q_up, rel)
        if chosen is None:
            self.say("no verified upright transit")
            return self.stage("flip_over_bin", False)
        self.say(f"transit via {len(chosen) - 1} waypoint(s)")
        for w in chosen[:-1]:
            self.goto_q(w, dur=1.4, settle=0.1)
        self.goto_q(q_up, dur=2.0, settle=0.3)
        self.say(f"after transit: grasp slip {1000*self.grasp_offset():.0f} mm")
        cells_before = [env.d.body(f"remote_cell{i}").xpos.copy() for i in range(2)]
        for qk in path[1:]:                                    # roll the device about its long axis
            self.goto_q(qk, dur=0.35, settle=0.0, warn=False)
        self.env.step(0.4)
        pd, Rd = self.device()
        self.say(f"at flip pose: device up-axis z {Rd[2,2]:.2f}, pocket {np.round(env.d.site('remote_comp').xpos,3)}, grasp slip {1000*self.grasp_offset():.0f} mm")
        for _ in range(3):                                     # gentle shake about the flex axis
            for d in (+0.10, -0.10):
                qs = q_flip.copy()
                qs[3] = np.clip(qs[3] + d, self.ik.lo[3], self.ik.hi[3])
                self.goto_q(qs, dur=0.25, settle=0.0, warn=False)
        self.goto_q(q_flip, dur=0.25, settle=1.0)
        moved = [np.linalg.norm(env.d.body(f"remote_cell{i}").xpos - cells_before[i]) for i in range(2)]
        rep = env.success()
        self.say(f"cells moved {np.round(np.array(moved)*1000,0)} mm, in bin {rep.cells_in_battery_bin}")
        self.say(f"after shake: grasp slip {1000*self.grasp_offset():.0f} mm")
        # cells are out: lift the (still inverted) device straight up and away from the bin rim
        q_lift = self.qcmd.copy()
        p_now = self.tool((0, 0, 0))[0]
        q_l, e_l, _ = self.ik.solve(q_lift, p_now + [0, 0, 0.08], {}, iters=200)
        self.goto_q(q_l, dur=0.8, settle=0.1, warn=False)
        return self.stage("flip_over_bin", all(rep.cells_in_battery_bin))

    def goto_q(self, q1, dur=1.0, settle=0.1, warn=True):
        q0 = self.qcmd
        n = max(1, int(dur / DT))
        for i in range(1, n + 1):
            s = i / n
            s = s * s * (3 - 2 * s)
            self.env.set_ctrl(q0 + (q1 - q0) * s, self.grip_cmd)
            self.env.step(DT)
        self.qcmd = np.array(q1, float)
        self.env.step(settle)
        track = np.abs(self.env.q - self.qcmd).max()
        if warn and track > 0.12:
            self.say(f"WARNING joint tracking error {np.degrees(track):.0f} deg (blocked?) per joint {np.degrees(self.env.q - self.qcmd).round(0)}")

    def drop_in_crate(self):
        """Carry the empty device over the blue crate (long axis along the crate's long side) and release."""
        cc = np.array(BODY_CRATE["center"][:2])
        ctop = BODY_CRATE["center"][2] + BODY_CRATE["size"][2]
        # raise first (shoulder back) so the swing clears both bins
        q_r = self.qcmd.copy()
        q_r[1] = max(self.ik.lo[1], q_r[1] - np.radians(30))
        self.goto_q(q_r, dur=0.8, warn=False)
        best = None
        for h in (0.05, 0.07, 0.09):
            for axes in ({2: DOWN, 1: (0, 1, 0)}, {2: DOWN, 1: (0, -1, 0)}, {2: DOWN}, {}):
                for seed in (self.qcmd, HOME):
                    q, err, rerr = self.ik.solve(seed, [cc[0], cc[1], ctop + h], axes, iters=300)
                    pen = 0.0 if len(axes) == 2 else (0.004 if len(axes) == 1 else 0.008)
                    sc = err + pen + 0.002 * (h - 0.05) / 0.02
                    if best is None or sc < best[0]:
                        best = (sc, q, err)
        _, q_c, err = best
        self.say(f"crate pose ik err {1000*err:.1f} mm")
        q_swing = self.qcmd.copy()
        q_swing[0] = q_c[0]
        self.goto_q(q_swing, dur=1.4, warn=False)
        self.goto_q(q_c, dur=1.2, settle=0.3, warn=False)
        self.grip(GRIP_OPEN, 0.8)
        self.env.step(0.6)
        q_up = self.qcmd.copy()
        q_up[1] = max(self.ik.lo[1], q_up[1] - np.radians(25))
        self.goto_q(q_up, dur=0.8, settle=0.5, warn=False)
        rep = self.env.success()
        self.say(f"device at {np.round(self.device()[0],3)}, in crate: {rep.body_in_crate}")
        return self.stage("drop_in_crate", rep.body_in_crate)

    # ------------------------------------------------------------- run
    def run(self):
        env = self.env
        ok = self.push_to_fence()
        if ok:
            ok = self.slide_cover()
            if not ok:
                ok = self.slide_cover(attempt=1)
        if ok:
            self.push_to_fence(name="reseat_on_fence")             # the cells must be pushed against the fence-braced device
            ok = self.unlatch_cells()
            for k in (1, 2):
                if ok:
                    break
                ok = self.unlatch_cells(attempt=k)
        if ok:
            ok = self.grasp_device()
            if not ok:
                self.grip(GRIP_OPEN, 0.4)
                self.move(self.tool((0, 0, 0))[0] + [0, 0, 0.05], {2: DOWN})
                ok = self.grasp_device()
        if ok:
            ok = self.flip_over_bin()
        if ok or env.success().cells_in_battery_bin.count(True) > 0:
            self.drop_in_crate()
        self.home()
        return env.success()
