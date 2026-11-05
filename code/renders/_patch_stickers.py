def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, (p, a[:70]); s = s.replace(a, b)
    open(p, 'w', encoding='utf-8').write(s)
patch('battery_sim/textures.py', [('''    device_sticker(tex_dir / "sticker_clock.png", "DC-55", "DC 1.5V (AA x 1)")''',
 '''    device_sticker(tex_dir / "sticker_clock.png", "DC-55", "DC 1.5V (AA x 1)")
    device_sticker(tex_dir / "sticker_stb.png", "STB-700", "DC 3V (1.5V AAA x 2)")
    device_sticker(tex_dir / "sticker_ac.png", "AC-R12", "DC 3V (1.5V AA x 2)")
    device_sticker(tex_dir / "sticker_light.png", "LR-5", "DC 3V (1.5V AAA x 2)")''')])
patch('battery_sim/scene.py', [('''    "sticker_remote": ("sticker_remote.png", "1 1", False, 0.1, 0.1, 0.0),''',
 '''    "sticker_remote": ("sticker_remote.png", "1 1", False, 0.1, 0.1, 0.0),
    "sticker_stb": ("sticker_stb.png", "1 1", False, 0.1, 0.1, 0.0),
    "sticker_ac": ("sticker_ac.png", "1 1", False, 0.1, 0.1, 0.0),
    "sticker_light": ("sticker_light.png", "1 1", False, 0.1, 0.1, 0.0),''')])
patch('battery_sim/devices.py', [('sticker_material="sticker_mouse"', 'sticker_material="sticker_stb"'),
 ('sticker_material="sticker_clock"', 'sticker_material="sticker_ac"'),
 ('''cell=AAA, body_material="navy", sticker_material="sticker_remote",''', '''cell=AAA, body_material="navy", sticker_material="sticker_light",''')])
print('ok')
