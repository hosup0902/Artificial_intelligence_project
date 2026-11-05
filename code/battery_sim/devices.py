"""MJCF generators for the waste appliances (폐가전) used in the battery-removal task.

Each device is lying battery-side up. Coordinates in a device frame: x along the
long axis (battery end toward +x), z = 0 at the face touching the table.

The battery compartment follows the construction of a real remote control:
  * battery cover   : separate free body sitting in a recess; side rims and the rear
                      wall leave only +x open, so it can only be slid off toward +x.
                      A weld equality ``<prefix>latch`` models the snap latch; the env
                      releases it only when the cover is pressed down AND pushed along +x
                      (press-and-slide), like the flexible latch tab of a real cover.
  * - terminal      : sprung coil-spring plunger (slide joint with stiffness), 0.6 N preload, with a contact
                      plate as tall as the pocket.
  * + terminal      : flat contact plate on the end stop.
  * retaining lips  : rigid tabs over the top of each + end. A seated cell lies flat on the
                      pocket floor with its + end trapped under the lip (0.5 mm play): it can
                      neither be lifted nor tipped out, even upside down and shaken.
                      Pushing it toward the spring alone does not free it either: the spring
                      pushes it straight back under the lip. The + end has to be pushed past
                      the lip AND lifted above the lip top, which is what a pry tool does.
  * pry notch       : notch behind the + ends (19 mm wide, 10 mm long), whose floor is recessed 3 mm and continues
                      16 mm under the + ends, so a thin pry tool with a wide hooked tip can reach under
                      both cell ends; above the cells the lips leave only a 9.6 mm gap (< any cell).
  * cells           : free bodies with IEC dimensions (AA 14.5 x 50.5 mm, 23 g; AAA 10.5 x 44.5 mm, 11.5 g).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class CellType:
    """IEC cylindrical cell. ``pitch`` = centre spacing of the two cells."""
    name: str
    r: float
    length: float
    mass: float
    pitch: float
    div_h: float          # centre divider height

    @property
    def col_len(self):
        return 2 * (self.length / 2 - 0.0008)

    @property
    def div_hw(self):
        """Divider half-width: touches a cell's lower flank (0.2 mm clearance) at the divider top."""
        h = self.div_h - 0.0002
        chord = np.sqrt(self.r ** 2 - (self.r - h) ** 2)
        return self.pitch / 2 - chord - 0.0002


AA = CellType("AA", 0.00725, 0.0505, 0.023, 0.016, 0.0025)       # 1.5 mm rib between the cells
AAA = CellType("AAA", 0.00525, 0.0445, 0.0115, 0.017, 0.0012)
AA_R, AA_L, AA_MASS = AA.r, AA.length, AA.mass
SPRING_K = 400.0                   # N/m coil spring (1.5 mm preload -> 0.6 N; ~3 N when pushed past the lip)
SPRING_STROKE = 0.0100             # plunger travel beyond the seated position
LIP_LEN = 0.0045                   # retaining lip overhang over the + ends (m)
LIP_GAP = 0.0005                   # play between a seated cell's crest and the lip underside
SLOT_HALF_W = 0.0095               # pry notch half-width: just outside both cells' lowest lines (|y| = 8-8.5 mm),
                                   # so the tool foot (+-8.4 mm) lifts the cells from below, not by wedging between them
LIP_IN = 0.0048                    # retaining lips start at |y| = 4.8 mm: the 9.6 mm gap between them is narrower
                                   # than any cell (AAA 10.5 mm), the pry tool's 8 mm neck passes through it
SLOT_LEN = 0.010                   # pry notch length behind the + end stop (short: a cell cannot drop into it)
PRY_DEPTH = 0.003                  # notch floor sits 3 mm below the pocket floor ...
PRY_EXT = 0.016                    # ... and the recess continues 16 mm under the + ends
REAR_LIP = 0.004                   # end-stop thickness between the cover recess and the pocket
# light parts (cells 11-23 g): stiff contacts, otherwise MuJoCo's mass-scaled soft contacts let a tool
# sink millimetres into a cell before it moves
STIFF = 'solref="0.005 1"'
METAL = f'friction="0.12 0.005 0.0001" priority="2" {STIFF}'   # nickel-plated coil-spring contact
LIP_METAL = f'friction="0.10 0.005 0.0001" priority="2" {STIFF}'   # + terminal tab (retaining lip)


