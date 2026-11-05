"""Run flip_over_bin + drop_in_crate from a pre-flip snapshot: python dev_tools/run_flip.py <dev> <seed>"""
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
from snap import load
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=True, stage="preflip")
ok = pol.run_par(pol.flip_over_bin())
if ok or env.success().cells_in_battery_bin.count(True):
    pol.run_par(pol.drop_in_crate())
print(env.success())
