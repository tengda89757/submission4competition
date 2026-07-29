"""
collect_demos_multi.py — Collect scripted expert grasp demos in ANY FactorySorting
scene (L1–L5), reusing the official collector's functions unmodified.

Why: the official collector hardcodes scene 1, but the BC policy trained only on
L1 demos diverges in other scenes (verified: L2 grasp misses by >1 m). Per the
official PPT, participants may self-train the robomimic checkpoint — so we collect
per-scene demos at the calibrated grasp pose and later merge + retrain a
generalist policy.

Usage:
  .venv\\Scripts\\python pipeline\\collect_demos_multi.py --level L2 --num-rollouts 20
  .venv\\Scripts\\python pipeline\\collect_demos_multi.py --level L5 --object white_tote_b01_left_center --num-rollouts 15
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
import os
import sys
import tempfile
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

import robosuite as suite  # noqa: E402
from robosuite.wrappers import DataCollectionWrapper  # noqa: E402
# register the numbered envs
from robosuite.environments.factory_sorting.factory_sorting_1_3fo3erfhisem import FactorySorting1_3FO3ERFHISEM  # noqa
from robosuite.environments.factory_sorting.factory_sorting_3_3fo3errph7x9 import FactorySorting3_3FO3ERRPH7X9  # noqa
from robosuite.environments.factory_sorting.factory_sorting_5_3fo3ertpxeut import FactorySorting5_3FO3ERTPXEUT  # noqa
from robosuite.environments.factory_sorting.factory_sorting_7_3fo3erfky9rn import FactorySorting7_3FO3ERFKY9RN  # noqa
from robosuite.environments.factory_sorting.factory_sorting_9_3fo3ert2c5fp import FactorySorting9_3FO3ERT2C5FP  # noqa


def _import_collect_module():
    path = (APP_DIR / "robosuite" / "robosuite" / "environments" / "factory_sorting"
            / "load_factory_sorting_1_3fo3erfhisem_collect.py")
    spec = importlib.util.spec_from_file_location("fs_collect", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", required=True, choices=["L1", "L2", "L3", "L4", "L5"])
    ap.add_argument("--object", default="", help="override object (default: task_config object)")
    ap.add_argument("--num-rollouts", type=int, default=20)
    ap.add_argument("--dist", type=float, default=0.0,
                    help="override base-to-object distance (default: trained 0.941; taller totes may need ~1.05)")
    ap.add_argument("--shift-x", type=float, default=0.0, help="post-hoc base x shift (clear scene AABB proxies)")
    ap.add_argument("--shift-y", type=float, default=0.0, help="post-hoc base y shift")
    ap.add_argument("--arrival-tol", type=float, default=0.0, help="override arrival tolerance (default 0.025)")
    ap.add_argument("--clearance", type=float, default=0.0, help="override site_above_clearance (default 0.05)")
    ap.add_argument("--yaw-shift", type=float, default=0.0, help="rotate base yaw (rad) to dodge side obstacles")
    ap.add_argument("--approach-rot", type=float, default=0.0,
                    help="rotate the WHOLE grasp geometry (base pose + virtual site targets) around the "
                         "object centre by this many degrees; e.g. 90 = approach from the east instead of "
                         "south. Use when the model's grasp sites are buried in a scene AABB proxy "
                         "(L5 back tote: south sites blocked by input_1 table, east face is open)")
    ap.add_argument("--site-forward", type=float, default=0.0,
                    help="with --approach-rot on a RECTANGULAR tote: distance from object centre to the "
                         "virtual sites along the new approach axis (wall half-extent minus ~0.025 inset; "
                         "white 1.2x tote east wall: 0.36-0.025=0.335)")
    ap.add_argument("--site-lateral", type=float, default=0.0,
                    help="lateral half-spacing of the virtual sites along the gripped wall "
                         "(white tote east wall: 0.165*0.48/0.72=0.11)")
    ap.add_argument("--allow-touch", action="store_true",
                    help="don't abort a rollout when the gripper brushes the TARGET object mid-approach "
                         "(scene-collision scoring only counts scene proxies; final grasp check still applies)")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    args_cli = ap.parse_args()

    cfg = json.loads((APP_DIR / "knowledge" / "task_config.json").read_text(encoding="utf-8"))
    task = next(t for t in cfg["tasks"] if t["level"] == args_cli.level)
    env_name = task["env_name"]
    object_name = args_cli.object or task["object"]
    source = task["source"]

    # Compute the calibrated grasp pose from the object's own grasp sites using a
    # cheap probe env (same geometry rule as pipeline/patch_grasp_pose.py).
    sys.path.insert(0, str(APP_DIR / "pipeline"))
    import patch_grasp_pose as pgp
    if args_cli.dist and args_cli.dist > 0:
        pgp.TRAINED_BASE_DIST = float(args_cli.dist)
    if object_name in pgp.KNOWN_DEMO_POSES and not args_cli.dist:
        pos, yaw = pgp.KNOWN_DEMO_POSES[object_name]
        print("using KNOWN demo pose for", object_name)
    else:
        probe = suite.make(
            env_name, robots="Tiago",
            has_renderer=False, has_offscreen_renderer=True,
            use_camera_obs=False, use_object_obs=True, ignore_done=True, control_freq=20,
        )
        try:
            probe.reset()
            pos, yaw = pgp.compute_pose(probe, object_name)
            if args_cli.approach_rot:
                import numpy as _np
                _obj = _np.array(probe.sim.data.body_xpos[probe.obj_body_id[object_name]])[:2]
                _rot = math.radians(args_cli.approach_rot)
                _c, _s = math.cos(_rot), math.sin(_rot)
                _d = _np.array([pos[0], pos[1]]) - _obj
                pos = [float(_obj[0] + _d[0] * _c - _d[1] * _s),
                       float(_obj[1] + _d[0] * _s + _d[1] * _c), 0.0]
                yaw = float(yaw) + _rot
                print(f"approach-rot {args_cli.approach_rot} deg: rotated base pose around object centre")
        finally:
            probe.close()
    base_pos = [float(pos[0]) + float(args_cli.shift_x), float(pos[1]) + float(args_cli.shift_y), 0.0]
    base_ori = [0.0, 0.0, float(yaw) + float(args_cli.yaw_shift)]

    col = _import_collect_module()
    if args_cli.approach_rot:
        # Rotate the descent/settle targets to match the rotated base pose: the
        # model's grasp sites stay fixed, so we synthesize "virtual sites" by
        # rotating each target around the object centre by the same angle.
        import numpy as _np
        _rot = math.radians(args_cli.approach_rot)
        _c, _s = math.cos(_rot), math.sin(_rot)
        _orig_gtp = col.get_target_positions

        def _gtp_rotated(env, object_name, site_below_offset):
            targets, site_names = _orig_gtp(env, object_name, site_below_offset)
            obj = _np.array(env.sim.data.body_xpos[env.obj_body_id[object_name]])[:2]
            if args_cli.site_forward > 0:
                # analytic virtual sites in the rotated approach frame (rectangular
                # totes change wall half-extents when the approach axis rotates)
                psi = float(base_ori[2])          # robot facing yaw
                fwd = _np.array([math.cos(psi), math.sin(psi)])
                right = _np.array([math.sin(psi), -math.cos(psi)])
                lat = args_cli.site_lateral
                for arm, t in targets.items():
                    sgn = 1.0 if arm == "right" else -1.0
                    xy = obj - args_cli.site_forward * fwd + sgn * lat * right
                    targets[arm] = _np.array([xy[0], xy[1], t[2]])
            else:
                for arm, t in targets.items():
                    d = t[:2] - obj
                    targets[arm] = _np.array([obj[0] + d[0] * _c - d[1] * _s,
                                              obj[1] + d[0] * _s + d[1] * _c, t[2]])
            return targets, site_names

        col.get_target_positions = _gtp_rotated
        print(f"approach-rot: virtual site targets rotated {args_cli.approach_rot} deg around object centre")
    if args_cli.allow_touch:
        _orig_seg = col.move_along_linear_segment

        def _seg_no_reject(*a, **kw):
            kw["reject_object_contact"] = False
            return _orig_seg(*a, **kw)

        col.move_along_linear_segment = _seg_no_reject
        print("allow-touch: target-object contact will not abort rollouts")
    render = bool(args_cli.render)

    out_dir_root = APP_DIR / "pipeline" / "collected" / "raw"
    out_dir_root.mkdir(parents=True, exist_ok=True)
    tag = f"{args_cli.level.lower()}_{object_name}"

    # Build the same args namespace the official collector uses (its defaults + our scene)
    ns = argparse.Namespace(
        num_rollouts=args_cli.num_rollouts,
        object_name=object_name,
        up_steps=col.DEFAULT_UP_STEPS, xy_steps=col.DEFAULT_XY_STEPS, down_steps=col.DEFAULT_DOWN_STEPS,
        safe_z=col.DEFAULT_SAFE_Z,
        site_above_clearance=(args_cli.clearance or col.DEFAULT_SITE_ABOVE_CLEARANCE),
        site_below_offset=col.DEFAULT_SITE_BELOW_OFFSET,
        arrival_tolerance=(args_cli.arrival_tol or col.DEFAULT_ARRIVAL_TOLERANCE),
        gripper_end_arrival_tolerance=max(args_cli.arrival_tol, col.DEFAULT_GRIPPER_END_ARRIVAL_TOLERANCE),
        settle_steps=col.DEFAULT_SETTLE_STEPS, grasp_steps=col.DEFAULT_GRASP_STEPS,
        post_success_hold_steps=col.DEFAULT_POST_SUCCESS_HOLD_STEPS,
        max_action=col.DEFAULT_MAX_ACTION,
        initial_view_steps=col.DEFAULT_INITIAL_VIEW_STEPS,
        render_sleep=col.DEFAULT_RENDER_SLEEP,
        camera_height=col.DEFAULT_CAMERA_HEIGHT, camera_width=col.DEFAULT_CAMERA_WIDTH,
        # CRITICAL: keep grasp-site markers INVISIBLE in the camera obs. Runtime eval
        # hides them; training with visible markers teaches the policy to key off
        # bright spheres that won't exist at eval time (train/eval visual mismatch).
        show_object_sites=False, object_site_size=col.DEFAULT_OBJECT_SITE_SIZE,
        robot_base_pos=base_pos, robot_base_ori=base_ori,
        directory=str(out_dir_root), output_name=tag,
        renderer="mjviewer", camera=col.DEFAULT_CAMERA, controller=None,
        gripper_types="Robotiq140Gripper", seed=args_cli.seed,
        no_render=not render,
    )

    print(f"level={args_cli.level} scene={env_name} object={object_name} "
          f"pose=({base_pos[0]:.3f},{base_pos[1]:.3f},yaw={base_ori[2]:.4f}) rollouts={ns.num_rollouts}")

    env_kwargs = col.make_env_kwargs(ns, render=render)
    dataset_env_kwargs = dict(env_kwargs)
    dataset_env_kwargs["has_renderer"] = False

    raw_env = suite.make(env_name=env_name, **env_kwargs)
    tmp_directory = tempfile.mkdtemp(prefix=f"fs_grasp_{tag}_")
    env = DataCollectionWrapper(raw_env, tmp_directory, collect_freq=1, flush_freq=1000)

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    out_dir = os.path.join(str(out_dir_root), timestamp)
    hdf5_name = f"{tag}_{timestamp}.hdf5"
    os.makedirs(out_dir, exist_ok=True)

    successes = 0
    obs_cache = {}
    for i in range(ns.num_rollouts):
        print(f"\nRollout {i + 1}/{ns.num_rollouts}")
        success, reason, ep_directory, obs_buffer = col.rollout_once(env, render=render, args=ns)
        successes += int(success)
        if success:
            obs_cache[os.path.normpath(ep_directory)] = obs_buffer
        print(f"Result: {reason}")
    env.close()

    hdf5_path, num_saved = col.gather_successful_demonstrations_as_hdf5(
        tmp_directory, out_dir, hdf5_name=hdf5_name,
        env_name=env_name, env_kwargs=dataset_env_kwargs,
        policy_info=vars(ns), obs_cache=obs_cache,
    )
    print(f"\nAttempts: {ns.num_rollouts}, successes: {successes}, saved: {num_saved}")
    print(f"HDF5 saved to: {hdf5_path}")
    return 0 if num_saved > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