def _f(*v) -> str:
    return " ".join(f"{x:.5g}" for x in v)


def _box(name, lo, hi, material, extra="") -> str:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c, h = (lo + hi) / 2, (hi - lo) / 2
    nm = f'name="{name}" ' if name else ""
    return f'<geom {nm}type="box" pos="{_f(*c)}" size="{_f(*h)}" material="{material}" {extra}/>'


@dataclass
class RemoteSpec:
    """Remote control with a slide-off battery cover and 2 cylindrical cells."""

    prefix: str = "remote_"
    length: float = 0.180
    width: float = 0.050
    thick: float = 0.022
    n_cells: int = 2
    cell_materials: list[str] = field(default_factory=lambda: ["battery_a", "battery_a"])
    body_material: str = "plastic_remote"
    sticker_material: str = "sticker_remote"
    cell: CellType = AA
    name: str = "tv_remote"
    label: str = "TV 리모컨"


DEVICES = {
    "tv_remote": RemoteSpec(),
    "stb_remote": RemoteSpec(name="stb_remote", label="셋톱박스 리모컨 (AAA)", length=0.165, width=0.046, thick=0.019,
                             cell=AAA, body_material="plastic_mouse", sticker_material="sticker_stb",
                             cell_materials=["battery_b", "battery_b"]),
    "ac_remote": RemoteSpec(name="ac_remote", label="에어컨 리모컨", length=0.150, width=0.058, thick=0.026,
                            body_material="plastic_clock", sticker_material="sticker_ac"),
    "light_remote": RemoteSpec(name="light_remote", label="조명 리모컨 (AAA)", length=0.130, width=0.046, thick=0.019,
                               cell=AAA, body_material="navy", sticker_material="sticker_light",
                               cell_materials=["battery_a", "battery_b"]),
}
DEVICE_ORDER = ["tv_remote", "stb_remote", "ac_remote", "light_remote"]


