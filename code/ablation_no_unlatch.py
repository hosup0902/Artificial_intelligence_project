"""Control experiment: same policy and seeds, but the unlatch_cells skill is skipped.
If the spring latch works, the flip-and-shake alone must NOT release the cells."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sim.env import BatteryRemovalEnv
from battery_sim.policy import SkillPolicy

seeds = [int(s) for s in (sys.argv[1] if len(sys.argv) > 1 else "0").split(",")]
env = BatteryRemovalEnv()
for sd in seeds:
    env.reset(sd)
    pol = SkillPolicy(env, verbose=False)
    pol.unlatch_cells = lambda attempt=0: pol.stage("unlatch_cells(skipped)", True)
    rep = pol.run()
    print(json.dumps(dict(seed=sd, success=bool(rep.success), cells_in_bin=[bool(c) for c in rep.cells_in_battery_bin],
                          stages=[(n, ok) for n, _, ok in env.log.stages])))
