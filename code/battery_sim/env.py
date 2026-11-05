"""Bimanual battery-removal environment on the SO101-Nexus SO-101 MuJoCo model.

Two SO-101 arms share the workstation:
  * arm "R" (main arm, base at the origin, facing +x): handles the device
    (push to the fence, slide the cover off, hold the device down, flip it over the
    battery bin, drop the empty body into the crate);
  * arm "L" (tool arm, joint/body names prefixed ``l_``, base across the jig facing -x):
    picks the thin pry tool from its rack, pries the cells out of their latched seats,
    and puts the tool back.

The scene (``scene.py``) is compiled once; every ``reset(seed)`` re-poses the device,
its cover and cells as one rigid group (random x/y/yaw inside the jig) and re-arms the
cover latch. Physics: 2 ms step, position-servo SO-101 (STS3215 gains from so101-nexus).

Mechanism logic implemented here (not expressible in MJCF alone):
  * snap latch: the weld ``remote_latch`` holds the cover until the cover is pressed down by
    the robot (>= ``LATCH_PRESS`` N) while being pushed along the device +x axis
    (>= ``LATCH_FORCE`` N) for ``LATCH_STEPS`` consecutive steps (press-and-slide), then the
    weld is disabled for the rest of the episode.
  * damage monitor: the peak normal force between any robot geom (either arm or the hand-held
    tool) and the device (body or cover) is recorded for the success check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import mujoco
import numpy as np

import battery_sim.scene as scene_mod
from battery_sim.scene import load_model
from battery_sim.success import check_success

ARM = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
HOME = np.radians([0.0, -100.0, 40.0, 80.0, 0.0])
GRIP_OPEN, GRIP_CLOSED = 0.8, -0.17
LATCH_FORCE = 1.5          # N, latch release threshold along the slide direction ...
LATCH_PRESS = 1.0          # N, ... while the latch tab is pressed down at least this hard
LATCH_STEPS = 10
DEVICE_BODIES = ("remote_body", "remote_cover", "remote_cell0", "remote_cell1")
ARM_PREFIX = {"R": "", "L": "l_"}


@dataclass
class EpisodeLog:
    seed: int
    stages: list[tuple[str, float, bool]] = field(default_factory=list)   # (name, sim time, ok)
    peak_force: float = 0.0
    latch_released_at: float | None = None


class ArmIO:
    """Joint / actuator indices of one SO-101."""

    def __init__(self, m, key):
        pre = ARM_PREFIX[key]
        self.key, self.prefix = key, pre
        self.joints = tuple(pre + j for j in ARM)
        self.qadr = np.array([m.joint(j).qposadr[0] for j in self.joints])
        self.aid = np.array([m.actuator(j).id for j in self.joints])
        self.gq = m.joint(pre + "gripper").qposadr[0]
        self.ga = m.actuator(pre + "gripper").id
        self.site = pre + "gripperframe"
        self.base = pre + "base"


class BatteryRemovalEnv:
    def __init__(self, device="tv_remote", randomize=True, video=False, video_cam="hero", video_every=0.04,
                 size=(480, 854)):
        self.device = device
        self.m = load_model(device=device)
        self.dims = dict(scene_mod.LAST_DIMS)
        self.d = mujoco.MjData(self.m)
        self.randomize = randomize
        self.arms = {k: ArmIO(self.m, k) for k in ARM_PREFIX}
        self.latch = self.m.eq("remote_latch").id
        self.free = {b: self.m.joint(f"{b}_free" if b != "remote_body" else "remote_free").qposadr[0]
                     for b in DEVICE_BODIES}
        self.tool_bid = self.m.body("pry_tool").id
        self.arm_bodies = {k: self._subtree(self.m.body(a.base).id) for k, a in self.arms.items()}
        self.robot_bodies = self.arm_bodies["R"] | self.arm_bodies["L"] | {self.tool_bid}
        self.device_bids = {self.m.body(b).id for b in ("remote_body", "remote_cover")}
        self.cover_bid = self.m.body("remote_cover").id
        self.video = video
        self.frames: list[np.ndarray] = []
        self.video_cam = video_cam
        self.video_every = video_every
        self._renderer = mujoco.Renderer(self.m, *size) if video else None
        self._next_frame = 0.0
        self.max_time = 90.0

    # backwards-compatible single-arm accessors (main arm R)
    @property
    def qadr(self):
        return self.arms["R"].qadr

    @property
    def aid(self):
        return self.arms["R"].aid

    @property
    def gq(self):
        return self.arms["R"].gq

    @property
    def ga(self):
        return self.arms["R"].ga

    def _subtree(self, root):
        ids = {root}
        for b in range(self.m.nbody):
            p = b
            while p != 0:
                if p == root:
                    ids.add(b)
                    break
                p = self.m.body_parentid[p]
        return ids

    # ------------------------------------------------------------------ reset
    def reset(self, seed: int):
        m, d = self.m, self.d
        mujoco.mj_resetData(m, d)
        rng = np.random.default_rng(seed)
        self.log = EpisodeLog(seed)
        self._latch_count = 0
        d.eq_active[self.latch] = 1
        if self.randomize:
            dx, dy, dyaw = rng.uniform(-0.02, 0.0), rng.uniform(-0.012, 0.022), rng.uniform(-0.25, 0.25)
        else:
            dx = dy = dyaw = 0.0
        c0 = np.array(self.dims["nominal"][:2])
        Rz = np.array([[np.cos(dyaw), -np.sin(dyaw)], [np.sin(dyaw), np.cos(dyaw)]])
        qz = np.array([np.cos(dyaw / 2), 0, 0, np.sin(dyaw / 2)])
        for b, a in self.free.items():
            p = d.qpos[a:a + 2].copy()
            d.qpos[a:a + 2] = c0 + Rz @ (p - c0) + [dx, dy]
            q = d.qpos[a + 3:a + 7].copy()
            d.qpos[a + 3:a + 7] = _qmul(qz, q)
        for a in self.arms.values():
            d.qpos[a.qadr] = HOME
            d.ctrl[a.aid] = HOME
            d.qpos[a.gq] = d.ctrl[a.ga] = 0.0
        mujoco.mj_forward(m, d)
        self.frames = []
        self._next_frame = 0.0
        self.step(0.5)
        return self

    # ------------------------------------------------------------------ physics
    def step(self, seconds: float):
        m, d = self.m, self.d
        for _ in range(max(1, int(round(seconds / m.opt.timestep)))):
            mujoco.mj_step(m, d)
            self._contact_monitor()
            self._latch_logic()
            if self.video and d.time >= self._next_frame:
                self._renderer.update_scene(d, camera=self.video_cam)
                self.frames.append(self._renderer.render().copy())
                self._next_frame += self.video_every

    def _latch_logic(self):
        d = self.d
        if not d.eq_active[self.latch]:
            return
        rows = np.where((d.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY) & (d.efc_id == self.latch))[0]
        if len(rows) < 3:
            return
        f = d.efc_force[rows[:3]]
        xdev = d.xmat[self.m.body("remote_body").id].reshape(3, 3)[:, 0]
        if abs(f @ xdev) > LATCH_FORCE and self._cover_press >= LATCH_PRESS:
            self._latch_count += 1
            if self._latch_count >= LATCH_STEPS:
                d.eq_active[self.latch] = 0
                self.log.latch_released_at = float(d.time)
        else:
            self._latch_count = 0

    def _contact_monitor(self):
        """Peak robot->device normal force (damage check) and the robot's press force on the cover."""
        m, d = self.m, self.d
        f6 = np.zeros(6)
        press = 0.0
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if (b1 in self.robot_bodies and b2 in self.device_bids) or (b2 in self.robot_bodies and b1 in self.device_bids):
                mujoco.mj_contactForce(m, d, i, f6)
                self.log.peak_force = max(self.log.peak_force, abs(f6[0]))
                if self.cover_bid in (b1, b2):
                    press += abs(f6[0]) * abs(c.frame[2])          # vertical component of the normal force
        self._cover_press = press

    def grip_force(self, arm="R", body="remote_body"):
        """Total normal force (N) between an arm and a body (jaw squeeze)."""
        m, d = self.m, self.d
        f6 = np.zeros(6)
        tot = 0.0
        bid = self.m.body(body).id
        rb = self.arm_bodies[arm]
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if (b1 in rb and b2 == bid) or (b2 in rb and b1 == bid):
                mujoco.mj_contactForce(m, d, i, f6)
                tot += abs(f6[0])
        return tot

    # ------------------------------------------------------------------ io
    def q_of(self, arm):
        return self.d.qpos[self.arms[arm].qadr].copy()

    @property
    def q(self):
        return self.q_of("R")

    def set_ctrl(self, q, grip=None, arm="R"):
        a = self.arms[arm]
        self.d.ctrl[a.aid] = q
        if grip is not None:
            self.d.ctrl[a.ga] = grip

    def body_pose(self, name):
        b = self.d.body(name)
        return b.xpos.copy(), b.xmat.reshape(3, 3).copy()

    def success(self):
        return check_success(self.m, self.d, peak_force=self.log.peak_force)


def _qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])
