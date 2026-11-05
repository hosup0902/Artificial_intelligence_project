def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:70])
        s = s.replace(a, b)
    open(p, 'w', encoding='utf-8').write(s)

patch('battery_sim/env.py', [
    ('''from battery_sim.scene import NOMINAL_REMOTE_POSE, load_model''', '''import battery_sim.scene as scene_mod
from battery_sim.scene import load_model'''),
    ('''    def __init__(self, randomize=True, video=False, video_cam="hero", video_every=0.04, size=(480, 854)):
        self.m = load_model()''', '''    def __init__(self, device="tv_remote", randomize=True, video=False, video_cam="hero", video_every=0.04,
                 size=(480, 854)):
        self.device = device
        self.m = load_model(device=device)
        self.dims = dict(scene_mod.LAST_DIMS)'''),
    ('''        c0 = np.array(NOMINAL_REMOTE_POSE[:2])''', '''        c0 = np.array(self.dims["nominal"][:2])'''),
])
patch('battery_sim/policy.py', [
    ('''        self.qcmd = env.q
        self.grip_cmd = 0.0''', '''        self.qcmd = env.q
        self.grip_cmd = 0.0
        dm = env.dims
        self.L, self.W, self.T = dm["L"], dm["W"], dm["T"]
        self.grasp_x = dm["grasp_x"]
        self.grasp_off = np.array([0.02 - self.W / 2, 0.0, 0.0])   # fixed jaw tip at tool x = +0.02
        self.grasp_depth = min(GRASP_DEPTH, self.T - 0.006)         # jaw bottom (6.6 mm below origin) stays above the tray
        self.push_h = dm["push_h"]'''),
    ('''        front_x = max((p + R @ [L / 2, sy * W / 2, 0])[0] for sy in (-1, 1))
        gap = FENCE_X - front_x''', '''        front_x = max((p + R @ [self.L / 2, sy * self.W / 2, 0])[0] for sy in (-1, 1))
        gap = FENCE_X - front_x'''),
    ('''        pt = p + R @ [-0.055, 0, T]''', '''        pt = p + R @ [-self.L / 2 + 0.035, 0, self.T]'''),
    ('''        front_x = max((p + R @ [L / 2, sy * W / 2, 0])[0] for sy in (-1, 1))
        self.say(''', '''        front_x = max((p + R @ [self.L / 2, sy * self.W / 2, 0])[0] for sy in (-1, 1))
        self.say('''),
    ('''        h = PUSH_H + 0.001 * attempt''', '''        h = self.push_h + 0.001 * attempt'''),
    ('''        c = p + R @ [GRASP_X, 0, 0]''', '''        c = p + R @ [self.grasp_x, 0, 0]'''),
    ('''        top = p[2] + T
''', '''        top = p[2] + self.T
'''),
    ('''        self.goto([c[0], c[1], top + 0.05], axes, GRASP_OFF, grip=GRIP_OPEN)
        self.move([c[0], c[1], top - GRASP_DEPTH], axes, GRASP_OFF, speed=0.04, settle=0.1)''', '''        self.goto([c[0], c[1], top + 0.05], axes, self.grasp_off, grip=GRIP_OPEN)
        self.move([c[0], c[1], top - self.grasp_depth], axes, self.grasp_off, speed=0.04, settle=0.1)'''),
    ('''        self.move([c[0], c[1], 0.12], axes, GRASP_OFF, speed=0.06, settle=0.3)''', '''        self.move([c[0], c[1], 0.12], axes, self.grasp_off, speed=0.06, settle=0.3)'''),
    ('''        corners = np.array([[sx * L / 2, sy * W / 2, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, T)])''',
     '''        corners = np.array([[sx * self.L / 2, sy * self.W / 2, z] for sx in (-1, 1) for sy in (-1, 1)
                            for z in (0.0, self.T)])'''),
])
print('ok')