def remote_body_xml(spec: RemoteSpec, pos, yaw: float, with_cover=True, cover_offset=0.0,
                    cells_in=True, freejoint=True):
    """Return (body_xml, equality_xml, extra_bodies, cell_body_names, asset_xml, dims).

    Cells and the cover are separate top-level bodies (free joints), placed in
    world coordinates computed from the device pose.
    """
    p = spec.prefix
    L, W, T = spec.length, spec.width, spec.thick
    floor = 0.004                      # bottom slab (button side)
    cov_t = 0.0016                     # cover thickness
    cov_z0 = T - cov_t                 # cover underside = top of the pocket walls / lips
    ct = spec.cell
    cell_pitch = ct.pitch
    inner_w = (spec.n_cells - 1) * cell_pitch + 2 * ct.r + 0.0005   # 0.25 mm side clearance
    hw_in = inner_w / 2
    rim = 0.003
    ledge_w = (W / 2 - rim) - hw_in    # ledge supporting the cover edges
    end_wall = 0.007
    # spring: 1.5 mm preload when the cell is seated, SPRING_STROKE further travel before the stop
    comp_len = ct.col_len + 0.0002 + 0.0012 + SPRING_STROKE + 0.0006
    cx1 = L / 2 - end_wall             # compartment +x end (spring side)
    cx0 = cx1 - comp_len               # compartment -x end (+ contact side)
    rx = cx0 - REAR_LIP                # start of the cover recess
    slot_w = SLOT_HALF_W
    nx0 = cx0 - SLOT_LEN               # pry notch: x in [nx0, cx0 + PRY_EXT], |y| < slot_w
    px1 = cx0 + PRY_EXT
    slot_floor = floor - PRY_DEPTH
    lip_z0 = floor + 2 * ct.r + 0.0001 + LIP_GAP      # lip underside
    m = spec.body_material

    g = []
    # collision shell: boxes (hidden, group 3). Visual: rounded CSG mesh below.
    col = f'group="3" rgba="0.5 0.5 0.5 1" friction="0.35 0.005 0.0001" {STIFF}'
    wall = f'group="3" rgba="0.5 0.5 0.5 1" friction="0.2 0.005 0.0001" {STIFF}'   # smooth moulded pocket walls
    # bottom slab with the recessed notch floor
    g.append(_box(f"{p}slab", (-L / 2, -W / 2, 0), (nx0, W / 2, floor), m, col))
    g.append(_box(f"{p}slabF", (px1, -W / 2, 0), (L / 2, W / 2, floor), m, col))
    for s_ in (-1, 1):
        y0, y1 = sorted((s_ * slot_w, s_ * W / 2))
        g.append(_box(f"{p}slab{'L' if s_ > 0 else 'R'}", (nx0, y0, 0), (px1, y1, floor), m, col))
    g.append(_box(f"{p}slotfloor", (nx0, -slot_w, 0), (px1, slot_w, slot_floor), m, col))
    # solid rear section, notch side walls, + end stop and retaining lips
    g.append(_box(f"{p}rear", (-L / 2, -W / 2, floor), (nx0, W / 2, T), m, col))
    for s in (-1, 1):
        tag = "L" if s > 0 else "R"
        y0, y1 = sorted((s * slot_w, s * W / 2))
        g.append(_box(f"{p}rear{tag}", (nx0, y0, floor), (rx, y1, T), m, col))          # notch side walls
        y0, y1 = sorted((s * slot_w, s * hw_in))
        g.append(_box(f"{p}rearwall{tag}", (rx, y0, floor), (cx0, y1, cov_z0), m, col))  # + end stop beside the notch
        y0, y1 = sorted((s * LIP_IN, s * hw_in))
        g.append(_box(f"{p}lip{tag}", (cx0, y0, lip_z0), (cx0 + LIP_LEN, y1, cov_z0), m,
                      'group="3" rgba="0.5 0.5 0.5 1" ' + LIP_METAL))
        g.append(f'<geom type="box" pos="{_f(cx0 + LIP_LEN / 2, (y0 + y1) / 2, (lip_z0 + cov_z0) / 2)}" '
                 f'size="{_f(LIP_LEN / 2, (y1 - y0) / 2, (cov_z0 - lip_z0) / 2)}" material="{m}_plain" '
                 f'contype="0" conaffinity="0" group="1"/>')
    g.append(_box(f"{p}endwall", (cx1, -hw_in, floor), (L / 2, hw_in, cov_z0), m, col))
    # low centre divider between the cells (behind the pry recess)
    for i in range(spec.n_cells - 1):
        yd = (i + 0.5 - (spec.n_cells - 1) / 2) * cell_pitch
        dw, dh = ct.div_hw, ct.div_h
        x0d = px1 + 0.0005
        g.append(_box(f"{p}divider{i}", (x0d, yd - dw, floor), (cx1, yd + dw, floor + dh), m, col))
        g.append(f'<geom type="box" pos="{_f((x0d + cx1) / 2, yd, floor + dh / 2)}" '
                 f'size="{_f((cx1 - x0d) / 2, dw, dh / 2)}" material="{m}_plain" contype="0" conaffinity="0" group="1"/>')
    for s in (-1, 1):
        y0, y1 = sorted((s * hw_in, s * (hw_in + ledge_w)))
        g.append(_box(f"{p}ledge{'L' if s > 0 else 'R'}", (rx, y0, floor), (L / 2, y1, cov_z0), m, wall))
        y0, y1 = sorted((s * (W / 2 - rim), s * W / 2))
        g.append(_box(f"{p}rim{'L' if s > 0 else 'R'}", (rx, y0, floor), (L / 2, y1, T), m, col))
    shell_mesh = f"{p}shell_{spec.name}"
    g.append(f'<geom type="mesh" mesh="{shell_mesh}" material="{m}_plain" contype="0" conaffinity="0" group="1"/>')
    asset_xml = f'<mesh name="{shell_mesh}" file="devices/{shell_mesh}.obj"/>'
    shell_dims = dict(L=L, W=W, T=T, floor=floor, cov_z0=cov_z0, hw_in=hw_in, rim=rim, cx0=cx0, cx1=cx1, rx=rx,
                      nx0=nx0, px1=px1, slot_w=slot_w, slot_floor=slot_floor, lip_z0=lip_z0, lip_len=LIP_LEN,
                      cell_r=ct.r, cell_len=ct.col_len, cell_pitch=cell_pitch,
                      # arm R grasps the solid section 28 mm behind the pry notch (closer, its fingers disturb the
                      # raised cells; the open pocket must stay clear so the cells can fall out)
                      grasp_x=max(cx0 - 0.044, -L / 2 + 0.014), hold_x=max(cx0 - 0.044, -L / 2 + 0.014))
    # rating sticker on the exposed underside region (now facing up)
    sx1 = min(-L / 2 + 0.075, nx0 - 0.004)          # keep the sticker clear of the notch
    g.append(_box(f"{p}sticker", (-L / 2 + 0.012, -W / 2 + 0.008, T), (sx1, W / 2 - 0.008, T + 0.0003),
                  spec.sticker_material, 'contype="0" conaffinity="0" group="1"'))
    cz = floor + ct.r + 0.0001
    seat_x = cx0 + 0.0001 + ct.col_len / 2
    plunger_x = cx0 + 0.0001 + ct.col_len + 0.0001 + 0.0006
    for i in range(spec.n_cells):
        yc = (i - (spec.n_cells - 1) / 2) * cell_pitch
        # + contact plate on the end stop beside the notch (visual)
        ys = yc + np.sign(yc) * 0.0035
        g.append(_box("", (cx0 - 0.0004, ys - 0.0025, floor + 0.002), (cx0, ys + 0.0025, floor + 2 * ct.r - 0.002),
                      "metal_contact", 'contype="0" conaffinity="0" group="1"'))
        # conical coil spring (visual): rings of decreasing radius between the plate and the end wall
        n_ring = 6
        for k in range(n_ring):
            xk = plunger_x + 0.0012 + (cx1 - plunger_x - 0.0016) * k / (n_ring - 1)
            rk = 0.0047 - 0.0017 * k / (n_ring - 1)
            g.append(f'<geom type="cylinder" fromto="{_f(xk - 0.0004, yc, cz, xk + 0.0004, yc, cz)}" size="{rk:.5f}" '
                     f'material="metal_spring" contype="0" conaffinity="0" group="1"/>')
        g.append(f'<geom type="cylinder" fromto="{_f(plunger_x + 0.0006, yc, cz, cx1, yc, cz)}" '
                 f'size="0.0015" material="metal_spring" contype="0" conaffinity="0" group="1"/>')
    # sites: pocket centre (flip planning), + end stop face centre (pry skill)
    g.append(f'<site name="{p}comp" pos="{_f((cx0 + cx1) / 2, 0, floor + ct.r)}" size="0.003" group="4"/>')
    g.append(f'<site name="{p}plus" pos="{_f(cx0, 0, cz)}" size="0.002" group="4"/>')

    # spring plungers (one per cell) as child bodies with sprung slide joints (+x = compression)
    plungers = []
    pz_lo, pz_hi = floor + 0.0008 - cz, cov_z0 - 0.0003 - cz          # plate extent relative to the cell axis
    pz_c, pz_h = (pz_lo + pz_hi) / 2, (pz_hi - pz_lo) / 2
    for i in range(spec.n_cells):
        yc = (i - (spec.n_cells - 1) / 2) * cell_pitch
        plungers.append(
            f'<body name="{p}plunger{i}" pos="{_f(plunger_x, yc, cz)}">'
            f'<joint name="{p}spring{i}" type="slide" axis="1 0 0" range="-0.0015 {SPRING_STROKE}" stiffness="{SPRING_K}" '
            f'springref="-0.0015" damping="0.4"/>'
            # tall contact plate (floor+0.8 mm .. pocket top-0.3 mm): an upside-down cell whose - end lifts by a
            # few mm still bears on the spring, so it stays pressed against the + stop under the lip
            f'<geom type="box" pos="0 0 {pz_c:.5f}" size="0.0006 {min(0.005, ct.r - 0.0003):.4f} {pz_h:.5f}" '
            f'material="metal_contact" mass="0.002" {METAL}/></body>')

    c, s_ = np.cos(yaw), np.sin(yaw)
    quat = (np.cos(yaw / 2), 0, 0, np.sin(yaw / 2))
    jt = f'<freejoint name="{p}free"/>' if freejoint else ""
    body = (f'<body name="{p}body" pos="{_f(*pos)}" quat="{_f(*quat)}">{jt}'
            f'<inertial pos="0 0 {T/2:.4f}" mass="0.075" diaginertia="2.2e-4 2.0e-5 2.3e-4"/>'
            + "".join(g) + "".join(plungers) + "</body>")

    def to_world(local):
        lx, ly, lz = local
        return np.array([pos[0] + c * lx - s_ * ly, pos[1] + s_ * lx + c * ly, pos[2] + lz])

    extra_bodies = []
    cells = []
    if cells_in:
        for i in range(spec.n_cells):
            yc = (i - (spec.n_cells - 1) / 2) * cell_pitch
            wp = to_world((seat_x, yc, cz))
            name = f"{p}cell{i}"
            cells.append(name)
            extra_bodies.append(aa_cell_xml(name, wp, yaw, spec.cell_materials[i % len(spec.cell_materials)], ct=ct))
    eq = ""
    if with_cover:
        cov_lo = np.array([rx + 0.0003, -(W / 2 - rim) + 0.0003, cov_z0])
        cov_hi = np.array([L / 2, (W / 2 - rim) - 0.0003, T])
        cc = (cov_lo + cov_hi) / 2 + np.array([cover_offset, 0, 0])
        hh = (cov_hi - cov_lo) / 2
        wp = to_world(cc)
        ridges = "".join(
            f'<geom type="box" pos="{_f(-hh[0] + 0.006 + k * 0.0035, 0, hh[2] + 0.0003)}" size="0.0006 {hh[1]*0.6:.4f} 0.0004" '
            f'material="{m}_plain" mass="0.0001"/>' for k in range(4))
        arrow = (f'<geom type="box" pos="{_f(0.004, 0, hh[2] + 0.0001)}" size="0.006 0.0012 0.0001" '
                 f'material="emboss" contype="0" conaffinity="0" group="1"/>'
                 f'<geom type="box" pos="{_f(0.011, 0.002, hh[2] + 0.0001)}" size="0.0025 0.0008 0.0001" euler="0 0 -0.7" '
                 f'material="emboss" contype="0" conaffinity="0" group="1"/>'
                 f'<geom type="box" pos="{_f(0.011, -0.002, hh[2] + 0.0001)}" size="0.0025 0.0008 0.0001" euler="0 0 0.7" '
                 f'material="emboss" contype="0" conaffinity="0" group="1"/>')
        extra_bodies.append(
            f'<body name="{p}cover" pos="{_f(*wp)}" quat="{_f(*quat)}"><freejoint name="{p}cover_free"/>'
            f'<geom name="{p}cover_plate" type="box" size="{_f(*hh)}" material="{m}_plain" mass="0.006" friction="0.3 0.005 0.0001"/>'
            + ridges + arrow + "</body>")
        if cover_offset == 0.0:
            eq = f'<weld name="{p}latch" body1="{p}cover" body2="{p}body" solref="0.004 1"/>'
    return body, eq, extra_bodies, cells, asset_xml, shell_dims


