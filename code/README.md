# 폐가전 건전지 분리 (E-waste Battery Removal) — SO101-Nexus

SO-101 arm in a Korean small-appliance dismantling workstation removes the AA cells
from a waste TV remote: slide the latched cover off, push the cells into their spring
terminals so their + ends come free of the retaining lip (finger slot behind the + ends),
flip the remote over the red 폐건전지 수거함 so the cells drop out, and put the empty body
into the blue 소형 폐가전 crate.

Cell retention (devices.py): 400 N/m spring terminals (1.5 mm preload, 6.8 mm stroke), a
4.5 mm polished retaining lip over each + end, a low centre divider, and a 0.8 mm floor rib
on which a freed + end tips up (pop-up) so it catches on the lip's outer edge.

Results (seeds 0-9): full policy 10/10; same policy without `unlatch_cells`
(`python ablation_no_unlatch.py 0,1,2,3,4`) 0/5.

## Setup (Windows, Python 3.12)

```bash
uv venv %USERPROFILE%\.venvs\aiproj2 --python 3.12
uv pip install --python %USERPROFILE%\.venvs\aiproj2\Scripts\python.exe -r requirements.txt
```

* Python 3.12 is used because MuJoCo / so101-nexus wheels target <=3.13.
* **MuJoCo cannot open files under non-ASCII Windows paths** (e.g. a Korean folder name).
  The venv therefore lives in an ASCII path, and the scene is compiled from memory
  (`mujoco.MjModel.from_xml_string(xml, assets=...)`, see `battery_sim/scene.py::load_model`),
  so the project folder itself may have any name.
* Decor meshes (screwdriver, scissors, marker, tapes, C-clamp) are YCB / Google Scanned
  Objects scans (CC-BY-4.0) downloaded by so101-nexus on first run and copied into
  `battery_sim/mjcf/assets/decor/`.

## Run

```bash
python battery_sim/textures.py   # regenerate procedural textures (fixed seed)
python render_scene.py           # build scene, 2 s physics settle + drift check, render 5 cameras
python render_states.py          # staged key states 1_start / 2_press / 3_open / 4_goal + success check
```

Run the policy:

```bash
python run_episode.py --seeds 0 --video        # one rollout + mp4 in videos/
python run_episode.py --seeds 0-29 -q --out results.json   # evaluation sweep
python debug_frames.py 0 bincam 29 45          # contact sheet of a time window (debugging)
```

Renders go to `renders/`. The `render_states.py` images are **staged** (objects/arm placed by
script, physics settled), not policy rollouts.

## Layout

| file | content |
|---|---|
| `battery_sim/scene.py` | full MJCF: room, bench, jig, bins, decor, lights, cameras; `load_model()` |
| `battery_sim/devices.py` | TV remote (latched sliding cover, sprung terminals, 2×AA), decor appliances |
| `battery_sim/textures.py` | procedural textures + Korean signage |
| `battery_sim/ik.py` | damped-least-squares IK (tool point + any tool-fixed direction; SO-101 is 5-DoF) |
| `battery_sim/env.py` | episode reset/randomisation, latch release by push force, contact-force monitor |
| `battery_sim/policy.py` | skill state machine: push_to_fence → slide_cover → reseat → unlatch_cells (push into springs) → grasp (force-limited) → flip_over_bin → drop_in_crate |
| `ablation_no_unlatch.py`, `latch_test.py` | control experiments for the latch |
| `battery_sim/success.py` | success judgement |
| `battery_sim/mjcf/` | SO-101 model (MuJoCo Menagerie, Apache-2.0, vendored by so101-nexus) + assets |

## Success criterion

All AA cells inside the battery-bin region **and** the device body inside the body-crate
region **and** no cell in the body crate **and** peak contact force on the device ≤ 40 N.
