"""Success judgement for the battery-removal task.

Success iff ALL of:
  1. every AA cell's centre lies inside the battery-bin region (red 폐건전지 수거함);
  2. the appliance body's centre lies inside the body-crate region (blue 소형 폐가전);
  3. no cell lies inside the body crate (mis-sorted cell = failure);
  4. (optional) peak contact force on the device never exceeded the damage threshold —
     tracked by the rollout loop, passed in as ``peak_force``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DAMAGE_FORCE_N = 40.0


def _inside(data, model, site: str, point, margin=0.0) -> bool:
    sid = model.site(site).id
    c = data.site_xpos[sid]
    R = data.site_xmat[sid].reshape(3, 3)
    half = model.site_size[sid] + margin
    local = R.T @ (np.asarray(point) - c)
    return bool(np.all(np.abs(local) <= half))


@dataclass
class SuccessReport:
    cells_in_battery_bin: list[bool]
    body_in_crate: bool
    cell_in_crate: bool
    force_ok: bool

    @property
    def success(self) -> bool:
        return all(self.cells_in_battery_bin) and self.body_in_crate and not self.cell_in_crate and self.force_ok


def check_success(model, data, prefix="remote_", n_cells=2, peak_force=0.0) -> SuccessReport:
    cells = [data.body(f"{prefix}cell{i}").xpos for i in range(n_cells)]
    return SuccessReport(
        cells_in_battery_bin=[_inside(data, model, "battery_bin_region", p) for p in cells],
        body_in_crate=_inside(data, model, "body_bin_region", data.body(f"{prefix}body").xpos, margin=0.01),
        cell_in_crate=any(_inside(data, model, "body_bin_region", p) for p in cells),
        force_ok=peak_force <= DAMAGE_FORCE_N,
    )
