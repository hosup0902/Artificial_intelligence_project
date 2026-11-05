p = 'battery_sim/policy.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:70]; s = s.replace(a, b)
rep('''        h = self.push_h + 0.001 * attempt
        start = plus - x * 0.003 + z * h''', '''        h = self.push_h
        # retries: shift the jaw sideways (the slot leaves ~1 mm of play) toward a cell that is still latched,
        # so that its + end face gets more of the jaw (AAA faces overlap the jaw by only ~3.5 mm)
        lat0 = self.cells_latched()
        yoff = 0.0
        if attempt > 0 and any(lat0) and not all(lat0):
            yoff = 0.0009 * (1 if lat0[1] else -1)                     # cell1 at +y, cell0 at -y
        elif attempt > 0:
            yoff = 0.0009 * (1 if attempt % 2 else -1)
        y = R[:, 1]
        plus = plus + y * yoff
        start = plus - x * 0.003 + z * h''')
rep('''        while k < 30:''', '''        while k < 34:''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
