"""Battery-removal environment on the SO101-Nexus SO-101 MuJoCo model.

The scene (``scene.py``) is compiled once; every ``reset(seed)`` re-poses the device,
its cover and cells as one rigid group (random x/y/yaw inside the jig) and re-arms the
cover latch. Physics: 2 ms step, position-servo SO-101 (STS3215 gains from so101-nexus).

Mechanism logic implemented here (not expressible in MJCF alone):
  * snap latch: the weld ``remote_latch`` holds the cover until the latch force along the
    device +x axis exceeds ``LATCH_FORCE`` for ``LATCH_STEPS`` consecutive steps, then the
    weld is disabled for the rest of the episode (the cover is free to slide off).
  * damage monitor: the peak normal force between any robot geom and the device
    (body or cover) is recorded for the success check.
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
LATCH_FORCE = 1.5          # N, latch release threshold along the slide direction
LATCH_STEPS = 10
DEVICE_BODIES = ("remote_body", "remote_cover", "remote_cell0", "remote_cell1")


@dataclass
class EpisodeLog:
    seed: int
    stages: list[tuple[str, float, bool]] = field(default_factory=list)   # (name, sim time, ok)
    peak_force: float = 0.0
    latch_released_at: float | None = None


class BatteryRemovalEnv:
    def __init__(self, device="tv_remote", randomize=True, video=False, video_cam="hero", video_every=0.04,
                 size=(480, 854)):
        self.device = device
        self.m = load_model(device=device)
        self.dims = dict(scene_mod.LAST_DIMS)
        self.d = mujoco.MjData(self.m)
        self.randomize = randomize
        self.qadr = np.array([self.m.joint(j).qposadr[0] for j in ARM])
        self.aid = np.array([self.m.actuator(j).id for j in ARM])
        self.gq = self.m.joint("gripper").qposadr[0]
        self.ga = self.m.actuator("gripper").id
        self.latch = self.m.eq("remote_latch").id
        self.free = {b: self.m.joint(f"{b}_free" if b != "remote_body" else "remote_free").qposadr[0]
                     for b in DEVICE_BODIES}
        self.robot_bodies = self._subtree(self.m.body("base").id)
        self.device_bids = {self.m.body(b).id for b in ("remote_body", "remote_cover")}
        self.video = video
        self.frames: list[np.ndarray] = []
        self.video_cam = video_cam
        self.video_every = video_every
        self._renderer = mujoco.Renderer(self.m, *size) if video else None
        self._next_frame = 0.0
        self.max_time = 60.0

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
        d.qpos[self.qadr] = HOME
        d.ctrl[self.aid] = HOME
        d.qpos[self.gq] = d.ctrl[self.ga] = 0.0
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
            self._latch_logic()
            self._force_monitor()
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
        if abs(f @ xdev) > LATCH_FORCE:
            self._latch_count += 1
            if self._latch_count >= LATCH_STEPS:
                d.eq_active[self.latch] = 0
                self.log.latch_released_at = float(d.time)
        else:
            self._latch_count = 0

    def _force_monitor(self):
        m, d = self.m, self.d
        f6 = np.zeros(6)
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if (b1 in self.robot_bodies and b2 in self.device_bids) or (b2 in self.robot_bodies and b1 in self.device_bids):
                mujoco.mj_contactForce(m, d, i, f6)
                self.log.peak_force = max(self.log.peak_force, abs(f6[0]))

    def grip_force(self):
        """Total normal force (N) between the robot and the device body (jaw squeeze)."""
        m, d = self.m, self.d
        f6 = np.zeros(6)
        tot = 0.0
        bid = self.m.body("remote_body").id
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if (b1 in self.robot_bodies and b2 == bid) or (b2 in self.robot_bodies and b1 == bid):
                mujoco.mj_contactForce(m, d, i, f6)
                tot += abs(f6[0])
        return tot

    # ------------------------------------------------------------------ io
    @property
    def q(self):
        return self.d.qpos[self.qadr].copy()

    def set_ctrl(self, q, grip=None):
        self.d.ctrl[self.aid] = q
        if grip is not None:
            self.d.ctrl[self.ga] = grip

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
