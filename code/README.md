# 폐가전 건전지 분리 (E-waste Battery Removal) — bimanual SO101-Nexus

Two SO-101 arms in a Korean small-appliance dismantling workstation remove the cells from four kinds
of waste remote controls (TV / set-top box (AAA) / air-conditioner / lighting (AAA)):

1. **arm R** (main arm) pushes the remote against the jig fence and slides the latched cover off
   (press-and-slide latch); a cover caught between the fingers is dropped beyond the fence;
2. **arm L** (tool arm) picks a thin pry tool (spudger with a hooked T-shaped tip) out of its fork holder;
3. arm R grasps the remote and holds it on the jig while arm L inserts the tool into the pry notch behind
   the + ends, **pushes both cells into their springs past the retaining lips and levers the + ends up**
   onto the lip tops;
4. arm L backs off; arm R re-grasps, carries the remote over the red 폐건전지 수거함, rolls it upside down and
   shakes it so the freed cells drop out, then puts the empty body into the blue 소형 폐가전 crate;
   meanwhile arm L puts the tool back into its holder.

The compartment is built like a real one (`battery_sim/devices.py`): flat-lying cells, a coil-spring
plunger at the − end (0.6 N preload), rigid retaining lips over the + ends (9.6 mm gap, narrower than any
cell), a pry notch with a recess under the + ends. Turning the remote over or only pushing the cells into
the springs does **not** release them (see the ablations below); they have to be pushed **and** lifted.

## Results

| experiment | command | result |
|---|---|---|
| full bimanual policy, 4 devices × seeds 0-9 | `python run_episode.py --seeds 0-9 --device <dev>` | **40/40** (each device 10/10), peak contact force on the device ≤ 33 N |
| ablation: no tool (just flip + shake) | `python ablation.py --mode no_tool --seeds 0-2` | 0/12, cells in bin 0/24 |
| ablation: push into springs, no lift | `python ablation.py --mode push_only --seeds 0-2` | 0/12, cells in bin 0/24 |

Per-episode results: `renders/eval_bimanual_<device>.json`, `renders/ablation_<mode>.json`.

## Setup (Python 3.12)

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt     # Windows: .venv\Scripts\python.exe
```

* Python 3.12: MuJoCo / so101-nexus wheels target <= 3.13.
* Headless Linux rendering: install OSMesa (`apt-get install libosmesa6`) and run with `MUJOCO_GL=osmesa`
  (only needed for videos/renders; the evaluation itself does not render).
* **MuJoCo cannot open files under non-ASCII Windows paths** (e.g. a Korean folder name). The scene is
  compiled from memory (`mujoco.MjModel.from_xml_string(xml, assets=...)`, `battery_sim/scene.py::load_model`),
  so the project folder may have any name; keep the venv in an ASCII path.
* Decor meshes (screwdriver, scissors, marker, tapes, C-clamp) are YCB / Google Scanned Objects scans
  (CC-BY-4.0) downloaded by so101-nexus on first run and copied into `battery_sim/mjcf/assets/decor/`.

## Run

```bash
python run_episode.py --seeds 0 --device tv_remote             # one verbose episode
python run_episode.py --seeds 0 --device tv_remote --video     # + mp4 in videos/ (needs a GL backend)
python run_episode.py --seeds 0-9 --device ac_remote -q --out results.json   # evaluation sweep
python ablation.py --mode no_tool --seeds 0-2                  # control experiments
python render_scene.py                                          # scene renders (5 cameras)
python render_devices.py                                        # the four devices, closed / opened
```

`--device all` cycles the four devices by seed. Each result line reports `success`, cells in the bin,
body in the crate, the peak contact force and where it occurred, the first failed stage, sim time and
step count, and whether the tool was put back into its holder (`tool_returned`, not part of the success
criterion).

## Layout

| file | content |
|---|---|
| `battery_sim/scene.py` | full MJCF: room, bench, jig, bins, decor, lights, cameras, **second SO-101** (`l_` prefix), pry tool + fork holder |
| `battery_sim/devices.py` | remote controls (latched sliding cover, sprung terminals, retaining lips, pry notch, 2 cells), decor appliances |
| `battery_sim/env.py` | two-arm environment: reset/randomisation, press-and-slide latch, contact-force monitor, finger pads |
| `battery_sim/ik.py` | damped-least-squares IK for either arm (tool point + any tool-fixed directions; SO-101 is 5-DoF) |
| `battery_sim/policy.py` | bimanual skill state machine; skills are generators so both arms run concurrently (`run_par`) |
| `battery_sim/success.py` | success judgement |
| `run_episode.py`, `ablation.py` | evaluation and control experiments |
| `dev_tools/` | debugging harness (snapshots before the pry / flip, step-by-step traces, retention test) |
| `legacy_midterm/` | mid-term single-arm experiment scripts (pop-up design, no longer runnable) |
| `battery_sim/mjcf/` | SO-101 model (MuJoCo Menagerie, Apache-2.0, vendored by so101-nexus) + assets |

## Success criterion

All cells inside the battery-bin region **and** the device body inside the body-crate region **and** no
cell in the body crate **and** peak contact force between the robots (incl. the hand-held tool) and the
device ≤ 40 N.
