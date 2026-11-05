p = 'run_episode.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:60]
    s = s.replace(a, b)
rep('''from battery_sim.env import BatteryRemovalEnv  # noqa: E402''', '''from battery_sim.devices import DEVICE_ORDER  # noqa: E402
from battery_sim.env import BatteryRemovalEnv  # noqa: E402''')
rep('''    ap.add_argument("--out", default=None, help="json results file")''', '''    ap.add_argument("--out", default=None, help="json results file")
    ap.add_argument("--device", default="all", help="device type, or 'all' = cycle the 4 types by seed")''')
rep('''    env = BatteryRemovalEnv(video=args.video, video_cam=args.cam)
    results = []
    for sd in seeds:
        t0 = time.time()
        env.reset(sd)''', '''    envs = {}
    results = []
    for sd in seeds:
        dev = DEVICE_ORDER[sd % len(DEVICE_ORDER)] if args.device == "all" else args.device
        if dev not in envs:
            envs[dev] = BatteryRemovalEnv(device=dev, video=args.video, video_cam=args.cam)
        env = envs[dev]
        t0 = time.time()
        env.reset(sd)''')
rep('''        r = dict(seed=sd, success=bool(rep.success),''', '''        r = dict(seed=sd, device=dev, success=bool(rep.success),''')
rep('''            path = ROOT / "videos" / f"seed{sd:03d}_{'success' if rep.success else 'fail'}.mp4"''', '''            path = ROOT / "videos" / f"seed{sd:03d}_{dev}_{'success' if rep.success else 'fail'}.mp4"''')
rep('''    print(f"SUCCESS RATE {sr*100:.1f}% ({sum(r['success'] for r in results)}/{len(results)})")''', '''    print(f"SUCCESS RATE {sr*100:.1f}% ({sum(r['success'] for r in results)}/{len(results)})")
    for dev in DEVICE_ORDER:
        rs = [r for r in results if r["device"] == dev]
        if rs:
            print(f"  {dev:13s} {sum(r['success'] for r in rs)}/{len(rs)}")''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
