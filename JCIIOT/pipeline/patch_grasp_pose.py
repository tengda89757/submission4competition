"""
patch_grasp_pose.py — Diagnose the BC grasp base pose from live scene geometry.

Why: task_config's grasp_poses were calibrated for the L1 layout only. In scenes
3/7 the same input_N is at a different world position and objects are rotated, so
the baseline pose is metres off (verified: L2 grasp failed at nav pose 13.0,3.95
while the tote sits at 11.87,4.63). The runtime pick-up skill performs this
calculation directly; this diagnostic never writes locked task_config.json.

Rule (reverse-engineered from the trained L1 geometry and verified 10/10):
    base_xy = object_center_xy + 0.941 * normalize(site_center_xy - object_center_xy)
    yaw     = atan2(-dir.y, -dir.x)          # face the object
This generalizes to rotated objects because the grasp sites rotate with them.

Usage:
  .venv\\Scripts\\python pipeline\\patch_grasp_pose.py --level L2
  .venv\\Scripts\\python pipeline\\patch_grasp_pose.py --level L3 --object blue_container_h10_back --source input_3
  .venv\\Scripts\\python pipeline\\patch_grasp_pose.py --level L1 --dry-run     # sanity check vs known-good pose
"""
from __future__ import annotations

import argparse
import json
import math
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

import numpy as np  # noqa: E402
import robosuite as suite  # noqa: E402
from robosuite.environments.factory_sorting.factory_sorting_1_3fo3erfhisem import FactorySorting1_3FO3ERFHISEM  # noqa
from robosuite.environments.factory_sorting.factory_sorting_3_3fo3errph7x9 import FactorySorting3_3FO3ERRPH7X9  # noqa
from robosuite.environments.factory_sorting.factory_sorting_5_3fo3ertpxeut import FactorySorting5_3FO3ERTPXEUT  # noqa
from robosuite.environments.factory_sorting.factory_sorting_7_3fo3erfky9rn import FactorySorting7_3FO3ERFKY9RN  # noqa
from robosuite.environments.factory_sorting.factory_sorting_9_3fo3ert2c5fp import FactorySorting9_3FO3ERT2C5FP  # noqa

TRAINED_BASE_DIST = 0.941   # metres from object centre, from the L1 trained pose

# Poses that MUST match the exact demo-collection pose (runtime pose == demo pose).
# L1 demos (and the official 150 ckpt) were collected at the collector's default
# pose, not the site-computed one — 2 cm off is enough to matter for BC.
KNOWN_DEMO_POSES = {
    "line_5_container_h01_near": ([8.000001, 4.6, 0.0], -3.139453),
}

CFG_PATH = APP_DIR / "knowledge" / "task_config.json"


def compute_pose(env, object_name: str) -> tuple[list[float], float]:
    def site(name):
        return np.array(env.sim.data.site_xpos[env.sim.model.site_name2id(name)])

    r = site(f"{object_name}_right_grasp_site")
    l = site(f"{object_name}_left_grasp_site")
    site_center = (r + l) / 2.0

    body_id = env.obj_body_id[object_name]
    obj = np.array(env.sim.data.body_xpos[body_id])

    # Rotated-approach objects (sites buried in scene AABB proxies): reuse the
    # skills-layer geometry so config yaw matches the runtime approach direction
    # (the backend force-feeds config yaw into the wrapped grasp env).
    try:
        from robot_agent.skills.scripted_grasp import (
            ROTATED_GRASP_OVERRIDES, rotated_grasp_geometry,
        )
        ov = ROTATED_GRASP_OVERRIDES.get(object_name)
    except ImportError:
        ov = None
    if ov is not None:
        base_xy, yaw, _, _ = rotated_grasp_geometry(obj[:2], site_center[:2], ov)
        print(f"rotated approach ({ov['rot_deg']:.0f} deg) for {object_name}")
        return ([round(float(base_xy[0]), 6), round(float(base_xy[1]), 6), 0.0],
                round(float(yaw), 6))

    d = site_center[:2] - obj[:2]
    n = np.linalg.norm(d)
    if n < 1e-6:
        raise RuntimeError(f"grasp sites of {object_name} coincide with object centre")
    d = d / n
    base_xy = obj[:2] + TRAINED_BASE_DIST * d
    yaw = math.atan2(-d[1], -d[0])
    return [round(float(base_xy[0]), 6), round(float(base_xy[1]), 6), 0.0], round(float(yaw), 6)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", required=True, choices=["L1", "L2", "L3", "L4", "L5"])
    ap.add_argument("--object", default="", help="override object (default: task_config object)")
    ap.add_argument("--source", default="", help="override source port key to display")
    ap.add_argument("--shift-x", type=float, default=0.0, help="extra base x shift (clear scene obstacles)")
    ap.add_argument("--shift-y", type=float, default=0.0, help="extra base y shift")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    task = next(t for t in cfg["tasks"] if t["level"] == args.level)
    env_name = task["env_name"]
    source = args.source or task["source"]
    configured_objects = task.get("object", "")
    if isinstance(configured_objects, (list, tuple)):
        configured_objects = next((str(item) for item in configured_objects if item), "")
    object_name = args.object or str(configured_objects)

    print(f"level={args.level} scene={env_name} source={source} object={object_name}")
    if object_name in KNOWN_DEMO_POSES:
        pos, yaw = KNOWN_DEMO_POSES[object_name]
        pos = list(pos)
        print("using KNOWN demo-collection pose (exact match to training data)")
    else:
        env = suite.make(
            env_name, robots="Tiago",
            has_renderer=False, has_offscreen_renderer=True,
            use_camera_obs=False, use_object_obs=True, ignore_done=True, control_freq=20,
        )
        try:
            env.reset()
            pos, yaw = compute_pose(env, object_name)
        finally:
            env.close()
    if args.shift_x or args.shift_y:
        pos = [round(pos[0] + args.shift_x, 6), round(pos[1] + args.shift_y, 6), 0.0]

    old = cfg["grasp_poses"].get(source)
    print(f"computed grasp pose: pos={pos} yaw={yaw}")
    print(f"previous config    : {old}")
    print("(diagnostic only; locked task_config.json unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