def aa_cell_xml(name, pos, yaw, material, tilt=0.0, ct=AA) -> str:
    """Cylindrical cell with its axis along the device x axis (rotated by ``yaw``); ``tilt`` raises the + end."""
    # cylinder axis is local z; rotate z->x (with tilt about y) then yaw about world z
    a = np.pi / 2 + tilt
    q_y = np.array([np.cos(a / 2), 0, np.sin(a / 2), 0])
    q_z = np.array([np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)])
    q = _qmul(q_z, q_y)
    return (f'<body name="{name}" pos="{_f(*pos)}" quat="{_f(*q)}"><freejoint name="{name}_free"/>'
            f'<geom name="{name}_geom" type="cylinder" size="{ct.r:.5f} {ct.col_len/2:.5f}" material="{material}" '
            f'mass="{ct.mass}" condim="4" friction="0.25 0.01 0.001" {STIFF}/>'
            f'<geom type="cylinder" pos="0 0 {-ct.col_len/2 - 0.0003:.5f}" size="{0.36 * ct.r:.5f} 0.0003" material="metal_contact" '
            f'contype="0" conaffinity="0" group="1"/>'
            f'<geom type="cylinder" pos="0 0 {ct.col_len/2 - 0.0001:.5f}" size="{ct.r - 0.0008:.5f} 0.0002" material="metal_contact" '
            f'contype="0" conaffinity="0" group="1"/></body>')


