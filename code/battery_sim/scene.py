"""Build the MJCF for the e-waste battery-removal workstation.

Layout (metres, robot base at the origin on the bench surface, arm facing +x):

    back wall (sandwich panel, posters)            x = 0.95
    pegboard upright + shelf + task light          x = 0.62
    ┌──────────────── steel workbench + ESD mat ────────────────┐
    │  body crate (y<0)     disassembly jig (x≈0.22)   battery bin (y>0) │
    │                         SO-101 at origin                  │
    └────────────────────────────────────────────────────────────┘
    green epoxy floor z = -0.85, hazard tape around the cell.

Everything the policy touches (jig, bins, device, cells, cover) is within the
SO-101 top-down reach (~0.36 m). Decor (tools, queue crate, ton bag, shelving)
is static and placed outside the reach so it cannot interfere with the task.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from battery_sim import devices as dv

MJCF_DIR = Path(__file__).resolve().parent / "mjcf"
FLOOR_Z = -0.85
# disassembly jig (tray) geometry; the +x fence inner face is at JIG_CX + JIG_HX - 0.008
JIG_CX, JIG_CY, JIG_HX, JIG_HY = 0.20, 0.0, 0.13, 0.085
JIG_TOP = 0.006
FENCE_X = JIG_CX + JIG_HX - 0.008
NOMINAL_REMOTE_POSE = (0.205, 0.005, JIG_TOP + 0.0002)


def nominal_pose(spec):
    """Spawn pose of a device: battery end 27 mm short of the jig fence (same as the TV remote)."""
    return (FENCE_X - spec.length / 2 - 0.027, 0.005, JIG_TOP + 0.0002)
BATTERY_BIN = dict(center=(0.12, 0.33, 0.0), size=(0.11, 0.11, 0.085))
# second SO-101 ("tool arm", joint/body names prefixed "l_") across the jig, facing the main arm
LEFT_BASE = (0.50, 0.0, 0.0)
LEFT_YAW = np.pi
# pry tool rack next to the tool arm; the tool hangs in it with its hooked tip pointing along +RACK_DIR
# fork-type tool holder: the slot is open toward -x, the tool is lifted 4 mm and slid out along -x
TOOL_RACK = dict(center=(0.32, -0.14), plate_z=0.046)
TOOL_LEN = dict(tip_to_collar=0.033, handle=0.055)
TOOL_FOOT_ANGLE = np.radians(10.0)
BODY_CRATE = dict(center=(0.075, -0.27, 0.0), size=(0.18, 0.24, 0.075))
CACHE = Path.home() / ".cache" / "so101_nexus"

DECOR_MESHES = {
    "screwdriver": "043_phillips_screwdriver",
    "scissors": "037_scissors",
    "marker": "040_large_marker",
    "gaffer": "Shurtape_Gaffers_Tape_Silver_2_x_60_yd",
    "vinyl": "3M_Vinyl_Tape_Green_1_x_36_yd",
    "clamp": "Pony_C_Clamp_1440",
}


def _f(*v) -> str:
    return " ".join(f"{x:.5g}" for x in v)


def _box(lo, hi, mat, extra="", name="") -> str:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    nm = f'name="{name}" ' if name else ""
    return f'<geom {nm}type="box" pos="{_f(*(lo + hi) / 2)}" size="{_f(*(hi - lo) / 2)}" material="{mat}" {extra}/>'


def _cam(name, pos, target, fovy=45.0) -> str:
    pos, target = np.asarray(pos, float), np.asarray(target, float)
    fwd = target - pos
    fwd /= np.linalg.norm(fwd)
    x = np.cross(fwd, [0, 0, 1.0])
    x /= np.linalg.norm(x)
    y = np.cross(x, fwd)
    return f'<camera name="{name}" pos="{_f(*pos)}" xyaxes="{_f(*x, *y)}" fovy="{fovy}"/>'


def _open_box(name, center, size, t, mat, label_mat=None, label_face="-x") -> str:
    """Open-top bin. center = (x, y, z_bottom); size = (lx, ly, h)."""
    cx, cy, z0 = center
    lx, ly, h = size
    # thick base: falling cells (~2 m/s, 4 mm per 2 ms step) must not tunnel through a thin floor
    g = [_box((cx - lx / 2, cy - ly / 2, z0), (cx + lx / 2, cy + ly / 2, z0 + 0.012), mat, name=f"{name}_floor"),
         _box((cx - lx / 2, cy - ly / 2, z0), (cx - lx / 2 + t, cy + ly / 2, z0 + h), mat),
         _box((cx + lx / 2 - t, cy - ly / 2, z0), (cx + lx / 2, cy + ly / 2, z0 + h), mat),
         _box((cx - lx / 2, cy - ly / 2, z0), (cx + lx / 2, cy - ly / 2 + t, z0 + h), mat),
         _box((cx - lx / 2, cy + ly / 2 - t, z0), (cx + lx / 2, cy + ly / 2, z0 + h), mat)]
    if label_mat:
        m = 0.012
        if label_face == "both":
            g.append(_box((cx - lx / 2 + m, cy - ly / 2 - 0.0006, z0 + h * 0.2), (cx + lx / 2 - m, cy - ly / 2 - 0.0002, z0 + h * 0.85),
                          label_mat + "_y", 'contype="0" conaffinity="0" group="1"'))
            label_face = "-x"
        if label_face == "-x":
            g.append(_box((cx - lx / 2 - 0.0006, cy - ly / 2 + m, z0 + h * 0.2), (cx - lx / 2 - 0.0002, cy + ly / 2 - m, z0 + h * 0.85),
                          label_mat, 'contype="0" conaffinity="0" group="1"'))
        else:  # -y
            g.append(_box((cx - lx / 2 + m, cy - ly / 2 - 0.0006, z0 + h * 0.2), (cx + lx / 2 - m, cy - ly / 2 - 0.0002, z0 + h * 0.85),
                          label_mat, 'contype="0" conaffinity="0" group="1"'))
    # region site for success checks (inner volume)
    g.append(f'<site name="{name}_region" type="box" pos="{_f(cx, cy, z0 + h / 2)}" size="{_f(lx / 2 - t, ly / 2 - t, h / 2)}" '
             f'rgba="0 1 0 0.0" group="4"/>')
    return f'<body name="{name}">' + "".join(g) + "</body>"


def _copy_decor_meshes() -> dict[str, tuple[str, str]]:
    """Copy scanned decor meshes (YCB/GSO, CC-BY) into the mjcf folder for reproducibility."""
    out = {}
    dst_root = MJCF_DIR / "assets" / "decor"
    for key, model_id in DECOR_MESHES.items():
        dst = dst_root
        if not (dst / f"{key}_visual.obj").exists():
            src = next(CACHE.glob(f"*/*/*/{model_id}"), None)
            if src is None:
                from so101_nexus.gso_assets import ensure_gso_assets
                from so101_nexus.ycb_assets import ensure_ycb_assets
                src = ensure_ycb_assets(model_id) if model_id[:3].isdigit() else ensure_gso_assets(model_id)
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / "visual.obj", dst / f"{key}_visual.obj")
            shutil.copy(src / "texture.png", dst / f"{key}_texture.png")
        out[key] = (f"decor/{key}_visual.obj", f"decor/{key}_texture.png")
    return out


TEXTURED = {
    # name: (file, texrepeat, texuniform, specular, shininess, reflectance)
    "floor_epoxy": ("floor_epoxy.png", "3 3", True, 0.4, 0.5, 0.08),
    "wall_panel": ("wall_panel.png", "1.2 1.2", True, 0.1, 0.1, 0.0),
    "ceiling": ("ceiling.png", "1 1", True, 0.0, 0.0, 0.0),
    "hazard": ("hazard.png", "1 1", False, 0.2, 0.2, 0.0),
    "esd_mat": ("esd_mat.png", "1.5 1.5", True, 0.05, 0.05, 0.0),
    "steel_brushed": ("steel_brushed.png", "2 2", True, 0.8, 0.7, 0.05),
    "steel_blue": ("steel_blue.png", "4 4", True, 0.4, 0.4, 0.0),
    "steel_grey": ("steel_grey.png", "4 4", True, 0.4, 0.4, 0.0),
    "pegboard": ("pegboard.png", "2 1", False, 0.3, 0.3, 0.0),
    "poster_zone": ("poster_zone_mx.png", "1 1", False, 0.1, 0.1, 0.0),
    "poster_fire": ("poster_fire_mx.png", "1 1", False, 0.1, 0.1, 0.0),
    "poster_rules": ("poster_rules_mx.png", "1 1", False, 0.1, 0.1, 0.0),
    "label_battery_bin": ("label_battery_bin_mx.png", "1 1", False, 0.2, 0.2, 0.0),
    "label_battery_bin_y": ("label_battery_bin.png", "1 1", False, 0.2, 0.2, 0.0),
    "label_body_bin": ("label_body_bin_mx.png", "1 1", False, 0.2, 0.2, 0.0),
    "label_input": ("label_input_mx.png", "1 1", False, 0.2, 0.2, 0.0),
    "plastic_remote": ("plastic_remote.png", "1 1", False, 0.3, 0.3, 0.0),
    "plastic_mouse": ("plastic_mouse.png", "1 1", False, 0.4, 0.4, 0.0),
    "plastic_clock": ("plastic_clock.png", "1 1", False, 0.3, 0.3, 0.0),
    "plastic_red_bin": ("plastic_red_bin.png", "1 1", False, 0.3, 0.3, 0.0),
    "plastic_blue_crate": ("plastic_blue_crate.png", "1 1", False, 0.3, 0.3, 0.0),
    "plastic_grey_tray": ("plastic_grey_tray.png", "1 1", False, 0.2, 0.2, 0.0),
    "sticker_remote": ("sticker_remote.png", "1 1", False, 0.1, 0.1, 0.0),
    "sticker_stb": ("sticker_stb.png", "1 1", False, 0.1, 0.1, 0.0),
    "sticker_ac": ("sticker_ac.png", "1 1", False, 0.1, 0.1, 0.0),
    "sticker_light": ("sticker_light.png", "1 1", False, 0.1, 0.1, 0.0),
    "battery_a": ("battery_a.png", "1 1", False, 0.6, 0.6, 0.0),
    "battery_b": ("battery_b.png", "1 1", False, 0.6, 0.6, 0.0),
    "keyboard": ("keyboard.png", "1 1", False, 0.2, 0.2, 0.0),
    "remote_top": ("remote_top.png", "1 1", False, 0.3, 0.3, 0.0),
    "remote_top2": ("remote_top2.png", "1 1", False, 0.3, 0.3, 0.0),
}

PLAIN = {
    "metal_contact": "0.80 0.80 0.78 1",
    "metal_spring": "0.70 0.70 0.68 1",
    "emboss": "0.18 0.18 0.20 1",
    "clock_face": "0.95 0.95 0.92 1",
    "screen_dark": "0.05 0.06 0.08 1",
    "aluminum": "0.78 0.80 0.82 1",
    "rubber": "0.08 0.08 0.08 1",
    "wood": "0.62 0.48 0.30 1",
    "tonbag": "0.88 0.88 0.84 1",
    "cardboard": "0.66 0.52 0.36 1",
    "led": "1 1 1 1",
    "tool_red": "0.75 0.12 0.10 1",
    "tool_yellow": "0.90 0.72 0.10 1",
    "sand": "0.76 0.68 0.50 1",
    "plastic_remote_plain": "0.13 0.13 0.14 1",
    "plastic_mouse_plain": "0.55 0.57 0.60 1",
    "plastic_clock_plain": "0.90 0.89 0.85 1",
    "navy": "0.13 0.18 0.32 1",
    "navy_plain": "0.13 0.18 0.32 1",
    "tool_steel": "0.72 0.74 0.76 1",
    "tool_handle": "0.93 0.42 0.08 1",
    "tool_rib": "0.15 0.15 0.16 1",
    "label_tool": "0.95 0.85 0.15 1",
}


def _assets_xml(decor) -> str:
    a = []
    for name, (file, rep, uni, spec, shin, refl) in TEXTURED.items():
        a.append(f'<texture name="tex_{name}" type="2d" file="tex/{file}"/>')
        a.append(f'<material name="{name}" texture="tex_{name}" texrepeat="{rep}" texuniform="{str(uni).lower()}" '
                 f'specular="{spec}" shininess="{shin}" reflectance="{refl}"/>')
    for name, rgba in PLAIN.items():
        extra = ' emission="1"' if name == "led" else ' specular="0.5" shininess="0.5"'
        a.append(f'<material name="{name}" rgba="{rgba}"{extra}/>')
    for key, (mesh, tex) in decor.items():
        a.append(f'<mesh name="m_{key}" file="{mesh}"/>')
        a.append(f'<texture name="t_{key}" type="2d" file="{tex}"/>')
        a.append(f'<material name="d_{key}" texture="t_{key}" specular="0.3" shininess="0.3"/>')
    a.append('<texture name="sky" type="skybox" builtin="flat" rgb1="0.2 0.2 0.2" width="32" height="32"/>')
    return "\n".join(a)


def _room_xml() -> str:
    z0 = FLOOR_Z
    g = [f'<geom name="floor" type="plane" pos="0 0 {z0}" size="4 4 0.05" material="floor_epoxy"/>',
         # back wall, side walls, ceiling
         _box((0.95, -3.0, z0), (1.0, 3.0, 2.0), "wall_panel", name="wall_back"),
         _box((-3.0, -2.4, z0), (1.0, -2.35, 2.0), "wall_panel", name="wall_right"),
         _box((-3.0, 2.35, z0), (1.0, 2.4, 2.0), "wall_panel", name="wall_left"),
         _box((-3.0, -3.0, 2.0), (1.0, 3.0, 2.05), "ceiling", name="ceiling"),
         # wainscot / kick plate along the back wall
         _box((0.93, -3.0, z0), (0.95, 3.0, z0 + 0.15), "steel_grey"),
         # hazard tape around the robot cell on the floor
         _box((-0.75, -1.0, z0), (-0.70, 1.0, z0 + 0.001), "hazard", 'contype="0" conaffinity="0"'),
         _box((-0.75, -1.0, z0), (0.93, -0.95, z0 + 0.001), "hazard", 'contype="0" conaffinity="0"'),
         _box((-0.75, 0.95, z0), (0.93, 1.0, z0 + 0.001), "hazard", 'contype="0" conaffinity="0"'),
         # posters on the back wall
         _box((0.948, -0.30, 1.00), (0.95, 0.30, 1.45), "poster_zone", 'contype="0" conaffinity="0"'),
         _box((0.948, -1.05, 0.80), (0.95, -0.72, 1.24), "poster_fire", 'contype="0" conaffinity="0"'),
         _box((0.948, 0.72, 0.80), (0.95, 1.05, 1.24), "poster_rules", 'contype="0" conaffinity="0"'),
         ]
    # ceiling LED panels
    for x in (-1.2, 0.2):
        for y in (-1.2, 0.0, 1.2):
            g.append(_box((x - 0.3, y - 0.3, 1.985), (x + 0.3, y + 0.3, 2.0), "led", 'contype="0" conaffinity="0"'))
    return "\n".join(g)


def _bench_xml() -> str:
    x0, x1, y0, y1 = -0.13, 0.62, -0.75, 0.75
    g = [
        # steel top + ESD mat (mat surface is z = 0)
        _box((x0, y0, -0.032), (x1, y1, -0.004), "steel_brushed", name="bench_top"),
        _box((x0 + 0.02, -0.58, -0.004), (x1 - 0.06, 0.58, 0.0), "esd_mat", name="esd_mat"),
        # front/back edge trims
        _box((x0 - 0.004, y0, -0.07), (x0, y1, -0.004), "steel_blue"),
        _box((x1, y0, -0.07), (x1 + 0.004, y1, -0.004), "steel_blue"),
        # lower shelf
        _box((x0 + 0.03, y0 + 0.03, -0.66), (x1 - 0.03, y1 - 0.03, -0.64), "steel_grey"),
        # pegboard upright, top shelf, task light
        _box((0.60, y0, 0.0), (0.612, y1, 0.78), "pegboard", name="pegboard"),
        _box((0.48, y0, 0.78), (0.62, y1, 0.795), "steel_blue"),
        _box((0.50, -0.55, 0.770), (0.53, 0.55, 0.780), "led", 'contype="0" conaffinity="0"'),
        # grounding cable snap on the mat (ESD)
        f'<geom type="cylinder" pos="{_f(0.50, 0.54, 0.001)}" size="0.006 0.002" material="metal_contact" contype="0" conaffinity="0"/>',
    ]
    for x in (x0 + 0.02, x1 - 0.02):
        for y in (y0 + 0.02, y1 - 0.02):
            g.append(_box((x - 0.02, y - 0.02, FLOOR_Z), (x + 0.02, y + 0.02, -0.032), "steel_blue"))
    # uprights for the pegboard
    for y in (y0 + 0.01, y1 - 0.01):
        g.append(_box((0.61, y - 0.01, 0.0), (0.63, y + 0.01, 0.80), "steel_blue"))
    return f'<body name="bench">{"".join(g)}</body>'


def _jig_xml() -> str:
    """Disassembly jig: grey tray with an aluminium L-fence on the +x and -y sides."""
    cx, cy = JIG_CX, JIG_CY
    hx, hy = JIG_HX, JIG_HY
    tz = 0.006
    fr = 'friction="0.35 0.005 0.0001"'      # PP tray / aluminium vs ABS housing
    g = [_box((cx - hx, cy - hy, 0.0), (cx + hx, cy + hy, tz), "plastic_grey_tray", fr, name="jig_plate"),
         _box((cx + hx - 0.008, cy - hy, tz), (cx + hx, cy + hy, tz + 0.012), "aluminum", fr, name="jig_fence_x"),
         _box((cx - hx, cy - hy, tz), (cx + hx, cy - hy + 0.008, tz + 0.012), "aluminum", fr, name="jig_fence_y"),
         # label on the tray front edge
         _box((cx - hx - 0.0006, cy - 0.05, 0.0005), (cx - hx - 0.0002, cy + 0.05, tz - 0.0005), "label_input",
              'contype="0" conaffinity="0" group="1"'),
         f'<site name="jig_corner" pos="{_f(cx + hx - 0.008, cy - hy + 0.008, tz)}" size="0.003" group="4"/>']
    return f'<body name="jig">{"".join(g)}</body>'


def _decor_xml() -> str:
    g = []
    nc = 'contype="0" conaffinity="0"'
    # tools on the bench, right side (outside reach)
    g.append(f'<geom type="mesh" mesh="m_screwdriver" material="d_screwdriver" pos="0.30 -0.52 0" euler="0 0 0.4" {nc}/>')
    g.append(f'<geom type="mesh" mesh="m_scissors" material="d_scissors" pos="0.46 -0.45 0" euler="0 0 2.2" {nc}/>')
    g.append(f'<geom type="mesh" mesh="m_marker" material="d_marker" pos="0.18 -0.55 0" euler="0 0 1.2" {nc}/>')
    g.append(f'<geom type="mesh" mesh="m_gaffer" material="d_gaffer" pos="0.48 -0.62 0" {nc}/>')
    g.append(f'<geom type="mesh" mesh="m_vinyl" material="d_vinyl" pos="0.48 0.62 0.0" {nc}/>')
    g.append(f'<geom type="mesh" mesh="m_clamp" material="d_clamp" pos="0.02 -0.62 0" euler="0 0 0.3" {nc}/>')
    # tools hanging on the pegboard
    for i, y in enumerate((-0.35, -0.30, -0.25)):
        g.append(f'<geom type="mesh" mesh="m_screwdriver" material="d_screwdriver" pos="0.58 {y} 0.40" euler="0 1.5708 {1.5708}" {nc}/>')
    for y, mat in ((0.20, "tool_red"), (0.30, "tool_yellow")):   # pliers / cutters (stylised)
        g.append(f'<geom type="capsule" fromto="0.59 {y - 0.012} 0.30 0.59 {y - 0.004} 0.47" size="0.006" material="{mat}" {nc}/>')
        g.append(f'<geom type="capsule" fromto="0.59 {y + 0.012} 0.30 0.59 {y + 0.004} 0.47" size="0.006" material="{mat}" {nc}/>')
        g.append(f'<geom type="box" pos="0.59 {y} 0.50" size="0.004 0.009 0.035" material="steel_grey" {nc}/>')
    g.append(f'<geom type="mesh" mesh="m_gaffer" material="d_gaffer" pos="0.59 0.45 0.52" euler="0 1.5708 0" {nc}/>')
    # work-zone sign mounted on the pegboard (faces the robot / camera)
    g.append(_box((0.5975, -0.17, 0.50), (0.5995, 0.15, 0.74), "poster_zone", nc))
    # queue crate with waiting appliances (back-left of the bench)
    g.append(_open_box("queue_crate", (0.42, 0.50, 0.0), (0.26, 0.30, 0.10), 0.006, "plastic_blue_crate"))
    g.append(dv.decor_remote("q_r1", (0.40, 0.44, 0.02), (0.1, 0, 0.3)))
    g.append(dv.decor_remote("q_r2", (0.45, 0.55, 0.035), (-0.2, 0.15, -0.5), top_mat="remote_top2", body_mat="plastic_clock"))
    g.append(dv.decor_mouse("q_m1", (0.36, 0.58, 0.03), (0.2, 0, 1.0)))
    g.append(dv.decor_phone("q_p1", (0.49, 0.43, 0.03), (0.0, 0.25, 0.5)))
    g.append(dv.decor_clock("q_c1", (0.46, 0.60, 0.07), (0.6, 0, 0.2)))
    # floor: ton bag of incoming e-waste on a pallet, isolation sand bucket
    z = FLOOR_Z
    g.append(_box((-0.70, -1.75, z), (0.30, -0.95 - 0.10, z + 0.12), "wood"))
    g.append(_box((-0.62, -1.68, z + 0.12), (0.22, -1.12, z + 0.95), "tonbag"))
    for i, (x, y, yaw) in enumerate([(-0.4, -1.4, 0.3), (-0.1, -1.3, 1.2), (0.05, -1.5, 2.2), (-0.3, -1.55, 0.9)]):
        g.append(dv.decor_remote(f"tb_r{i}", (x, y, z + 0.965), (0.2, -0.1, yaw), top_mat="remote_top" if i % 2 else "remote_top2"))
    g.append(dv.decor_keyboard("tb_k1", (-0.2, -1.42, z + 0.985), (0.15, 0.1, 0.4)))
    g.append(dv.decor_mouse("tb_m1", (0.1, -1.25, z + 0.99), (0.3, 0.2, 0.2)))
    g.append(dv.decor_phone("tb_p1", (-0.5, -1.25, z + 0.975), (0.1, 0.3, 0.7)))
    g.append(f'<geom type="cylinder" pos="-0.40 0.95 {z + 0.20}" size="0.15 0.20" material="steel_grey" {nc}/>')
    g.append(f'<geom type="cylinder" pos="-0.40 0.95 {z + 0.39}" size="0.14 0.012" material="sand" {nc}/>')
    # second (empty) workstation in the background for context
    g.append(_box((-1.9, 1.2, -0.032), (-1.15, 2.3, -0.004), "steel_brushed"))
    g.append(_box((-1.88, 1.25, -0.004), (-1.17, 2.25, 0.0), "esd_mat"))
    for x in (-1.88, -1.17):
        for y in (1.22, 2.28):
            g.append(_box((x - 0.02, y - 0.02, FLOOR_Z), (x + 0.02, y + 0.02, -0.032), "steel_blue"))
    # shelving rack along the right wall with boxed e-waste
    for x in (-2.2, -1.0):
        g.append(_box((x - 0.02, -2.32, FLOOR_Z), (x + 0.02, -2.28, 1.2), "steel_blue"))
        g.append(_box((x - 0.02, -1.82, FLOOR_Z), (x + 0.02, -1.78, 1.2), "steel_blue"))
    for zs in (-0.6, -0.1, 0.4, 0.9):
        g.append(_box((-2.22, -2.32, zs), (-0.98, -1.78, zs + 0.02), "steel_grey"))
        for k, x in enumerate((-2.0, -1.6, -1.25)):
            h = 0.18 + 0.08 * ((k + int(zs * 10)) % 3)
            g.append(_box((x - 0.15, -2.25, zs + 0.02), (x + 0.15, -1.85, zs + 0.02 + h), "cardboard"))
    return f'<body name="decor">{"".join(g)}</body>'


def _second_arm_xml(prefix="l_", pos=LEFT_BASE, yaw=LEFT_YAW):
    """Prefixed copy of the SO-101 kinematic tree and actuators (meshes, materials and
    default classes are shared with the first arm included from so101.xml)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring((MJCF_DIR / "so101.xml").read_text(encoding="utf-8"))
    base = root.find("worldbody/body")
    for el in base.iter():
        if "name" in el.attrib and el.tag in ("body", "joint", "geom", "site", "camera"):
            el.attrib["name"] = prefix + el.attrib["name"]
    acts = root.find("actuator")
    for a in acts:
        a.attrib["name"] = prefix + a.attrib["name"]
        a.attrib["joint"] = prefix + a.attrib["joint"]
    q = (np.cos(yaw / 2), 0, 0, np.sin(yaw / 2))
    body = (f'<body name="{prefix}mount" pos="{_f(*pos)}" quat="{_f(*q)}">' + ET.tostring(base, encoding="unicode")
            + "</body>")
    return body, "".join(ET.tostring(a, encoding="unicode") for a in acts)


