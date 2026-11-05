p = 'battery_sim/devices.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b)


rep('''AA_COL = 2 * (AA_L / 2 - 0.0008)   # collision length of the cell body (nub/end discs are visual)''',
    '''AA_COL = 2 * (AA_L / 2 - 0.0008)   # collision length of the cell body (nub/end discs are visual)


@dataclass(frozen=True)
class CellType:
    """IEC cylindrical cell. ``pitch`` = centre spacing of the two cells: both crests must lie
    under the retaining lips, outside the central finger slot (|y| > SLOT_HALF_W)."""
    name: str
    r: float
    length: float
    mass: float
    pitch: float
    div_h: float          # centre divider height (must stay below the jaw tip during the push)

    @property
    def col_len(self):
        return 2 * (self.length / 2 - 0.0008)

    @property
    def div_hw(self):
        """Divider half-width: touches a cell's lower flank (0.2 mm clearance) at the divider top."""
        h = self.div_h - 0.0002
        chord = np.sqrt(self.r ** 2 - (self.r - h) ** 2)
        return self.pitch / 2 - chord - 0.0002


AA = CellType("AA", 0.00725, 0.0505, 0.023, 2 * 0.00725 + 0.0025, 0.0025)
AAA = CellType("AAA", 0.00525, 0.0445, 0.0115, 0.017, 0.0010)''')
rep('''    body_material: str = "plastic_remote"
    sticker_material: str = "sticker_remote"
''', '''    body_material: str = "plastic_remote"
    sticker_material: str = "sticker_remote"
    cell: CellType = AA
    name: str = "tv_remote"
    label: str = "TV 리모컨"
''')
rep('''    cell_pitch = 2 * AA_R + 0.0025
    inner_w = spec.n_cells * 2 * AA_R + (spec.n_cells - 1) * 0.0025 + 0.0005   # 0.25 mm side clearance''',
    '''    ct = spec.cell
    cell_pitch = ct.pitch
    inner_w = (spec.n_cells - 1) * cell_pitch + 2 * ct.r + 0.0005   # 0.25 mm side clearance''')
rep('''    comp_len = AA_COL + 0.0002''', '''    comp_len = ct.col_len + 0.0002''')
rep('''    lip_z0 = floor + 2 * AA_R + 0.0002 + 0.0003''', '''    lip_z0 = floor + 2 * ct.r + 0.0002 + 0.0003''')
rep('''        dw = 0.00315
        g.append(_box(f"{p}divider{i}", (cx0 + 0.0005, yd - dw, floor), (cx1, yd + dw, floor + 0.0025), m, col))
        g.append(f'<geom type="box" pos="{_f((cx0 + 0.0005 + cx1) / 2, yd, floor + 0.00125)}" '
                 f'size="{_f((cx1 - cx0 - 0.0005) / 2, dw, 0.00125)}" material="{m}_plain" contype="0" conaffinity="0" group="1"/>')''',
    '''        dw = 0.00315 if ct.name == "AA" else ct.div_hw
        dh = ct.div_h
        g.append(_box(f"{p}divider{i}", (cx0 + 0.0005, yd - dw, floor), (cx1, yd + dw, floor + dh), m, col))
        g.append(f'<geom type="box" pos="{_f((cx0 + 0.0005 + cx1) / 2, yd, floor + dh / 2)}" '
                 f'size="{_f((cx1 - cx0 - 0.0005) / 2, dw, dh / 2)}" material="{m}_plain" contype="0" conaffinity="0" group="1"/>')''')
rep('''    cz = floor + AA_R + 0.0002
    seat_x, seat_z, seat_tilt = _seated_pose(cx0, floor, lip_z0)''',
    '''    cz = floor + ct.r + 0.0002
    seat_x, seat_z, seat_tilt = _seated_pose(cx0, floor, lip_z0, ct)''')
