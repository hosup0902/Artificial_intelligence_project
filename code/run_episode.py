"""Run the skill policy on one or more seeds.

  python run_episode.py --seeds 0            # one episode, verbose
  python run_episode.py --seeds 0 --video    # + mp4 to videos/
  python run_episode.py --seeds 0-29 -q      # evaluation sweep
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.devices import DEVICE_ORDER  # noqa: E402
from battery_sim.env import BatteryRemovalEnv  # noqa: E402
from battery_sim.policy import SkillPolicy  # noqa: E402

ROOT = Path(__file__).resolve().parent


def parse_seeds(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--cam", default="hero")
    ap.add_argument("-q", "--quiet", action="store_true")
    ap.add_argument("--out", default=None, help="json results file")
    ap.add_argument("--device", default="all", help="device type, or 'all' = cycle the 4 types by seed")
    args = ap.parse_args()
    seeds = parse_seeds(args.seeds)
    envs = {}
    results = []
    for sd in seeds:
        dev = DEVICE_ORDER[sd % len(DEVICE_ORDER)] if args.device == "all" else args.device
        if dev not in envs:
            envs[dev] = BatteryRemovalEnv(device=dev, video=args.video, video_cam=args.cam)
        env = envs[dev]
        t0 = time.time()
        env.reset(sd)
        rep = SkillPolicy(env, verbose=not args.quiet).run()
        # first stage that failed for good (a retried stage that later succeeded does not count)
        final = {}
        for n, _, ok in env.log.stages:
            final[n] = ok
        # advisory stages (not part of the success criterion): reseat_on_fence, return_tool (tool back in its holder)
        advisory = ("reseat_on_fence", "return_tool")
        failed = next((n for n, ok in final.items() if not ok and n not in advisory), None)
        r = dict(seed=sd, device=dev, success=bool(rep.success), cells_in_bin=[bool(c) for c in rep.cells_in_battery_bin],
                 body_in_crate=bool(rep.body_in_crate), cell_in_crate=bool(rep.cell_in_crate),
                 peak_force=round(float(env.log.peak_force), 2), peak_info=env.log.peak_info,
                 sim_time=round(float(env.d.time), 2), steps=int(round(env.d.time / env.m.opt.timestep)),
                 failed_stage=failed, tool_returned=bool(final.get("return_tool", False)),
                 pry_attempts=sum(n == "pry_cells" for n, _, _ in env.log.stages),
                 hold_ok=bool(final.get("hold_device", False)),
                 wall=round(time.time() - t0, 1))
        results.append(r)
        print(json.dumps(r, ensure_ascii=False))
        if args.video:
            import imageio.v2 as imageio
            (ROOT / "videos").mkdir(exist_ok=True)
            path = ROOT / "videos" / f"seed{sd:03d}_{dev}_{'success' if rep.success else 'fail'}.mp4"
            imageio.mimsave(path, env.frames, fps=25, quality=8, macro_block_size=1)
            print("video:", path)
    sr = np.mean([r["success"] for r in results])
    print(f"SUCCESS RATE {sr*100:.1f}% ({sum(r['success'] for r in results)}/{len(results)})")
    for dev in DEVICE_ORDER:
        rs = [r for r in results if r["device"] == dev]
        if rs:
            print(f"  {dev:13s} {sum(r['success'] for r in rs)}/{len(rs)}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
