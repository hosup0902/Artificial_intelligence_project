"""Run the bimanual policy up to the pry stage and save a snapshot; or load it.
   python snap.py save <device> <seed>"""
import sys, pickle; sys.path.insert(0, '.')
import numpy as np, mujoco
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy
SP = str(__import__("pathlib").Path(__file__).resolve().parent / "_out")
SPEC = mujoco.mjtState.mjSTATE_INTEGRATION
def save(dev, seed, stage="prepry"):
    from battery_sim.policy import R_LEAN
    env = BatteryRemovalEnv(device=dev); env.reset(seed)
    pol = SkillPolicy(env, verbose=False)
    ok, tok = pol.run_par(pol._main_prep(), pol._tool_prep())
    pol.run_par(pol.tool_standby()); pol.run_par(pol.grasp_device(lift=False, gx=pol.dm["hold_x"], lean=R_LEAN))
    if stage == "preflip":
        for k in range(3):
            if pol.run_par(pol.pry_cells(attempt=k)):
                break
        def r_side():
            yield from pol.release_device()
            ok = yield from pol.grasp_device()
            return ok
        pol.run_par(pol.tool_retreat())
        pol.run_par(r_side())
    st = np.zeros(mujoco.mj_stateSize(env.m, SPEC)); mujoco.mj_getState(env.m, env.d, st, SPEC)
    blob = dict(state=st, R=(pol.R.qcmd, pol.R.grip_cmd), L=(pol.L.qcmd, pol.L.grip_cmd), tool_rel=pol.tool_rel,
                log=env.log, cover_seat=pol.cover_seat, extra=dict(_holding=pol._holding, _grasp_axes=pol._grasp_axes))
    if stage == "preflip":
        blob["extra"]["_grasp_rel"] = pol._grasp_rel
    pickle.dump(blob, open(f"{SP}/snap_{dev}_{seed}{'' if stage == 'prepry' else '_' + stage}.pkl", "wb"))
    print("saved", ok, tok, env.d.time)
def load(dev, seed, verbose=True, stage="prepry"):
    env = BatteryRemovalEnv(device=dev); env.reset(seed)
    pol = SkillPolicy(env, verbose=verbose)
    b = pickle.load(open(f"{SP}/snap_{dev}_{seed}{'' if stage == 'prepry' else '_' + stage}.pkl", "rb"))
    mujoco.mj_setState(env.m, env.d, b["state"], SPEC); mujoco.mj_forward(env.m, env.d)
    pol.R.qcmd, pol.R.grip_cmd = b["R"]; pol.L.qcmd, pol.L.grip_cmd = b["L"]
    pol.tool_rel = b["tool_rel"]; env.log = b["log"]; pol.cover_seat = b["cover_seat"]
    for k, v in b.get("extra", {}).items(): setattr(pol, k, v)
    env.set_ctrl(pol.R.qcmd, pol.R.grip_cmd, "R"); env.set_ctrl(pol.L.qcmd, pol.L.grip_cmd, "L")
    return env, pol
if __name__ == "__main__":
    save(sys.argv[2], int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else "prepry")