def _tool_xml():
    """Thin steel pry tool (spudger / thin-blade battery opener) with a moulded handle, in its holder.

    Tool frame: origin at the tip, +z toward the handle, +x = direction the hooked foot points.
      blade  : 12.6 mm wide (y) x 1.2 mm thick (x) spring steel, z in [0, 0.0245]
      foot   : 5 mm hook at the tip, bent toward +x (and 10 deg up), 1.0 mm thick (gets under a cell's + end)
      shank  : z in [0.0245, 0.033]
      handle : 11 (x) x 18 (y) mm moulded grip, z in [0.033, 0.088]; its lower face rests on the holder
    """
    tl = TOOL_LEN["tip_to_collar"]
    hl = TOOL_LEN["handle"]
    cx, cy = TOOL_RACK["center"]
    z = TOOL_RACK["plate_z"] + 0.002 - tl          # tip height when the handle rests on the plate
    steel = 'material="tool_steel" friction="0.25 0.005 0.0001" solref="0.005 1"'
    u = np.array([np.cos(TOOL_FOOT_ANGLE), 0.0, np.sin(TOOL_FOOT_ANGLE)])
    foot_c = np.array([-0.0006, 0.0, 0.0005]) + 0.0028 * u
    grip = 'material="tool_handle" friction="1.0 0.005 0.0001"'
    g = [
        f'<geom name="pry_blade" type="box" pos="0 0 0.0125" size="0.0006 0.0063 0.0120" {steel} mass="0.004"/>',
        # hooked foot, bent up by TOOL_FOOT_ANGLE so that it is level while the tool leans back by that angle
        f'<geom name="pry_foot" type="box" pos="{_f(*foot_c)}" euler="0 {-TOOL_FOOT_ANGLE:.4f} 0" '
        f'size="0.0028 0.0063 0.0005" {steel} mass="0.0005"/>',
        f'<geom name="pry_shank" type="box" pos="0 0 {0.0245 + (tl - 0.0245) / 2:.4f}" size="0.0012 0.0040 {(tl - 0.0245) / 2:.4f}" '
        f'{steel} mass="0.002"/>',
        f'<geom name="pry_handle" type="box" pos="0 0 {tl + hl / 2:.4f}" size="0.0055 0.009 {hl / 2:.4f}" {grip} mass="0.014"/>',
        # visual details: grip ribs and an end cap
        *[f'<geom type="box" pos="{_f(0, 0, tl + 0.016 + 0.008 * k)}" size="0.0058 0.0093 0.0012" material="tool_rib" '
          f'contype="0" conaffinity="0" group="1"/>' for k in range(4)],
        f'<geom type="box" pos="0 0 {tl + hl - 0.002:.4f}" size="0.0058 0.0093 0.002" material="tool_rib" contype="0" '
        f'conaffinity="0" group="1"/>',
        f'<site name="pry_tip" pos="0.0006 0 0.0005" size="0.001" group="4"/>',
    ]
    # tool hangs with its foot pointing to world -x (along the open side of the holder slot)
    q = (0.0, 0.0, 0.0, 1.0)
    return (f'<body name="pry_tool" pos="{_f(cx, cy, z)}" quat="{_f(*q)}"><freejoint name="pry_tool_free"/>'
            + "".join(g) + "</body>")


