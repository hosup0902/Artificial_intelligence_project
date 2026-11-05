p = 'battery_sim/devices.py'
s = open(p, encoding='utf-8').read()
a = '''                      grasp_x=max(nx0 - 0.022, -L / 2 + 0.012))'''
b = '''                      # (short remotes: only 10 mm behind the slot so the grasp stays near the centre of mass)
                      grasp_x=max(nx0 - (0.022 if L >= 0.16 else 0.010), -L / 2 + 0.012))'''
assert a in s; s = s.replace(a, b); open(p, 'w', encoding='utf-8').write(s); print('ok')
