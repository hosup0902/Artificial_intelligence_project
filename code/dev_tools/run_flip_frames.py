import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np, mujoco
from PIL import Image
from snap import load
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
r = mujoco.Renderer(env.m, 360, 480)
frames = []; t_next = [env.d.time]
orig = env.step
pk = [env.log.peak_force]
def step(sec):
    orig(sec)
    if env.d.time >= t_next[0]:
        t_next[0] += 0.25
        r.update_scene(env.d, camera="bincam"); frames.append((env.d.time, r.render().copy()))
    if env.log.peak_force > pk[0] + 2:
        pk[0] = env.log.peak_force
        m, d = env.m, env.d
        for i in range(d.ncon):
            c = d.contact[i]; b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if (b1 in env.robot_bodies) != (b2 in env.robot_bodies) and (b1 in env.device_bids or b2 in env.device_bids):
                print(f"t={d.time:.2f} peak {pk[0]:.1f}: {m.geom(c.geom1).name or m.body(b1).name} | {m.geom(c.geom2).name or m.body(b2).name}")
env.step = step
pol.run_par(pol.flip_over_bin())
print(env.success())
sel = frames[::max(1, len(frames) // 12)][:12]
W, H = 480, 360
sheet = Image.new("RGB", (W * 4, H * 3))
for i, (t, f) in enumerate(sel):
    sheet.paste(Image.fromarray(f), ((i % 4) * W, (i // 4) * H))
sheet.save(HERE / "_out" / "flip_sheet.png")