rep('''    plunger_x = cx0 + 0.0001 + AA_COL + 0.0001 + 0.0006''', '''    plunger_x = cx0 + 0.0001 + ct.col_len + 0.0001 + 0.0006''')
rep('''(cx0 + cx1) / 2, 0, floor + AA_R)}" size="0.003" group="4"/>')''', '''(cx0 + cx1) / 2, 0, floor + ct.r)}" size="0.003" group="4"/>')''')
rep('''spec.cell_materials[i % len(spec.cell_materials)], tilt=seat_tilt))''',
    '''spec.cell_materials[i % len(spec.cell_materials)], tilt=seat_tilt,
                                            ct=ct))''')
rep('''def _seated_pose(cx0, floor, lip_z0):''', '''def _seated_pose(cx0, floor, lip_z0, ct=AA):''')
rep('''    r, half = AA_R, AA_COL / 2''', '''    r, half = ct.r, ct.col_len / 2''')
rep('''def aa_cell_xml(name, pos, yaw, material, tilt=0.0) -> str:''', '''def aa_cell_xml(name, pos, yaw, material, tilt=0.0, ct=AA) -> str:''')
rep('''size="{AA_R:.5f} {AA_L/2 - 0.0008:.5f}" material="{material}" '
            f'mass="{AA_MASS}" ''', '''size="{ct.r:.5f} {ct.col_len/2:.5f}" material="{material}" '
            f'mass="{ct.mass}" ''')
rep('''pos="0 0 {-AA_COL/2 - 0.0003:.5f}" size="0.0026 0.0003"''', '''pos="0 0 {-ct.col_len/2 - 0.0003:.5f}" size="{0.36 * ct.r:.5f} 0.0003"''')
rep('''pos="0 0 {AA_COL/2 - 0.0001:.5f}" size="{AA_R - 0.0008:.5f} 0.0002"''', '''pos="0 0 {ct.col_len/2 - 0.0001:.5f}" size="{ct.r - 0.0008:.5f} 0.0002"''')
rep('''    shell_mesh = f"{p}shell"''', '''    shell_mesh = f"{p}shell_{spec.name}"''')
rep('''                      nx0=nx0, slot_w=slot_w)''', '''                      nx0=nx0, slot_w=slot_w, cell_r=ct.r, cell_len=ct.col_len,
                      # jaw push height above the cell axis: jaw bottom >= divider top + 0.8 mm (jaw bottom is
                      # 6.6 mm below the tool origin, the push point 2.5 mm above it), never below 5 mm
                      push_h=max(0.005, ct.div_h + 0.0008 + 0.0066 + 0.0025 - (ct.r + 0.0002)),
                      # grasp on solid material behind the finger slot, not closer than 12 mm to the rear end
                      grasp_x=max(nx0 - 0.022, -L / 2 + 0.012))''')
rep('''def remote_body_xml(spec: RemoteSpec,''', '''DEVICES = {
    "tv_remote": RemoteSpec(),
    "stb_remote": RemoteSpec(name="stb_remote", label="셋톱박스 리모컨 (AAA)", length=0.165, width=0.046, thick=0.019,
                             cell=AAA, body_material="plastic_mouse", sticker_material="sticker_mouse",
                             cell_materials=["battery_b", "battery_b"]),
    "ac_remote": RemoteSpec(name="ac_remote", label="에어컨 리모컨", length=0.150, width=0.058, thick=0.026,
                            body_material="plastic_clock", sticker_material="sticker_clock"),
    "light_remote": RemoteSpec(name="light_remote", label="조명 리모컨 (AAA)", length=0.130, width=0.046, thick=0.019,
                               cell=AAA, body_material="navy", sticker_material="sticker_remote",
                               cell_materials=["battery_a", "battery_b"]),
}
DEVICE_ORDER = ["tv_remote", "stb_remote", "ac_remote", "light_remote"]


def remote_body_xml(spec: RemoteSpec,''')
open(p, 'w', encoding='utf-8').write(s)
print("patched; remaining AA_ refs in functions:", [l for l in s.splitlines() if ("AA_R" in l or "AA_COL" in l or "AA_MASS" in l) and not l.startswith("AA")])
