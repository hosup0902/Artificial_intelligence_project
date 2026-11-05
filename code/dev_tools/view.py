"""Scratch helper: render free-camera views. usage: views(env, out, [(lookat, dist, az, el) | camname, ...])"""
import mujoco, numpy as np
from PIL import Image
def views(env, out, specs, size=(480, 640), collision=False):
    r = mujoco.Renderer(env.m, *size)
    opt = mujoco.MjvOption()
    if collision:
        opt.geomgroup[:] = [1, 0, 0, 1, 1, 0]
    tiles = []
    for s in specs:
        if isinstance(s, str):
            r.update_scene(env.d, camera=s, scene_option=opt)
        else:
            cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            cam.lookat[:], cam.distance, cam.azimuth, cam.elevation = s
            r.update_scene(env.d, cam, scene_option=opt)
        tiles.append(r.render().copy())
    r.close()
    n = len(tiles); cols = min(n, 3); rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (size[1] * cols, size[0] * rows))
    for i, t in enumerate(tiles):
        sheet.paste(Image.fromarray(t), ((i % cols) * size[1], (i // cols) * size[0]))
    sheet.save(out)
