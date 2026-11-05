p = 'battery_sim/scene.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b)
rep('''NOMINAL_REMOTE_POSE = (0.205, 0.005, JIG_TOP + 0.0002)''', '''NOMINAL_REMOTE_POSE = (0.205, 0.005, JIG_TOP + 0.0002)


def nominal_pose(spec):
    """Spawn pose of a device: battery end 27 mm short of the jig fence (same as the TV remote)."""
    return (FENCE_X - spec.length / 2 - 0.027, 0.005, JIG_TOP + 0.0002)''')
rep('''    "plastic_remote_plain": "0.13 0.13 0.14 1",''', '''    "plastic_remote_plain": "0.13 0.13 0.14 1",
    "plastic_mouse_plain": "0.55 0.57 0.60 1",
    "plastic_clock_plain": "0.90 0.89 0.85 1",
    "navy": "0.13 0.18 0.32 1",
    "navy_plain": "0.13 0.18 0.32 1",''')
rep('''def build_scene_xml(remote_pose=NOMINAL_REMOTE_POSE, remote_yaw=0.0, cover_on=True, cover_offset=0.0,
                    cell_materials=("battery_a", "battery_a")) -> str:
    decor = _copy_decor_meshes()
    spec = dv.RemoteSpec(cell_materials=list(cell_materials))
    body, eq, extra, _cells, dev_assets, dims = dv.remote_body_xml(spec, remote_pose, remote_yaw, with_cover=cover_on,
                                                                   cover_offset=cover_offset)
    dv.write_remote_shell(dims, MJCF_DIR / "assets" / "devices" / f"{spec.prefix}shell.obj")''',
'''def build_scene_xml(device="tv_remote", remote_pose=None, remote_yaw=0.0, cover_on=True, cover_offset=0.0) -> str:
    decor = _copy_decor_meshes()
    spec = dv.DEVICES[device]
    remote_pose = remote_pose or nominal_pose(spec)
    body, eq, extra, _cells, dev_assets, dims = dv.remote_body_xml(spec, remote_pose, remote_yaw, with_cover=cover_on,
                                                                   cover_offset=cover_offset)
    dv.write_remote_shell(dims, MJCF_DIR / "assets" / "devices" / f"{spec.prefix}shell_{spec.name}.obj")
    global LAST_DIMS
    LAST_DIMS = dict(dims, name=spec.name, label=spec.label, nominal=remote_pose)''')
rep('''def load_model(**kw):''', '''LAST_DIMS: dict = {}


def load_model(**kw):''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