def _qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])


# ---------------------------------------------------------------------------
# Static decorative e-waste (queue crate, background) – simple, textured
# ---------------------------------------------------------------------------

def decor_remote(name, pos, euler, top_mat="remote_top", body_mat="plastic_remote") -> str:
    return (f'<body name="{name}" pos="{_f(*pos)}" euler="{_f(*euler)}">'
            f'<geom type="box" size="0.025 0.09 0.010" material="{body_mat}"/>'
            f'<geom type="box" pos="0 0 0.0101" size="0.024 0.088 0.0002" material="{top_mat}" contype="0" conaffinity="0"/>'
            f'</body>')


def decor_mouse(name, pos, euler, mat="plastic_mouse") -> str:
    return (f'<body name="{name}" pos="{_f(*pos)}" euler="{_f(*euler)}">'
            f'<geom type="ellipsoid" size="0.032 0.058 0.019" material="{mat}"/>'
            f'<geom type="box" pos="0 -0.03 0.014" size="0.0015 0.022 0.004" material="plastic_remote" contype="0" conaffinity="0"/>'
            f'<geom type="cylinder" pos="0 -0.035 0.017" size="0.004 0.004" euler="0 1.5708 0" material="plastic_remote" contype="0" conaffinity="0"/>'
            f'</body>')


