"""eval_grasp_noflip.py — Falsification probe #3: evaluate a checkpoint while feeding
the policy UNFLIPPED (bottom-up) images, matching what our collector recorded.

Background: robosuite's raw camera obs are bottom-up; robomimic's EnvRobosuite
flips them upright at eval time (di[k][::-1]). Our collector stored the RAW obs,
so v2 was trained on upside-down images. If v2 succeeds here (double-flip restores
the training orientation), the vertical-flip mismatch is the proven root cause.

Usage:
  .venv\\Scripts\\python pipeline\\eval_grasp_noflip.py --checkpoint <path> [--level L1]
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--level", default="L1")
    ap.add_argument("--object", default="")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--eval-steps", type=int, default=360)
    args_cli = ap.parse_args()

    # Patch BEFORE the eval module builds any env: re-flip image obs so the policy
    # sees the same (bottom-up) orientation it was trained on.
    from robomimic.envs.env_robosuite import EnvRobosuite

    _orig_get_obs = EnvRobosuite.get_observation

    def _get_obs_noflip(self, di=None):
        ret = _orig_get_obs(self, di)
        for k, v in list(ret.items()):
            if k.endswith("_image") and getattr(v, "ndim", 0) >= 3:
                ret[k] = v[::-1].copy()   # undo robomimic's upright flip
        return ret

    EnvRobosuite.get_observation = _get_obs_noflip
    print("[noflip probe] EnvRobosuite.get_observation patched (images fed bottom-up)")

    cfg = json.loads((APP_DIR / "knowledge" / "task_config.json").read_text(encoding="utf-8"))
    task = next(t for t in cfg["tasks"] if t["level"] == args_cli.level)
    obj = args_cli.object or task["object"]
    pose = cfg["grasp_poses"][task["source"]]

    path = (APP_DIR / "robosuite" / "robosuite" / "environments" / "factory_sorting"
            / "load_factory_sorting_evalization.py")
    spec = importlib.util.spec_from_file_location("fs_eval", path)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)

    sys.argv = [
        "eval_grasp_noflip",
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
    ok = ev.main()
    print(f"[noflip probe] RESULT: {'SUCCESS' if ok else 'FAILURE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
