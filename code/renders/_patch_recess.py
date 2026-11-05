p = 'battery_sim/devices.py'
s = open(p, encoding='utf-8').read()
a = '''    slot_floor = floor - SLOT_RECESS'''
b = '''    slot_floor = floor - (SLOT_RECESS if ct.name != "AA" else 0.0)   # AA keeps the validated flat slot floor'''
assert a in s; s = s.replace(a, b)
a2 = '''    g.append(_box(f"{p}slotfloor", (nx0, -slot_w, 0), (cx0, slot_w, slot_floor), m, col))'''
b2 = '''    if slot_floor > 1e-4:
        g.append(_box(f"{p}slotfloor", (nx0, -slot_w, 0), (cx0, slot_w, slot_floor), m, col))'''
assert a2 in s; s = s.replace(a2, b2)
open(p, 'w', encoding='utf-8').write(s); print('ok')
