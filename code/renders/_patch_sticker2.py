p = 'battery_sim/devices.py'
s = open(p, encoding='utf-8').read()
a = '''    g.append(_box(f"{p}sticker", (-L / 2 + 0.015, -W / 2 + 0.008, T), (-L / 2 + 0.075, W / 2 - 0.008, T + 0.0003),'''
b = '''    sx1 = min(-L / 2 + 0.075, nx0 - 0.004)          # keep the sticker clear of the finger slot
    g.append(_box(f"{p}sticker", (-L / 2 + 0.012, -W / 2 + 0.008, T), (sx1, W / 2 - 0.008, T + 0.0003),'''
assert a in s; s = s.replace(a, b); open(p, 'w', encoding='utf-8').write(s); print('ok')
