import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
import numpy as np
from snap import load
from view import views
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False, stage="preflip")
pd, Rd = pol.device()
print("device up", np.round(Rd[:, 2], 3), "x-axis", np.round(Rd[:, 0], 3), "grip", round(env.grip_force("R"), 1))
c = pd + Rd @ [0, 0, 0.01]
views(env, str(HERE / "_out" / "lift.png"), [(c, 0.3, 270, -10), (c, 0.3, 180, -10), (c, 0.3, 225, -40)])
