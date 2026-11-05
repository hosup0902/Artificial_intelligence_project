p = 'battery_sim/devices.py'
s = open(p, encoding='utf-8').read()
a = '''    g.append(_box(f"{p}slab", (-L / 2, -W / 2, 0), (nx0, W / 2, floor), m, col))
    g.append(_box(f"{p}slabF", (cx0, -W / 2, 0), (L / 2, W / 2, floor), m, col))
    for s_ in (-1, 1):
        y0, y1 = sorted((s_ * slot_w, s_ * W / 2))
        g.append(_box(f"{p}slab{'L' if s_ > 0 else 'R'}", (nx0, y0, 0), (cx0, y1, floor), m, col))
    if slot_floor > 1e-4:
        g.append(_box(f"{p}slotfloor", (nx0, -slot_w, 0), (cx0, slot_w, slot_floor), m, col))'''
b = '''    if slot_floor >= floor - 1e-6:                     # flat slot floor (AA): single bottom slab, as validated
        g.append(_box(f"{p}slab", (-L / 2, -W / 2, 0), (L / 2, W / 2, floor), m, col))
    else:                                              # recessed slot floor (AAA)
        g.append(_box(f"{p}slab", (-L / 2, -W / 2, 0), (nx0, W / 2, floor), m, col))
        g.append(_box(f"{p}slabF", (cx0, -W / 2, 0), (L / 2, W / 2, floor), m, col))
        for s_ in (-1, 1):
            y0, y1 = sorted((s_ * slot_w, s_ * W / 2))
            g.append(_box(f"{p}slab{'L' if s_ > 0 else 'R'}", (nx0, y0, 0), (cx0, y1, floor), m, col))
        g.append(_box(f"{p}slotfloor", (nx0, -slot_w, 0), (cx0, slot_w, slot_floor), m, col))'''
assert a in s; s = s.replace(a, b); open(p, 'w', encoding='utf-8').write(s); print('ok')
