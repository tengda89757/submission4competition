"""
inspect_scenes.py — Ground-truth scene audit for L2–L5.

Creates each FactorySorting scene headless and dumps every material object, its
position, and its port mapping (material_metadata.port_name). This settles
data-driven questions before running tasks, e.g. which official blue candidate
sits at L3's ``aux_input_1`` placement point.

Usage:  .venv\\Scripts\\python pipeline\\inspect_scenes.py [--scenes 3 5 7 9]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# same namespace monkey-patch as app.py / tests
_INNER = APP_DIR / "robosuite" / "robosuite" / "__init__.py"
import robosuite as _rs  # noqa: E402
_rs.__file__ = str(_INNER)
_rs.__path__ = [str(_INNER.parent)]
exec(compile(_INNER.read_text(encoding="utf-8"), str(_INNER), "exec"), _rs.__dict__)

import numpy as np  # noqa: E402
import robosuite as suite  # noqa: E402
# import to register the numbered envs
from robosuite.environments.factory_sorting.factory_sorting_1_3fo3erfhisem import FactorySorting1_3FO3ERFHISEM  # noqa
from robosuite.environments.factory_sorting.factory_sorting_3_3fo3errph7x9 import FactorySorting3_3FO3ERRPH7X9  # noqa
from robosuite.environments.factory_sorting.factory_sorting_5_3fo3ertpxeut import FactorySorting5_3FO3ERTPXEUT  # noqa
from robosuite.environments.factory_sorting.factory_sorting_7_3fo3erfky9rn import FactorySorting7_3FO3ERFKY9RN  # noqa
from robosuite.environments.factory_sorting.factory_sorting_9_3fo3ert2c5fp import FactorySorting9_3FO3ERT2C5FP  # noqa

SCENES = {
    1: "FactorySorting1_3FO3ERFHISEM",
    3: "FactorySorting3_3FO3ERRPH7X9",
    5: "FactorySorting5_3FO3ERTPXEUT",
    7: "FactorySorting7_3FO3ERFKY9RN",
    9: "FactorySorting9_3FO3ERT2C5FP",
}


def inspect(env_name: str) -> None:
    print(f"\n{'='*70}\nSCENE {env_name}\n{'='*70}")
    env = suite.make(
        env_name,
        robots="Tiago",
        has_renderer=False,
        has_offscreen_renderer=True,
        use_camera_obs=False,
        use_object_obs=True,
        ignore_done=True,
        control_freq=20,
    )
    try:
        env.reset()
        meta = getattr(env, "material_metadata", {}) or {}
        objs = getattr(env, "material_objects", []) or []
        print(f"material_objects ({len(objs)}):")
        for name in objs:
            body_id = env.obj_body_id.get(name) if hasattr(env, "obj_body_id") else None
            pos = np.array(env.sim.data.body_xpos[body_id]) if body_id is not None else None
            info = meta.get(name, {}) if isinstance(meta, dict) else {}
            port = info.get("port_name", "?") if isinstance(info, dict) else "?"
            extra = {k: v for k, v in (info.items() if isinstance(info, dict) else []) if k != "port_name"}
            pos_s = f"({pos[0]:7.3f},{pos[1]:7.3f},{pos[2]:6.3f})" if pos is not None else "(n/a)"
            # grasp-site world positions (decides BC-policy approach feasibility)
            sites = ""
            for arm in ("right", "left"):
                sn = f"{name}_{arm}_grasp_site"
                try:
                    sp = env.sim.data.site_xpos[env.sim.model.site_name2id(sn)]
                    sites += f" {arm}Site=({sp[0]:.3f},{sp[1]:.3f})"
                except Exception:
                    sites += f" {arm}Site=NONE"
            print(f"  {name:42s} port={str(port):10s} pos={pos_s}{sites}")
        # port -> object summary
        print("port -> object:")
        for name, info in (meta.items() if isinstance(meta, dict) else []):
            if isinstance(info, dict) and info.get("port_name"):
                print(f"  {info['port_name']:10s} -> {name}")
    finally:
        env.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=int, nargs="*", default=[3, 5, 7, 9])
    args = ap.parse_args()
    for s in args.scenes:
        inspect(SCENES[s])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
