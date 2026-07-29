"""probe_geometry.py — Dump scene AABB proxies & free floor around a station.
Usage: .venv\\Scripts\\python pipeline\\probe_geometry.py --level L2 [--xmin 10 --xmax 14]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
_INNER = APP_DIR / "robosuite" / "robosuite" / "__init__.py"
import robosuite as _rs
_rs.__file__ = str(_INNER); _rs.__path__ = [str(_INNER.parent)]
exec(compile(_INNER.read_text(encoding="utf-8"), str(_INNER), "exec"), _rs.__dict__)
import numpy as np
import robosuite as suite
from robosuite.environments.factory_sorting.factory_sorting_3_3fo3errph7x9 import FactorySorting3_3FO3ERRPH7X9  # noqa
from robosuite.environments.factory_sorting.factory_sorting_5_3fo3ertpxeut import FactorySorting5_3FO3ERTPXEUT  # noqa
from robosuite.environments.factory_sorting.factory_sorting_7_3fo3erfky9rn import FactorySorting7_3FO3ERFKY9RN  # noqa
from robosuite.environments.factory_sorting.factory_sorting_9_3fo3ert2c5fp import FactorySorting9_3FO3ERT2C5FP  # noqa

ap = argparse.ArgumentParser()
ap.add_argument("--level", default="L2")
ap.add_argument("--xmin", type=float, default=9.5)
ap.add_argument("--xmax", type=float, default=14.5)
ap.add_argument("--ymin", type=float, default=0.0)
ap.add_argument("--ymax", type=float, default=7.0)
a = ap.parse_args()

cfg = json.loads((APP_DIR / "knowledge" / "task_config.json").read_text(encoding="utf-8"))
task = next(t for t in cfg["tasks"] if t["level"] == a.level)
env = suite.make(task["env_name"], robots="Tiago", has_renderer=False, has_offscreen_renderer=True,
                 use_camera_obs=False, use_object_obs=True, ignore_done=True, control_freq=20)
try:
    env.reset()
    m = env.sim.model
    print(f"scene={task['env_name']}  window x[{a.xmin},{a.xmax}] y[{a.ymin},{a.ymax}]")
    for gid in range(m.ngeom):
        name = m.geom_id2name(gid)
        if not name:
            continue
        pos = env.sim.data.geom_xpos[gid]
        if not (a.xmin <= pos[0] <= a.xmax and a.ymin <= pos[1] <= a.ymax):
            continue
        size = m.geom_size[gid]
        ct, ca = int(m.geom_contype[gid]), int(m.geom_conaffinity[gid])
        grp = int(m.geom_group[gid])
        if "proxy" in name or "line_6" in name or "input_6" in name or ct or ca:
            print(f"  {name[:58]:58s} pos=({pos[0]:6.2f},{pos[1]:6.2f},{pos[2]:5.2f}) "
                  f"size=({size[0]:5.2f},{size[1]:5.2f},{size[2]:5.2f}) contype={ct} conaff={ca} grp={grp}")
finally:
    env.close()
