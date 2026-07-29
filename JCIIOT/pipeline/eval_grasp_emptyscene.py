"""eval_grasp_emptyscene.py — Falsification probe: run a checkpoint's grasp in the
COLLECTOR's env config (include_material_objects=False, empty scene) instead of the
eval harness's full scene.

If a v2 ckpt that FAILS the standard eval SUCCEEDS here, the root cause of the v2
regression is the scene-content distribution gap (trained on empty scenes, evaluated
on full scenes), not the policy itself.

Usage:
  .venv\\Scripts\\python pipeline\\eval_grasp_emptyscene.py --checkpoint <path> [--level L1]
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

import importlib.util  # noqa: E402


def _load_eval_module():
    path = (APP_DIR / "robosuite" / "robosuite" / "environments" / "factory_sorting"
            / "load_factory_sorting_evalization.py")
    spec = importlib.util.spec_from_file_location("fs_eval", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--level", default="L1")
    ap.add_argument("--object", default="")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--eval-steps", type=int, default=360)
    args_cli = ap.parse_args()

    cfg = json.loads((APP_DIR / "knowledge" / "task_config.json").read_text(encoding="utf-8"))
    task = next(t for t in cfg["tasks"] if t["level"] == args_cli.level)
    obj = args_cli.object or task["object"]
    pose = cfg["grasp_poses"][task["source"]]

    ev = _load_eval_module()

    # Patch the env-kwargs factory to the COLLECTOR's scene config (empty scene).
    _orig = ev.make_factory_sorting_env_kwargs

    def _empty_scene_kwargs(args):
        kw = _orig(args)
        kw["include_material_objects"] = False   # ← the only difference vs standard eval
        return kw

    ev.make_factory_sorting_env_kwargs = _empty_scene_kwargs
    print(f"[emptyscene probe] level={args_cli.level} object={obj} ckpt={args_cli.checkpoint}")

    argv = [
        "eval_grasp_emptyscene",
        "--checkpoint", args_cli.checkpoint,
        "--factory-scene", task["env_name"],
        "--object-name", obj,
        "--robot-base-pos", str(pose["pos"][0]), str(pose["pos"][1]), "0.0",
        "--robot-base-ori", "0.0", "0.0", str(pose["yaw"]),
        "--renderer", "mjviewer",
        "--device", args_cli.device,
        "--eval-steps", str(args_cli.eval_steps),
        "--no-render",
    ]
    # ev.parse_args() reads sys.argv directly (no argv parameter)
    sys.argv = argv
    ok = ev.main()
    print(f"[emptyscene probe] RESULT: {'SUCCESS' if ok else 'FAILURE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
