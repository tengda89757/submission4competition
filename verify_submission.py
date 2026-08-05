#!/usr/bin/env python3
"""Verify the five JCIIOT submission packages with only Python's stdlib.

The scoring logic mirrors score rule grasp_success_gate_l5_multi_v2. Source and
target centers are read from semantic maps copied byte-for-byte from official
commit 129e94a9cff787031472045e19c24a4baeaefc48.

Usage:
    python verify_submission.py
    python verify_submission.py --json-out submission/verification_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_SUBMISSIONS = ROOT / "submission"
REFERENCE_DIR = ROOT / "verification"
OFFICIAL_REFERENCE_COMMIT = "129e94a9cff787031472045e19c24a4baeaefc48"
SCORE_RULE_VERSION = "grasp_success_gate_l5_multi_v2"
EXPECTED_MEMBERS = {"trajectory.json", "score.json", "submission_manifest.json"}
L5_OBJECTS = (
    "white_tote_b01_left_center",
    "white_tote_b01_left_front",
    "white_tote_b01_left_back",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _event_succeeded(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "ok",
        "success",
        "succeeded",
    }


def _object_name_matches(name: str, candidates: list[str]) -> bool:
    if not candidates or not name:
        return True
    return any(candidate == name or candidate in name or name in candidate for candidate in candidates)


def _object_position(object_positions: Any, object_name: str) -> tuple[float, float, float] | None:
    if not isinstance(object_positions, dict) or not object_name:
        return None
    position = object_positions.get(object_name)
    if position is None:
        for candidate, candidate_position in object_positions.items():
            candidate = str(candidate)
            if object_name in candidate or candidate in object_name:
                position = candidate_position
                break
    try:
        if position is None or len(position) < 2:
            return None
        z = float(position[2]) if len(position) >= 3 else 0.0
        return float(position[0]), float(position[1]), z
    except (TypeError, ValueError):
        return None


def _xy_distance(position: tuple[float, float, float], center: list[float]) -> float:
    return math.hypot(position[0] - float(center[0]), position[1] - float(center[1]))


def _load_tasks() -> list[dict[str, Any]]:
    document = _read_json(REFERENCE_DIR / "task_config.json")
    tasks = document.get("tasks", [])
    expected_levels = ["L1", "L2", "L3", "L4", "L5"]
    if [task.get("level") for task in tasks] != expected_levels:
        raise ValueError("verification/task_config.json does not contain the expected L1-L5 order")
    return tasks


def _port_centers(task: dict[str, Any]) -> tuple[list[float], list[float]]:
    scene_prefix = str(task["scene_prefix"])
    map_path = REFERENCE_DIR / "maps" / f"{scene_prefix}_scene_regenerated_semantic_map.json"
    scene = _read_json(map_path)
    source = scene.get("input_ports", {}).get(task["source"])
    target = scene.get("output_ports", {}).get(task["target"])
    if not source or not target:
        raise ValueError(
            f"missing source/target port in {map_path.name}: {task['source']} -> {task['target']}"
        )
    return source["center"], target["center"]


def _has_collision(frames: list[Any]) -> bool:
    return any(isinstance(frame, dict) and frame.get("has_collision") for frame in frames)


def _score_single(
    task: dict[str, Any],
    frames: list[Any],
    events: list[Any],
    source_center: list[float],
    target_center: list[float],
) -> dict[str, Any]:
    object_hints = task.get("object", [])
    if isinstance(object_hints, str):
        object_hints = [object_hints] if object_hints else []
    object_hints = [str(name) for name in object_hints if name]

    grasp_succeeded = False
    grasped_object = ""
    for event in events:
        if not isinstance(event, dict) or event.get("name") != "grasp_end":
            continue
        source_ok = not event.get("source") or str(event.get("source")) == task["source"]
        event_object = str(event.get("object_name") or "")
        if source_ok and _object_name_matches(event_object, object_hints) and _event_succeeded(event.get("success")):
            grasp_succeeded = True
            grasped_object = event_object
            break

    maximum = int(task["max_score"])
    if not frames:
        return {"total": 0, "max": maximum, "items": [], "error": "no frames"}

    final_positions = frames[-1].get("object_positions", {}) if isinstance(frames[-1], dict) else {}
    final_position = None
    for candidate in ([grasped_object] if grasped_object else []) + object_hints:
        final_position = _object_position(final_positions, candidate)
        if final_position is not None:
            break

    if final_position is None and isinstance(final_positions, dict):
        nearest_distance = float("inf")
        for name, value in final_positions.items():
            if object_hints and not _object_name_matches(str(name), object_hints):
                continue
            candidate_position = _object_position({str(name): value}, str(name))
            if candidate_position is None:
                continue
            distance = _xy_distance(candidate_position, target_center)
            if distance < nearest_distance:
                nearest_distance = distance
                final_position = candidate_position

    if final_position is None:
        return {
            "total": 0,
            "max": maximum,
            "items": [],
            "error": "no scored object position in final frame",
        }

    dx_source = abs(final_position[0] - float(source_center[0]))
    dy_source = abs(final_position[1] - float(source_center[1]))
    distance_target = _xy_distance(final_position, target_center)
    leave_weight = max(1, maximum // 2)
    place_weight = maximum - leave_weight
    left_source = grasp_succeeded and (dx_source > 1.0 or dy_source > 1.0)
    on_target = grasp_succeeded and distance_target < 0.80
    items = [
        {
            "label": "Grasp success and left source",
            "score": leave_weight,
            "ok": left_source,
            "dx_source": dx_source,
            "dy_source": dy_source,
        },
        {
            "label": "Object reached target after grasp",
            "score": place_weight,
            "ok": on_target,
            "distance_target": distance_target,
            "final_position": list(final_position),
        },
    ]
    total = sum(item["score"] for item in items if item["ok"])
    if _has_collision(frames):
        total = max(0, total - 5)
        items.append({"label": "Collision penalty", "score": -5, "ok": True})
    return {"total": total, "max": maximum, "items": items}


def _matching_l5_object(event_object: str, tracked: list[str]) -> str | None:
    if not event_object:
        return None
    for name in tracked:
        if name == event_object or name in event_object or event_object in name:
            return name
    return None


def _left_source_after_grasp(
    frames: list[Any],
    object_name: str,
    source_center: list[float],
    start_frame: int,
) -> bool:
    start_frame = max(0, min(start_frame, max(0, len(frames) - 1)))
    for frame in frames[start_frame:]:
        if not isinstance(frame, dict):
            continue
        position = _object_position(frame.get("object_positions", {}), object_name)
        if position is None:
            continue
        if (
            abs(position[0] - float(source_center[0])) > 1.0
            or abs(position[1] - float(source_center[1])) > 1.0
        ):
            return True
    return False


def _score_l5(
    task: dict[str, Any],
    frames: list[Any],
    events: list[Any],
    source_center: list[float],
    target_center: list[float],
) -> dict[str, Any]:
    if not frames:
        return {"total": 0, "max": 30, "items": [], "error": "no frames"}

    first_positions = frames[0].get("object_positions", {}) if isinstance(frames[0], dict) else {}
    final_positions = frames[-1].get("object_positions", {}) if isinstance(frames[-1], dict) else {}
    tracked = [
        name
        for name in L5_OBJECTS
        if _object_position(first_positions, name) is not None
        or _object_position(final_positions, name) is not None
    ] or list(L5_OBJECTS)

    grasp_frames: dict[str, int] = {}
    for event in events:
        if (
            not isinstance(event, dict)
            or event.get("name") != "grasp_end"
            or not _event_succeeded(event.get("success"))
        ):
            continue
        name = _matching_l5_object(str(event.get("object_name") or ""), tracked)
        if name and name not in grasp_frames:
            try:
                grasp_frames[name] = int(event.get("frame", 0))
            except (TypeError, ValueError):
                grasp_frames[name] = 0

    items = []
    for name in tracked:
        grasped = name in grasp_frames
        left_source = grasped and _left_source_after_grasp(
            frames, name, source_center, grasp_frames.get(name, 0)
        )
        final_position = _object_position(final_positions, name)
        placed = bool(
            grasped
            and final_position is not None
            and _xy_distance(final_position, target_center) < 0.80
        )
        items.append(
            {
                "label": f"L5 {name}: grasped and left source",
                "score": 5,
                "ok": left_source,
            }
        )
        items.append(
            {
                "label": f"L5 {name}: placed at target",
                "score": 5,
                "ok": placed,
            }
        )

    total = sum(item["score"] for item in items if item["ok"])
    if _has_collision(frames):
        total = max(0, total - 5)
        items.append({"label": "Collision penalty", "score": -5, "ok": True})
    return {"total": total, "max": int(task["max_score"]), "items": items}


def _score(task: dict[str, Any], trajectory: dict[str, Any]) -> dict[str, Any]:
    frames = trajectory.get("frames", []) or []
    events = trajectory.get("events", []) or []
    if not isinstance(frames, list) or not isinstance(events, list):
        raise ValueError("trajectory frames/events must be lists")
    source_center, target_center = _port_centers(task)
    if task["level"] == "L5":
        return _score_l5(task, frames, events, source_center, target_center)
    return _score_single(task, frames, events, source_center, target_center)


def _declared_hashes(submissions: Path) -> dict[str, str]:
    path = submissions / "SHA256SUMS.txt"
    hashes: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        digest, filename = line.split(maxsplit=1)
        hashes[filename.lstrip("*")] = digest.lower()
    return hashes


def _verify_package(
    task: dict[str, Any],
    package: Path,
    declared_hash: str | None,
) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    package_hash = _sha256(package_bytes)
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(EXPECTED_MEMBERS) or set(names) != EXPECTED_MEMBERS:
            raise ValueError(f"unexpected ZIP members: {names}")
        trajectory_bytes = archive.read("trajectory.json")
        trajectory = json.loads(trajectory_bytes)
        score_document = json.loads(archive.read("score.json"))
        manifest = json.loads(archive.read("submission_manifest.json"))

    result = _score(task, trajectory)
    maximum = int(task["max_score"])
    reported = int(score_document.get("score", -1))
    recomputed = int(result.get("total", -1))
    checks = {
        "sha256_matches": declared_hash == package_hash,
        "reported_score_matches": reported == maximum,
        "recomputed_score_matches": recomputed == maximum,
        "score_details_match": int(score_document.get("details", {}).get("total", -1)) == reported,
        "score_rule_matches": score_document.get("score_rule_version") == SCORE_RULE_VERSION,
        "score_reference_matches": score_document.get("official_reference_commit")
        == OFFICIAL_REFERENCE_COMMIT,
        "manifest_level_matches": manifest.get("level") == task["level"],
        "manifest_task_index_matches": manifest.get("task_index") == int(task["level"][1:]) - 1,
        "manifest_environment_matches": manifest.get("env_name") == task["env_name"],
        "manifest_max_matches": manifest.get("max_score") == maximum,
        "manifest_score_matches": manifest.get("objective_score") == maximum,
        "manifest_rule_matches": manifest.get("score_rule_version") == SCORE_RULE_VERSION,
        "manifest_reference_matches": manifest.get("official_reference_commit")
        == OFFICIAL_REFERENCE_COMMIT,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "level": task["level"],
        "package": package.name,
        "package_sha256": package_hash,
        "trajectory_sha256": _sha256(trajectory_bytes),
        "members": sorted(EXPECTED_MEMBERS),
        "frames": len(trajectory.get("frames", [])),
        "events": len(trajectory.get("events", [])),
        "reported": reported,
        "recomputed": recomputed,
        "max": maximum,
        "collision_detected": _has_collision(trajectory.get("frames", []) or []),
        "checks": checks,
        "status": "PASS" if not failed_checks else "FAIL",
        "failed_checks": failed_checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--submissions",
        type=Path,
        default=DEFAULT_SUBMISSIONS,
        help="Directory containing exactly one L1-L5 ZIP plus SHA256SUMS.txt",
    )
    parser.add_argument("--json-out", type=Path, help="Optional JSON report output path")
    args = parser.parse_args(argv)
    submissions = args.submissions.resolve()

    tasks = _load_tasks()
    declared_hashes = _declared_hashes(submissions)
    rows: list[dict[str, Any]] = []

    for task in tasks:
        level = task["level"]
        candidates = sorted(submissions.glob(f"{level}_*.zip"))
        if len(candidates) != 1:
            rows.append(
                {
                    "level": level,
                    "package": "<missing>" if not candidates else "<multiple>",
                    "reported": None,
                    "recomputed": None,
                    "max": int(task["max_score"]),
                    "status": "FAIL",
                    "failed_checks": [f"expected exactly one {level}_*.zip, found {len(candidates)}"],
                }
            )
            continue
        package = candidates[0]
        try:
            row = _verify_package(task, package, declared_hashes.get(package.name))
        except Exception as exc:
            row = {
                "level": level,
                "package": package.name,
                "reported": None,
                "recomputed": None,
                "max": int(task["max_score"]),
                "status": "FAIL",
                "failed_checks": [f"{type(exc).__name__}: {exc}"],
            }
        rows.append(row)

    package_names = {row["package"] for row in rows if row["package"].endswith(".zip")}
    hash_list_ok = set(declared_hashes) == package_names
    if not hash_list_ok:
        rows.append(
            {
                "level": "HASH",
                "package": "SHA256SUMS.txt",
                "reported": None,
                "recomputed": None,
                "max": 0,
                "status": "FAIL",
                "failed_checks": ["checksum list does not exactly match the five packages"],
            }
        )

    reported_total = sum(row.get("reported") or 0 for row in rows if row["level"] != "HASH")
    recomputed_total = sum(row.get("recomputed") or 0 for row in rows if row["level"] != "HASH")
    maximum_total = sum(int(task["max_score"]) for task in tasks)
    success = (
        len(rows) == 5
        and hash_list_ok
        and all(row["status"] == "PASS" for row in rows)
        and reported_total == recomputed_total == maximum_total == 100
    )

    print()
    print(f"{'Level':<6}{'Package':<28}{'Reported':>9}{'Recomputed':>12}{'Max':>5}  Result")
    print("-" * 78)
    for row in rows:
        print(
            f"{row['level']:<6}{row['package']:<28}"
            f"{str(row.get('reported')):>9}{str(row.get('recomputed')):>12}"
            f"{row.get('max', 0):>5}  {row['status']}"
        )
        if row["status"] != "PASS":
            for failure in row.get("failed_checks", []):
                print(f"      - {failure}")
    print("-" * 78)
    print(f"{'TOTAL':<34}{reported_total:>9}{recomputed_total:>12}{maximum_total:>5}")
    print(f"Official reference: {OFFICIAL_REFERENCE_COMMIT}")

    report = {
        "official_reference_commit": OFFICIAL_REFERENCE_COMMIT,
        "score_rule_version": SCORE_RULE_VERSION,
        "submissions_directory": _display_path(submissions),
        "reported_total": reported_total,
        "recomputed_total": recomputed_total,
        "maximum_total": maximum_total,
        "result": "PASS" if success else "FAIL",
        "packages": rows,
    }
    if args.json_out:
        output = args.json_out.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Verification report: {_display_path(output)}")

    if success:
        print("RESULT: [OK] Five unique packages pass integrity and objective scoring checks: 100/100.")
        return 0
    print("RESULT: [FAIL] Submission verification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
