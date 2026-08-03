"""
score_trajectory.py — Headless re-implementation of app.py's objective scorer.

Reproduces the exact rule used by the Streamlit dashboard
(`SCORE_RULE_VERSION = grasp_success_gate_l5_multi_v2`) WITHOUT importing the
Streamlit app, so trajectories produced by a headless `run_level` can be scored
from the command line and packaged for submission.

Rule (per level max = 10/15/20/25/30, split ~50/50):
  * "Grasp success & left source": grasp_end.success AND object moved >1.0 m in
    x or y away from the source station.
  * "Object reached target table": grasp succeeded AND final object is <0.80 m
    (xy) from the target station center.
  * Collision anywhere in the trajectory: -5.
  * L5 scores the three white totes on input_1 independently (5+5 each).

Usage:
  python pipeline\\score_trajectory.py --trajectory <traj.json> --level L1
  python pipeline\\score_trajectory.py --trajectory <traj.json> --task-index 0 --out score.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1]          # JCIIOT
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

L5_INPUT1_OBJECTS = (
    "white_tote_b01_left_center",
    "white_tote_b01_left_front",
    "white_tote_b01_left_back",
)
MAX_SCORES = [10, 15, 20, 25, 30]
OFFICIAL_REFERENCE_COMMIT = "129e94a9cff787031472045e19c24a4baeaefc48"


def _json_safe(v):
    """Coerce numpy scalars/arrays to plain Python types for json.dumps."""
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


def _load_task_config() -> dict:
    p = APP_DIR / "knowledge" / "task_config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


_CFG = _load_task_config()
_TASKS = _CFG.get("tasks", [])


def _task(i: int) -> dict:
    return _TASKS[min(i, len(_TASKS) - 1)] if _TASKS else {}


def _task_object_names(i: int) -> list[str]:
    value = _task(i).get("object", "")
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return []


def _object_name_matches(name: str, candidates: list[str]) -> bool:
    if not candidates:
        return True
    name = str(name or "")
    if not name:
        return True
    return any(candidate == name or candidate in name or name in candidate for candidate in candidates)


def _level_to_index(level: str) -> int:
    return {"l1": 0, "l2": 1, "l3": 2, "l4": 3, "l5": 4}[level.strip().lower()]


def _choose_map_files(task_index: int):
    map_dir = APP_DIR / "robosuite" / "robosuite" / "environments" / "factory_sorting" / "generated_maps"
    prefix = _task(task_index).get("scene_prefix", "factory_sorting_1_3fo3erfhisem")
    semantic = map_dir / f"{prefix}_scene_regenerated_semantic_map.json"
    grid = map_dir / f"{prefix}_scene_regenerated_occupancy_grid.npy"
    if semantic.exists() and grid.exists():
        return semantic, grid
    fb = _task(0).get("scene_prefix", "factory_sorting_1_3fo3erfhisem")
    return (map_dir / f"{fb}_scene_regenerated_semantic_map.json",
            map_dir / f"{fb}_scene_regenerated_occupancy_grid.npy")


def _event_success_value(value) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "ok", "success", "succeeded"}


def _obj_pos(object_positions: dict, object_name: str):
    if not isinstance(object_positions, dict) or not object_name:
        return None
    pos = object_positions.get(object_name)
    if pos is None:
        for cand, cpos in object_positions.items():
            cand = str(cand)
            if object_name in cand or cand in object_name:
                pos = cpos
                break
    try:
        if pos is None or len(pos) < 2:
            return None
        z = float(pos[2]) if len(pos) >= 3 else 0.0
        return float(pos[0]), float(pos[1]), z
    except Exception:
        return None


def _l5_match_object(event_object: str, tracked):
    event_object = str(event_object or "")
    if not event_object:
        return None
    for name in tracked:
        if name == event_object or name in event_object or event_object in name:
            return name
    return None


def _l5_left_source_after_grasp(frames, object_name, src_xy, start_frame):
    last_dx = last_dy = None
    start_frame = max(0, min(int(start_frame), max(0, len(frames) - 1)))
    for frame in frames[start_frame:]:
        if not isinstance(frame, dict):
            continue
        pos = _obj_pos(frame.get("object_positions", {}), object_name)
        if pos is None:
            continue
        last_dx = abs(pos[0] - float(src_xy[0]))
        last_dy = abs(pos[1] - float(src_xy[1]))
        if last_dx > 1.0 or last_dy > 1.0:
            return True, last_dx, last_dy
    return False, last_dx, last_dy


def _scene_ports(task_index: int):
    from robot_agent.core.map_loader import load_map_files
    from robot_agent.core.scene_context import SceneContext
    sem, grid = _choose_map_files(task_index)
    scene_dict, _ = load_map_files(sem, grid)
    ctx = SceneContext.from_semantic_map(scene_dict)
    src = ctx.input_ports.get(_task(task_index).get("source", ""))
    tgt = ctx.output_ports.get(_task(task_index).get("target", ""))
    return src, tgt


def score(task_index: int, trajectory: Path, object_override: str = "") -> dict:
    traj = json.loads(Path(trajectory).read_text(encoding="utf-8"))
    frames = traj.get("frames", []) or []
    events = traj.get("events", []) or []
    src, tgt = _scene_ports(task_index)
    if src is None or tgt is None:
        return {"total": 0, "items": [], "error": "source/target port not found in scene map"}
    src_xy = np.array(src.center[:2], dtype=float)
    tgt_xy = np.array(tgt.center[:2], dtype=float)
    tgt_z = float(tgt.center[2]) if len(tgt.center) >= 3 else 1.09
    max_score = MAX_SCORES[min(task_index, 4)]

    if task_index == 4:
        return _score_l5(task_index, frames, events, src_xy, tgt_xy, tgt_z)

    obj_hints = [object_override] if object_override else _task_object_names(task_index)
    grasp_success = False
    grasped_object_name = None
    for ev in events:
        if not isinstance(ev, dict) or ev.get("name") != "grasp_end":
            continue
        src_ok = not ev.get("source") or str(ev.get("source")) == _task(task_index).get("source")
        eo = str(ev.get("object_name") or "")
        obj_ok = _object_name_matches(eo, obj_hints)
        if src_ok and obj_ok and _event_success_value(ev.get("success")):
            grasp_success = True
            grasped_object_name = eo or None
            break

    if not frames:
        return {"total": 0, "items": [], "error": "no frames"}
    last_positions = frames[-1].get("object_positions", {})
    px = py = pz = None
    score_candidates = []
    if grasped_object_name:
        score_candidates.append(grasped_object_name)
    score_candidates.extend(obj_hints)
    for candidate in score_candidates:
        candidate_pos = _obj_pos(last_positions, candidate)
        if candidate_pos is not None:
            px, py, pz = candidate_pos
            break
    if px is None and last_positions:
        best = float("inf")
        for name, pos in last_positions.items():
            if obj_hints and not _object_name_matches(str(name), obj_hints):
                continue
            d = float(np.linalg.norm(np.array(pos[:2]) - tgt_xy))
            if d < best:
                best, px, py, pz = d, float(pos[0]), float(pos[1]), float(pos[2])
    if px is None:
        return {"total": 0, "items": [], "error": "no object positions in last frame"}

    dx_src, dy_src = abs(px - src_xy[0]), abs(py - src_xy[1])
    dist_tgt = float(np.linalg.norm(np.array([px, py]) - tgt_xy))
    w_leave = max(1, max_score // 2)
    w_place = max_score - w_leave
    left_source = grasp_success and (dx_src > 1.0 or dy_src > 1.0)
    on_target = grasp_success and dist_tgt < 0.80
    items = [
        {"label": f"Grasp success & left source (grasp={'yes' if grasp_success else 'no'}, dx_src={dx_src:.2f}m, dy_src={dy_src:.2f}m)",
         "score": w_leave, "ok": left_source},
        {"label": f"Object reached target table after grasp (grasp={'yes' if grasp_success else 'no'}, dist={dist_tgt:.2f}m, x={px:.2f}, y={py:.2f}, z={pz:.2f})",
         "score": w_place, "ok": on_target},
    ]
    total = sum(it["score"] for it in items if it["ok"])
    if any(isinstance(f, dict) and f.get("has_collision") for f in frames):
        total = max(0, total - 5)
        items.append({"label": "Collision penalty", "score": -5, "ok": True, "is_penalty": True})
    return {"total": total, "items": items, "max": max_score}


def _score_l5(task_index, frames, events, src_xy, tgt_xy, tgt_z) -> dict:
    if not frames:
        return {"total": 0, "items": []}
    first_pos = frames[0].get("object_positions", {})
    last_pos = frames[-1].get("object_positions", {})
    tracked = [n for n in L5_INPUT1_OBJECTS
               if _obj_pos(first_pos, n) is not None or _obj_pos(last_pos, n) is not None] or list(L5_INPUT1_OBJECTS)
    grasp_frame = {}
    for ev in events:
        if not isinstance(ev, dict) or ev.get("name") != "grasp_end" or not _event_success_value(ev.get("success")):
            continue
        name = _l5_match_object(str(ev.get("object_name") or ""), tracked)
        if name and name not in grasp_frame:
            try:
                grasp_frame[name] = int(ev.get("frame", 0))
            except Exception:
                grasp_frame[name] = 0
    items = []
    for name in tracked:
        grasped = name in grasp_frame
        left_ok = False
        if grasped:
            left_ok, _, _ = _l5_left_source_after_grasp(frames, name, src_xy, grasp_frame[name])
        final_pos = _obj_pos(last_pos, name)
        placed_ok = bool(grasped and final_pos is not None
                         and float(np.linalg.norm(np.array(final_pos[:2]) - tgt_xy)) < 0.80)
        items.append({"label": f"L5 {name}: grasped & left source (grasp={'yes' if grasped else 'no'})", "score": 5, "ok": left_ok})
        items.append({"label": f"L5 {name}: placed at target (grasp={'yes' if grasped else 'no'})", "score": 5, "ok": placed_ok})
    total = sum(it["score"] for it in items if it["ok"])
    if any(isinstance(f, dict) and f.get("has_collision") for f in frames):
        total = max(0, total - 5)
        items.append({"label": "Collision penalty", "score": -5, "ok": True, "is_penalty": True})
    return {"total": total, "items": items, "max": 30}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Headless JCIIOT trajectory scorer")
    ap.add_argument("--trajectory", required=True, type=Path)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--task-index", type=int)
    g.add_argument("--level", type=str, help="L1..L5")
    ap.add_argument("--object", type=str, default="", help="override graded object name (e.g. L3 blue-box ruling)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    task_index = args.task_index if args.task_index is not None else _level_to_index(args.level)

    result = score(task_index, args.trajectory, object_override=args.object)
    result = _json_safe(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n==> TOTAL {result.get('total', 0)} / {result.get('max', MAX_SCORES[min(task_index,4)])}")
    if args.out:
        args.out.write_text(json.dumps({
            "task_index": task_index,
            "trajectory": str(args.trajectory),
            "score": result.get("total", 0),
            "score_rule_version": "grasp_success_gate_l5_multi_v2",
            "official_reference_commit": OFFICIAL_REFERENCE_COMMIT,
            "details": result,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