def decor_clock(name, pos, euler) -> str:
    return (f'<body name="{name}" pos="{_f(*pos)}" euler="{_f(*euler)}">'
            f'<geom type="box" size="0.055 0.020 0.045" material="plastic_clock"/>'
            f'<geom type="box" pos="0 -0.0201 0" size="0.045 0.0002 0.035" material="clock_face" contype="0" conaffinity="0"/>'
            f'</body>')


def decor_keyboard(name, pos, euler) -> str:
    return (f'<body name="{name}" pos="{_f(*pos)}" euler="{_f(*euler)}">'
            f'<geom type="box" size="0.22 0.075 0.012" material="plastic_remote"/>'
            f'<geom type="box" pos="0 0 0.0121" size="0.215 0.07 0.0002" material="keyboard" contype="0" conaffinity="0"/>'
            f'</body>')


def decor_phone(name, pos, euler) -> str:
    return (f'<body name="{name}" pos="{_f(*pos)}" euler="{_f(*euler)}">'
            f'<geom type="box" size="0.026 0.052 0.007" material="plastic_mouse"/>'
            f'<geom type="box" pos="0 0.005 0.0071" size="0.022 0.04 0.0002" material="screen_dark" contype="0" conaffinity="0"/>'
            f'</body>')


def write_remote_shell(dims: dict, path) -> None:
    """Rounded remote housing with the battery pocket and cover recess cut out (visual only)."""
    import manifold3d as mf
    import trimesh

    L, W, T, r = dims["L"], dims["W"], dims["T"], 0.006
    sph = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (r, T - r):
                sph.append(mf.Manifold.sphere(r, 24).translate((sx * (L / 2 - r), sy * (W / 2 - r), z)))
    body = mf.Manifold.batch_hull(sph)
    # keep the faces flat where the cover sits: a sharp-cornered cap over the top
    def cube(lo, hi):
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        return mf.Manifold.cube(tuple(hi - lo)).translate(tuple(lo))
    pocket = cube((dims["cx0"], -dims["hw_in"], dims["floor"]), (dims["cx1"], dims["hw_in"], T + 0.01))
    recess = cube((dims["rx"], -(W / 2 - dims["rim"]), dims["cov_z0"]), (L / 2 + 0.01, W / 2 - dims["rim"], T + 0.01))
    slot = cube((dims["nx0"], -dims["slot_w"], dims["slot_floor"]), (dims["px1"], dims["slot_w"], T + 0.01))
    shell = body - pocket - recess - slot
    mesh = shell.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tm.export(str(path))
