p = 'battery_sim/devices.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:70]; s = s.replace(a, b)
# recessed finger-slot floor (3 mm deeper than the pocket floor)
rep('''    g.append(_box(f"{p}slab", (-L / 2, -W / 2, 0), (L / 2, W / 2, floor), m, col))''',
    '''    slot_floor = floor - SLOT_RECESS
    g.append(_box(f"{p}slab", (-L / 2, -W / 2, 0), (nx0, W / 2, floor), m, col))
    g.append(_box(f"{p}slabF", (cx0, -W / 2, 0), (L / 2, W / 2, floor), m, col))
    for s_ in (-1, 1):
        y0, y1 = sorted((s_ * slot_w, s_ * W / 2))
        g.append(_box(f"{p}slab{'L' if s_ > 0 else 'R'}", (nx0, y0, 0), (cx0, y1, floor), m, col))
    g.append(_box(f"{p}slotfloor", (nx0, -slot_w, 0), (cx0, slot_w, slot_floor), m, col))''')
rep('''SLOT_LEN = 0.034 ''', '''SLOT_RECESS = 0.003                # finger-slot floor sits 3 mm below the pocket floor
SLOT_LEN = 0.034 ''')
# slab needs nx0/slot_w defined before use: move the slot definitions up if necessary
i_slab = s.index('    slot_floor = floor - SLOT_RECESS')
i_nx0 = s.index('    nx0 = cx0 - SLOT_LEN')
assert i_nx0 < i_slab, "nx0 must be defined before the slab"
rep('''                      push_h=max(0.005, ct.div_h + 0.0008 + 0.0066 + 0.0025 - (ct.r + 0.0002)),''',
    '''                      # AA: validated 5 mm. Other cells: lowest tool origin such that the moving jaw (bottom 4.7 mm
                      # below the origin) clears the divider and the fixed jaw (6.6 mm) clears the recessed slot floor
                      push_h=0.005 if ct.name == "AA" else
                      max(floor + ct.div_h + 0.0008 + 0.0047, slot_floor + 0.0008 + 0.0066) + 0.0025 - (floor + ct.r + 0.0002),
                      slot_floor=slot_floor,''')
rep('''    slot = cube((dims["nx0"], -dims["slot_w"], dims["floor"]), (dims["cx0"] + 1e-4, dims["slot_w"], T + 0.01))''',
    '''    slot = cube((dims["nx0"], -dims["slot_w"], dims["slot_floor"]), (dims["cx0"] + 1e-4, dims["slot_w"], T + 0.01))''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