def _rack_xml():
    """Bench-top fork tool holder: aluminium plate with a slot open toward -x, on two side posts."""
    cx, cy = TOOL_RACK["center"]
    pz = TOOL_RACK["plate_z"]
    hy = 0.0076                                 # slot half width: the 12.6 mm blade passes, the 18 mm handle rests
    xb = cx + 0.0030                            # closed end of the slot (blade face + 2.4 mm)
    t = 0.003
    al = 'friction="0.4 0.005 0.0001"'
    g = [_box((xb, cy - 0.025, pz - t), (cx + 0.03, cy + 0.025, pz), "aluminum", al),                 # back
         _box((cx - 0.03, cy - 0.025, pz - t), (xb, cy - hy, pz), "aluminum", al),                    # fork tines
         _box((cx - 0.03, cy + hy, pz - t), (xb, cy + 0.025, pz), "aluminum", al)]
    for sy in (-1, 1):
        g.append(_box((cx - 0.03, cy + sy * 0.025 - 0.003, 0.004), (cx + 0.03, cy + sy * 0.025 + 0.003, pz - t),
                      "steel_blue", al))
    g.append(_box((cx - 0.035, cy - 0.032, 0.0), (cx + 0.035, cy + 0.032, 0.004), "steel_blue", al))
    g.append(_box((cx + 0.0302, cy - 0.02, pz - 0.0025), (cx + 0.0306, cy + 0.02, pz - 0.0005), "label_tool",
                  'contype="0" conaffinity="0" group="1"'))
    return '<body name="tool_rack">' + "".join(g) + "</body>"


