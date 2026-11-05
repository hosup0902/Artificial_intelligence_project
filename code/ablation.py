"""Control experiments for the battery-retention mechanism (same seeds, same success criterion).

  no_tool    : the tool arm never pries; the main arm opens the cover, grasps, flips and shakes the device
               over the bin (= "just turn it upside down").
  push_only  : the tool pushes both cells into their springs past the retaining lip but does not lift
               the + ends (= "push toward the spring and hope they pop out").

If the compartment is modelled like a real one, both must fail: the cells stay trapped under the lips.

  python ablation.py --mode no_tool --seeds 0-4 --device all
  python ablation.py --mode push_only --seeds 0-4 --device all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.devices import DEVICE_ORDER  # noqa: E402
from battery_sim.env import BatteryRemovalEnv  # noqa: E402
from battery_sim.policy import SkillPolicy  # noqa: E402
from run_episode import parse_seeds  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("no_tool", "push_only"), required=True)
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--device", default="all", help="device type, or 'all' = every device for every seed")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    devices = DEVICE_ORDER if args.device == "all" else [args.device]
    results = []
    for dev in devices:
        env = BatteryRemovalEnv(device=dev)
        for sd in parse_seeds(args.seeds):
            env.reset(sd)
            pol = SkillPolicy(env, verbose=False, use_tool=args.mode != "no_tool", lift_cells=args.mode != "push_only")
            rep = pol.run()
            r = dict(mode=args.mode, device=dev, seed=sd, success=bool(rep.success),
                     cells_in_bin=[bool(c) for c in rep.cells_in_battery_bin], body_in_crate=bool(rep.body_in_crate),
                     stages=[(n, ok) for n, _, ok in env.log.stages])
            results.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    n_ok = sum(r["success"] for r in results)
    n_cells = sum(sum(r["cells_in_bin"]) for r in results)
    print(f"ABLATION {args.mode}: success {n_ok}/{len(results)}, cells in bin {n_cells}/{2 * len(results)}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
