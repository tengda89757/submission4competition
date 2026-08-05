#!/usr/bin/env python3
"""Independently verify the frozen L1-L5 runs and full-frame videos."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "tmp" / "final_artifacts"
VIDEO_ROOT = ARTIFACT_ROOT / "videos"
RESULT_ROOT = ARTIFACT_ROOT / "results"
OFFICIAL_REFERENCE_COMMIT = "129e94a9cff787031472045e19c24a4baeaefc48"
SCORE_RULE_VERSION = "grasp_success_gate_l5_multi_v2"

RUNS: dict[str, dict[str, Any]] = {
    "L1": {"environment": "FactorySorting1_3FO3ERFHISEM", "stamp": "20260805_081914", "maximum": 10},
    "L2": {"environment": "FactorySorting3_3FO3ERRPH7X9", "stamp": "20260805_082054", "maximum": 15},
    "L3": {"environment": "FactorySorting5_3FO3ERTPXEUT", "stamp": "20260805_082229", "maximum": 20},
    "L4": {"environment": "FactorySorting7_3FO3ERFKY9RN", "stamp": "20260805_082430", "maximum": 25},
    "L5": {"environment": "FactorySorting9_3FO3ERT2C5FP", "stamp": "20260805_080916", "maximum": 30},
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_video(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path}")
    declared_frames = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
    height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    decoded = 0
    black_composite: list[int] = []
    black_left: list[int] = []
    black_right: list[int] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        decoded += 1
        midpoint = width // 2
        if int(frame.max()) <= 10:
            black_composite.append(decoded - 1)
        if int(frame[:, :midpoint].max()) <= 10:
            black_left.append(decoded - 1)
        if int(frame[:, midpoint:].max()) <= 10:
            black_right.append(decoded - 1)
    capture.release()
    return {
        "declared_frames": declared_frames,
        "decoded_frames": decoded,
        "fps": round(fps, 6),
        "resolution": [width, height],
        "black_composite_frames": black_composite,
        "black_left_view_frames": black_left,
        "black_right_view_frames": black_right,
    }


def _paths(level: str, config: dict[str, Any]) -> dict[str, Path]:
    record_dir = ROOT / "recordings" / config["environment"]
    stamp = config["stamp"]
    return {
        "trajectory": record_dir / f"trajectory_{stamp}_OK.json",
        "score": record_dir / f"score_{stamp}.json",
        "audit": record_dir / f"realism_{stamp}.json",
        "result": record_dir / f"result_{stamp}.json",
        "video": VIDEO_ROOT / f"{level}_dualview_full.mp4",
        "video_metadata": VIDEO_ROOT / f"{level}_dualview_full.metadata.json",
    }


def _l5_placement_distances(trajectory: dict[str, Any]) -> dict[str, float]:
    target_xy = (0.144, 8.473)
    names = (
        "white_tote_b01_left_front",
        "white_tote_b01_left_center",
        "white_tote_b01_left_back",
    )
    final_positions = trajectory["frames"][-1]["object_positions"]
    return {
        name: round(
            math.hypot(
                float(final_positions[name][0]) - target_xy[0],
                float(final_positions[name][1]) - target_xy[1],
            ),
            6,
        )
        for name in names
    }


def main() -> int:
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    run_rows: list[dict[str, Any]] = []
    video_rows: list[dict[str, Any]] = []

    for level, config in RUNS.items():
        paths = _paths(level, config)
        missing = [name for name, path in paths.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"{level}: missing {', '.join(missing)}")

        trajectory = _load(paths["trajectory"])
        score = _load(paths["score"])
        audit = _load(paths["audit"])
        result = _load(paths["result"])
        metadata = _load(paths["video_metadata"])
        decoded = _decode_video(paths["video"])

        trajectory_sha = _sha256(paths["trajectory"])
        video_sha = _sha256(paths["video"])
        frames = len(trajectory.get("frames", []))
        transition = audit["transition"]
        contact = audit["contact"]
        checks = {
            "objective_score_full": int(score["score"]) == int(config["maximum"]),
            "score_reference_frozen": score.get("official_reference_commit") == OFFICIAL_REFERENCE_COMMIT,
            "score_rule_frozen": score.get("score_rule_version") == SCORE_RULE_VERSION,
            "realism_audit_pass": audit.get("pass") is True,
            "recorded_collision_frames_zero": not audit.get("recorded_collision_frames"),
            "unintended_material_contact_frames_zero": not contact.get("unintended_contact_frames"),
            "held_contact_at_least_99_percent": float(contact["contact_fraction"]) >= 0.99,
            "video_source_hash_matches": metadata.get("source_trajectory_sha256") == trajectory_sha,
            "video_hash_matches": metadata.get("video_sha256") == video_sha,
            "video_decoded_frame_count_matches": decoded["decoded_frames"] == frames,
            "video_declared_frame_count_matches": decoded["declared_frames"] == frames,
            "video_metadata_frame_count_matches": int(metadata["encoded_frames"]) == frames,
            "video_has_no_black_composite_frames": not decoded["black_composite_frames"],
            "video_left_view_has_no_black_frames": not decoded["black_left_view_frames"],
            "video_right_view_has_no_black_frames": not decoded["black_right_view_frames"],
        }
        failures = [name for name, passed in checks.items() if not passed]
        status = "PASS" if not failures else "FAIL"

        run_row: dict[str, Any] = {
            "level": level,
            "environment": config["environment"],
            "run_stamp": config["stamp"],
            "score": int(score["score"]),
            "maximum": int(config["maximum"]),
            "elapsed_wall_seconds": float(result["elapsed_sec"]),
            "frames": frames,
            "events": len(trajectory.get("events", [])),
            "trajectory_sha256": trajectory_sha,
            "realism": {
                "max_base_step_m": transition["max_base_step_m"],
                "max_base_turn_rad": transition["max_base_turn_rad"],
                "max_joint_step": transition["max_joint_step"],
                "max_object_step_m": transition["max_object_step_m"],
                "max_object_turn_rad": transition["max_object_turn_rad"],
                "held_frames": contact["held_frames"],
                "held_contact_frames": contact["contact_frames"],
                "held_contact_fraction": contact["contact_fraction"],
                "recorded_collision_frames": len(audit["recorded_collision_frames"]),
                "unintended_material_contact_frames": len(contact["unintended_contact_frames"]),
                "limits": audit["limits"],
                "pass": audit["pass"],
            },
            "status": status,
            "failed_checks": failures,
        }
        if level == "L5":
            run_row["final_target_distances_m"] = _l5_placement_distances(trajectory)
            run_row["per_object_contact"] = contact["per_object"]
        run_rows.append(run_row)

        video_rows.append({
            "level": level,
            "file": paths["video"].name,
            "sha256": video_sha,
            "bytes": paths["video"].stat().st_size,
            "source_frames": frames,
            "camera_views": metadata["camera_views"],
            "duration_seconds": metadata["duration_seconds"],
            **decoded,
            "status": "PASS" if not [name for name in failures if name.startswith("video_")] else "FAIL",
            "failed_checks": [name for name in failures if name.startswith("video_")],
        })

    total_score = sum(row["score"] for row in run_rows)
    total_maximum = sum(row["maximum"] for row in run_rows)
    overall_pass = total_score == total_maximum == 100 and all(row["status"] == "PASS" for row in run_rows)
    summary = {
        "format_version": 1,
        "generated_from_frozen_runs": True,
        "official_reference_commit": OFFICIAL_REFERENCE_COMMIT,
        "score_rule_version": SCORE_RULE_VERSION,
        "total_score": total_score,
        "total_maximum": total_maximum,
        "total_frames": sum(row["frames"] for row in run_rows),
        "total_elapsed_wall_seconds": round(sum(row["elapsed_wall_seconds"] for row in run_rows), 3),
        "successful_grasps": sum(
            1
            for level, config in RUNS.items()
            for event in _load(_paths(level, config)["trajectory"]).get("events", [])
            if event.get("name") == "grasp_end" and event.get("success") is True
        ),
        "recorded_collision_frames": sum(row["realism"]["recorded_collision_frames"] for row in run_rows),
        "unintended_material_contact_frames": sum(row["realism"]["unintended_material_contact_frames"] for row in run_rows),
        "result": "PASS" if overall_pass else "FAIL",
        "levels": run_rows,
    }
    video_report = {
        "format_version": 1,
        "verification_scope": "full decode of every encoded frame",
        "result": "PASS" if all(row["status"] == "PASS" for row in video_rows) else "FAIL",
        "videos": video_rows,
    }
    (RESULT_ROOT / "final_run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (RESULT_ROOT / "video_verification.json").write_text(
        json.dumps(video_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("Level  Score  Frames  Contact    Video  Result")
    print("-" * 55)
    for run, video in zip(run_rows, video_rows):
        print(
            f"{run['level']:<6} {run['score']:>2}/{run['maximum']:<2} "
            f"{run['frames']:>7}  {run['realism']['held_contact_fraction']:.6f}  "
            f"{video['decoded_frames']:>5}  {run['status']}"
        )
    print("-" * 55)
    print(f"TOTAL  {total_score}/{total_maximum}  {summary['total_frames']} frames  {summary['result']}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