def _lights_xml() -> str:
    return "\n".join([
        '<light name="key" pos="0.1 -0.9 1.9" dir="0.1 0.5 -0.86" directional="false" cutoff="40" exponent="2" '
        'diffuse="0.55 0.55 0.52" specular="0.2 0.2 0.2" castshadow="true"/>',
        '<light name="task" pos="0.515 0 0.765" dir="-0.6 0 -0.8" directional="false" cutoff="60" exponent="1" '
        'diffuse="0.35 0.35 0.33" specular="0.1 0.1 0.1" castshadow="true"/>',
        '<light name="ceil1" pos="-1.2 0 1.95" dir="0 0 -1" directional="false" cutoff="80" diffuse="0.25 0.25 0.25" castshadow="false"/>',
        '<light name="ceil2" pos="0.2 1.2 1.95" dir="0 0 -1" directional="false" cutoff="80" diffuse="0.2 0.2 0.2" castshadow="false"/>',
        '<light name="ceil3" pos="0.2 -1.2 1.95" dir="0 0 -1" directional="false" cutoff="80" diffuse="0.2 0.2 0.2" castshadow="false"/>',
    ])


def _cameras_xml() -> str:
    return "\n".join([
        _cam("overview", (-0.66, -0.84, 0.72), (0.30, 0.04, 0.10), 52),
        _cam("hero", (-0.30, -0.52, 0.42), (0.22, 0.02, 0.03), 48),
        _cam("operator", (-0.85, 0.05, 0.78), (0.28, 0.0, 0.05), 45),
        _cam("wide", (-1.9, -1.6, 1.35), (0.2, 0.0, -0.1), 55),
        _cam("closeup", (0.08, -0.26, 0.22), (0.27, 0.0, 0.012), 40),
        _cam("top", (0.17, 0.0, 0.95), (0.17, 0.0001, 0.0), 45),
        _cam("side", (0.24, -0.20, 0.16), (0.21, 0.02, 0.01), 55),
        _cam("bincam", (0.30, 0.02, 0.36), (0.06, 0.22, 0.10), 60),
        _cam("slotcam", (0.27, -0.12, 0.085), (0.215, -0.02, 0.012), 34),
    ])


