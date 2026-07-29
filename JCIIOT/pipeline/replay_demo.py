"""replay_demo.py — Open-loop replay of a recorded demo's actions in a fresh env.

Falsification chain for the v2 BC regression:
  - markers hidden (done) -> still fails
  - empty-scene eval (done) -> still fails
  - THIS: replay the exact recorded action sequence. If the replay reproduces the
    grasp, the dataset is sound and the fault is in policy/obs processing; if not,
    the recorded actions don't reproduce (seed/reset nondeterminism, wrapper skew).

Usage:
  .venv\\Scripts\\python pipeline\\replay_demo.py --dataset pipeline\\collected\\merged_grasp_v2.hdf5 --demo demo_0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_INNER = APP_DIR / "robosuite" / "robosuite" / "__init__.py"
import robosuite as _rs  # noqa: E402
_rs.__file__ = str(_INNER)
_rs.__path__ = [str(_INNER.parent)]
exec(compile(_INNER.read_text(encoding="utf-8"), str(_INNER), "exec"), _rs.__dict__)

import h5py  # noqa: E402
import numpy as np  # noqa: E402
import robosuite as suite  # noqa: E402
from robosuite.environments.factory_sorting.factory_sorting_1_3fo3erfhisem import FactorySorting1_3FO3ERFHISEM  # noqa
from robosuite.environments.factory_sorting.factory_sorting_3_3fo3errph7x9 import FactorySorting3_3FO3ERRPH7X9  # noqa
from robosuite.environments.factory_sorting.factory_sorting_5_3fo3ertpxeut import FactorySorting5_3FO3ERTPXEUT  # noqa
from robosuite.environments.factory_sorting.factory_sorting_7_3fo3erfky9rn import FactorySorting7_3FO3ERFKY9RN  # noqa
from robosuite.environments.factory_sorting.factory_sorting_9_3fo3ert2c5fp import FactorySorting9_3FO3ERT2C5FP  # noqa


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--demo", default="demo_0")
    args = ap.parse_args()

    with h5py.File(str(args.dataset), "r") as f:
        g = f["data"][args.demo]
        actions = np.array(g["actions"])
        env_args = json.loads(f["data"].attrs["env_args"])
    env_name = env_args["env_name"]
    kw = dict(env_args["env_kwargs"])
    # robosuite doesn't accept these robomimic-side keys
    for k in ("env_name", "type", "render", "render_offscreen", "use_image_obs", "use_depth_obs"):
        kw.pop(k, None)
    kw["has_renderer"] = False
    kw["has_offscreen_renderer"] = True
    print(f"replaying {args.demo}: {actions.shape[0]} steps in {env_name}")
    print(f"base_pos={kw.get('robot_base_pos')} base_ori={kw.get('robot_base_ori')} seed={kw.get('seed')}")

    env = suite.make(env_name=env_name, **kw)
    env.reset()

    # object of interest: from policy_info if present
    obj = None
    with h5py.File(str(args.dataset), "r") as f:
        pi = f["data"].attrs.get("policy_info")
        if pi:
            try:
                obj = json.loads(pi).get("object_name")
            except Exception:
                pass
    if not obj:
        obj = "line_5_container_h01_near"

    def obj_pos():
        try:
            bid = env.sim.model.body_name2id(f"{obj}_main")
        except Exception:
            bid = env.sim.model.body_name2id(obj)
        return np.array(env.sim.data.body_xpos[bid])

    p0 = obj_pos()
    for i, a in enumerate(actions):
        env.step(np.array(a))
    p1 = obj_pos()
    dz = float(p1[2] - p0[2])
    print(f"object start z={p0[2]:.3f} end z={p1[2]:.3f} dz={dz:+.3f}")
    print(f"REPLAY {'SUCCESS (object lifted)' if dz > 0.05 else 'FAILURE (no lift)'}")
    env.close()
    return 0 if dz > 0.05 else 1


if __name__ == "__main__":
    raise SystemExit(main())
