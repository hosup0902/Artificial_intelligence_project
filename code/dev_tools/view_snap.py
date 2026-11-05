import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "."); sys.path.insert(0, str(HERE))
from snap import load
from view import views
import numpy as np
env, pol = load(sys.argv[1], int(sys.argv[2]), verbose=False)
d = env.d
print("cover", np.round(d.body("remote_cover").xpos, 3), "device", np.round(d.body("remote_body").xpos, 3))
pl = d.site("remote_plus").xpos
views(env, str(HERE / "_out" / "snap_view.png"), ["hero", (pl, 0.25, 150, -35), (pl, 0.25, 240, -30)])
