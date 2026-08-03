"""probe_object_pos.py — Compare an object's position between the EMPTY probe env
(include_material_objects=False, used by patch_grasp_pose) and the FULL runtime env
(include_material_objects=True, used by the backend's grasp env).

Usage: .venv\\Scripts\\python pipeline\\probe_object_pos.py FactorySorting5_3FO3ERTPXEUT blue_tote_b01_near_right
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
_INNER = APP_DIR / "robosuite" / "robosuite" / "__init__.py"
import robosuite as _rs
_rs.__file__ = str(_INNER)
_rs.__path__ = [str(_INNER.parent)]
exec(compile(_INNER.read_text(encoding="utf-8"), str(_INNER), "exec"), _rs.__dict__)

import numpy as np
import robosuite as suite
from robosuite.environments.factory_sorting.factory_sorting_5_3fo3ertpxeut import FactorySorting5_3FO3ERTPXEUT  # noqa
from robosuite.environments.factory_sorting.factory_sorting_7_3fo3erfky9rn import FactorySorting7_3FO3ERFKY9RN  # noqa

env_name = sys.argv[1] if len(sys.argv) > 1 else "FactorySorting5_3FO3ERTPXEUT"
obj = sys.argv[2] if len(sys.argv) > 2 else "blue_tote_b01_near_right"

for include in (False, True):
    env = suite.make(env_name, robots="Tiago", has_renderer=False, has_offscreen_renderer=True,
                     use_camera_obs=False, use_object_obs=True, ignore_done=True, control_freq=20,
                     include_material_objects=include)
    env.reset()
    tag = "FULL " if include else "EMPTY"
    try:
        bid = env.sim.model.body_name2id(f"{obj}_main")
        pos = np.round(env.sim.data.body_xpos[bid], 3)
    except Exception:
        try:
            bid = env.sim.model.body_name2id(obj)
            pos = np.round(env.sim.data.body_xpos[bid], 3)
        except Exception:
            pos = "BODY NOT FOUND"
    sites = {}
    for arm in ("right", "left"):
        sn = f"{obj}_{arm}_grasp_site"
        try:
            sites[arm] = np.round(env.sim.data.site_xpos[env.sim.model.site_name2id(sn)], 3).tolist()
        except Exception:
            sites[arm] = "NONE"
    print(f"[{tag}] {obj}: body={pos} sites={sites}")
    # any other bodies with similar name?
    similar = [n for n in env.sim.model.body_names if obj.split('_b01')[0] in n and "site" not in n]
    print(f"[{tag}] similar bodies: {similar[:8]}")
    env.close()
