def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:70]); s = s.replace(a, b)
    open(p, 'w', encoding='utf-8').write(s)
patch('battery_sim/devices.py', [
    ('''AAA = CellType("AAA", 0.00525, 0.0445, 0.0115, 0.017, 0.0010)''', '''AAA = CellType("AAA", 0.00525, 0.0445, 0.0115, 0.017, 0.0006)'''),
    ('''max(floor + ct.div_h + 0.0008 + 0.0047, slot_floor + 0.0008 + 0.0066)''', '''max(floor + ct.div_h + 0.0006 + 0.0047, slot_floor + 0.0008 + 0.0066)'''),
])
patch('battery_sim/policy.py', [
    ('''        self.grasp_depth = min(GRASP_DEPTH, self.T - 0.006)         # jaw bottom (6.6 mm below origin) stays above the tray''',
     '''        # jaw bottom is 6.6 mm below the tool origin: keep it >= 0.5 mm above the tray for thinner devices
        self.grasp_depth = GRASP_DEPTH if self.T >= 0.022 else self.T - 0.0071'''),
    ('''            if Rd[2, 2] > -0.5 or cw[:, 2].min() < top + 0.035 or comp[2] > top + 0.26:''',
     '''            if Rd[2, 2] > -0.5 or cw[:, 2].min() < top + 0.035 or comp[2] > top + 0.30:'''),
])
print('ok')