def build_scene_xml(device="tv_remote", remote_pose=None, remote_yaw=0.0, cover_on=True, cover_offset=0.0) -> str:
    decor = _copy_decor_meshes()
    spec = dv.DEVICES[device]
    remote_pose = remote_pose or nominal_pose(spec)
    body, eq, extra, _cells, dev_assets, dims = dv.remote_body_xml(spec, remote_pose, remote_yaw, with_cover=cover_on,
                                                                   cover_offset=cover_offset)
    dv.write_remote_shell(dims, MJCF_DIR / "assets" / "devices" / f"{spec.prefix}shell_{spec.name}.obj")
    global LAST_DIMS
    LAST_DIMS = dict(dims, name=spec.name, label=spec.label, nominal=remote_pose)
    arm2, arm2_act = _second_arm_xml()
    bins = (_open_box("battery_bin", BATTERY_BIN["center"], BATTERY_BIN["size"], 0.004, "plastic_red_bin",
                      "label_battery_bin", "both")
            + _open_box("body_bin", BODY_CRATE["center"], BODY_CRATE["size"], 0.005, "plastic_blue_crate", "label_body_bin"))
    return f"""<mujoco model="ewaste_battery_removal">
  <compiler angle="radian" meshdir="assets" texturedir="assets" autolimits="true"/>
  <include file="so101.xml"/>
  <option timestep="0.002" gravity="0 0 -9.81" cone="elliptic" integrator="implicitfast" impratio="10"
          iterations="30" ls_iterations="30" noslip_iterations="3"/>
  <visual>
    <headlight diffuse="0.15 0.15 0.15" ambient="0.25 0.25 0.25" specular="0 0 0"/>
    <quality shadowsize="8192" offsamples="8"/>
    <global offwidth="1920" offheight="1080"/>
    <map znear="0.005" zfar="20"/>
  </visual>
  <asset>
{_assets_xml(decor)}
{dev_assets}
  </asset>
  <worldbody>
{_lights_xml()}
{_room_xml()}
{_bench_xml()}
{_jig_xml()}
{bins}
{_decor_xml()}
{body}
{"".join(extra)}
{arm2}
{_rack_xml()}
{_tool_xml()}
{_cameras_xml()}
  </worldbody>
  <actuator>{arm2_act}</actuator>
  <equality>{eq}</equality>
</mujoco>
"""


def write_scene(path: Path | None = None, **kw) -> Path:
    path = path or (MJCF_DIR / "battery_scene.xml")
    path.write_text(build_scene_xml(**kw), encoding="utf-8")
    return path


def _vfs_assets() -> dict[str, bytes]:
    """Every file under mjcf/ keyed by its relative path.

    The model is compiled from memory (MuJoCo VFS) instead of from a file path,
    because MuJoCo cannot open non-ASCII Windows paths (e.g. a Korean folder name).
    """
    out = {}
    for f in MJCF_DIR.rglob("*"):
        if f.is_file() and f.suffix.lower() in {".xml", ".stl", ".obj", ".png"}:
            out[f.relative_to(MJCF_DIR).as_posix()] = f.read_bytes()
    return out


LAST_DIMS: dict = {}


def load_model(**kw):
    import mujoco
    xml = build_scene_xml(**kw)
    (MJCF_DIR / "battery_scene.xml").write_text(xml, encoding="utf-8")  # kept for inspection
    return mujoco.MjModel.from_xml_string(xml, assets=_vfs_assets())
