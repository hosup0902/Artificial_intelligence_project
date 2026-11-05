"""Damped-least-squares IK for the SO-101 tool (site ``gripperframe``).

Tool frame (measured): z = approach direction (out of the fingertips), x = jaw closing
direction (the fixed jaw tip sits at x = +0.02 m, the moving jaw swings in from -x),
y = x × z. The SO-101 has 5 arm joints, so a full 6-DoF pose is generally not reachable;
we track the tool *point* exactly and any subset of tool-axis directions softly, which is
what pushing, top-down grasping and the flip motion need.
"""

from __future__ import annotations

import mujoco
import numpy as np

ARM_JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
TCP_SITE = "gripperframe"


class IK:
    def __init__(self, model):
        self.m = model
        self.d = mujoco.MjData(model)
        self.qadr = np.array([model.joint(j).qposadr[0] for j in ARM_JOINTS])
        self.dadr = np.array([model.joint(j).dofadr[0] for j in ARM_JOINTS])
        self.lo = np.array([model.joint(j).range[0] for j in ARM_JOINTS])
        self.hi = np.array([model.joint(j).range[1] for j in ARM_JOINTS])
        self.sid = model.site(TCP_SITE).id
        self.bid = model.site_bodyid[self.sid]
        self.jacp = np.zeros((3, model.nv))
        self.jacr = np.zeros((3, model.nv))

    def fk(self, q, offset=(0, 0, 0)):
        d = self.d
        d.qpos[self.qadr] = q
        mujoco.mj_kinematics(self.m, d)
        R = d.site_xmat[self.sid].reshape(3, 3).copy()
        return d.site_xpos[self.sid] + R @ np.asarray(offset, float), R

    def solve(self, q0, target, axes=None, offset=(0, 0, 0), w_rot=0.25, iters=200, damping=1e-4, tol=2e-4,
              vecs=None):
        """axes: {tool_axis_index: desired world unit vector}; vecs: [(tool-frame vector, desired world
        vector)] for arbitrary directions fixed in the tool frame. Returns (q, pos_err, rot_err)."""
        m, d = self.m, self.d
        q = np.array(q0, float)
        axes = axes or {}
        target = np.asarray(target, float)
        off = np.asarray(offset, float)
        for _ in range(iters):
            p, R = self.fk(q, off)
            mujoco.mj_comPos(m, d)
            mujoco.mj_jac(m, d, self.jacp, self.jacr, p, self.bid)
            Jp = self.jacp[:, self.dadr]
            Jr = self.jacr[:, self.dadr]
            rows, errs = [Jp], [target - p]
            rot_err = 0.0
            pairs = [(np.eye(3)[k], v) for k, v in axes.items()] + list(vecs or [])
            for loc, v in pairs:
                v = np.asarray(v, float) / np.linalg.norm(v)
                a = R @ (np.asarray(loc, float) / np.linalg.norm(loc))
                e = v - a                                   # direction error of tool axis k
                if np.linalg.norm(e) > 0.5:                 # large error: step along the great circle
                    e = 0.5 * e / np.linalg.norm(e)
                rot_err = max(rot_err, float(np.linalg.norm(v - a)))
                skew = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
                rows.append(w_rot * (-skew @ Jr))           # d(a)/dq = omega x a = -[a]x Jr dq
                errs.append(w_rot * e)
            J = np.vstack(rows)
            err = np.concatenate(errs)
            dq = J.T @ np.linalg.solve(J @ J.T + damping * np.eye(J.shape[0]), err)
            dq = np.clip(dq, -0.2, 0.2)
            q = np.clip(q + dq, self.lo, self.hi)
            if np.linalg.norm(target - p) < tol and rot_err < 0.01:
                break
        p, R = self.fk(q, off)
        return q, float(np.linalg.norm(target - p)), rot_err


def solve_ik(model, data, target_pos, approach=(0, 0, -1), q_init=None, **_):
    """Backward-compatible helper used by render_states.py."""
    ik = IK(model)
    q0 = q_init if q_init is not None else data.qpos[ik.qadr]
    q, err, _ = ik.solve(q0, target_pos, axes={2: approach})
    return q, err
