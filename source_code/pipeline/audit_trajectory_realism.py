"""Fail-closed realism audit for JCIIOT trajectory JSON files.

Checks observable state continuity (base and every material object), recorded
collision flags, and reconstructed gripper/object contact on every held frame.
No trajectory data is edited by this tool.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1]
for _path in (
    APP_DIR / "src",
    APP_DIR,
    APP_DIR / "robomimic",
    APP_DIR / "robosuite" / "robosuite",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def _xyz(values) -> np.ndarray:
    return np.asarray(values[:3], dtype=float)


def _quat_angle(q0, q1) -> float:
    """Shortest orientation distance between two xyzw or wxyz quaternions."""
    a = np.asarray(q0, dtype=float)
    b = np.asarray(q1, dtype=float)
    if a.size != 4 or b.size != 4:
        return 0.0
    a_norm = float(np.linalg.norm(a))
    b_norm = float(np.linalg.norm(b))
    if a_norm < 1e-9 or b_norm < 1e-9:
        return 0.0
    dot = float(np.clip(abs(np.dot(a / a_norm, b / b_norm)), 0.0, 1.0))
    return 2.0 * math.acos(dot)


def _transition_metrics(frames: list[dict]) -> dict:
    base_steps: list[tuple[float, int]] = []
    base_turns: list[tuple[float, int]] = []
    joint_steps: list[tuple[float, int, str]] = []
    object_steps: list[tuple[float, int, str, bool]] = []
    object_turns: list[tuple[float, int, str, bool]] = []
    for index in range(1, len(frames)):
        before, after = frames[index - 1], frames[index]
        base0 = before.get("base_pose", {})
        base1 = after.get("base_pose", {})
        p0 = _xyz(base0.get("position", [0.0, 0.0, 0.0]))
        p1 = _xyz(base1.get("position", [0.0, 0.0, 0.0]))
        base_steps.append((float(np.linalg.norm(p1[:2] - p0[:2])), index))
        base_turns.append(
            (
                _quat_angle(
                    base0.get("orientation_xyzw", []),
                    base1.get("orientation_xyzw", []),
                ),
                index,
            )
        )

        joints0 = before.get("joint_positions", {})
        joints1 = after.get("joint_positions", {})
        for name in joints0.keys() & joints1.keys():
            joint_steps.append((abs(float(joints1[name]) - float(joints0[name])), index, name))

        objects0 = before.get("object_positions", {})
        objects1 = after.get("object_positions", {})
        held = {before.get("held_object"), after.get("held_object")}
        for name in objects0.keys() & objects1.keys():
            displacement = float(np.linalg.norm(_xyz(objects1[name]) - _xyz(objects0[name])))
            object_steps.append((displacement, index, name, name in held))
            object_turns.append(
                (
                    _quat_angle(objects0[name][3:7], objects1[name][3:7]),
                    index,
                    name,
                    name in held,
                )
            )

    base_steps.sort(reverse=True)
    base_turns.sort(reverse=True)
    joint_steps.sort(reverse=True)
    object_steps.sort(reverse=True)
    object_turns.sort(reverse=True)
    return {
        "max_base_step_m": base_steps[0][0] if base_steps else 0.0,
        "max_base_step_frame": base_steps[0][1] if base_steps else None,
        "max_base_turn_rad": base_turns[0][0] if base_turns else 0.0,
        "max_base_turn_frame": base_turns[0][1] if base_turns else None,
        "max_joint_step": joint_steps[0][0] if joint_steps else 0.0,
        "max_joint_step_frame": joint_steps[0][1] if joint_steps else None,
        "max_joint_step_name": joint_steps[0][2] if joint_steps else None,
        "max_object_step_m": object_steps[0][0] if object_steps else 0.0,
        "max_object_step_frame": object_steps[0][1] if object_steps else None,
        "max_object_step_name": object_steps[0][2] if object_steps else None,
        "max_object_turn_rad": object_turns[0][0] if object_turns else 0.0,
        "max_object_turn_frame": object_turns[0][1] if object_turns else None,
        "max_object_turn_name": object_turns[0][2] if object_turns else None,
        "largest_object_steps": [
            {
                "step_m": round(step, 6),
                "frame": index,
                "object": name,
                "held_transition": held,
            }
            for step, index, name, held in object_steps[:10]
        ],
    }


def _contact_metrics(data: dict) -> dict:
    from robot_agent.environments import RobosuiteBackend
    from robot_agent.environments.robosuite_backend import (
        _invalidate_base_xy_qpos_mapping,
        _robot_geom_names,
        _set_base_world_yaw_direct,
        _set_base_xy_direct,
    )

    frames = data["frames"]
    held_indexes = [i for i, frame in enumerate(frames) if frame.get("held_object")]
    if not held_indexes:
        return {
            "held_frames": 0,
            "contact_frames": 0,
            "contact_fraction": 0.0,
            "missing_contact_frames": [],
            "unintended_contact_frames": [],
            "unintended_contact_pairs": [],
        }

    backend = RobosuiteBackend(
        env_name=data["robot_model"],
        camera="birdview",
        headless=True,
        drive_mode="direct",
    )
    backend.reset()
    env = backend.env
    robot = env.robots[0]

    xy_joints = {"mobilebase0_joint_mobile_forward", "mobilebase0_joint_mobile_side"}
    joint_addrs: dict[str, int] = {}
    for name in data.get("joint_names", []):
        if name in xy_joints or name == "mobilebase0_joint_mobile_yaw":
            continue
        try:
            addr = env.sim.model.get_joint_qpos_addr(name)
            if not isinstance(addr, tuple):
                joint_addrs[name] = int(addr)
        except Exception:
            pass

    object_addrs: dict[str, tuple[int, int]] = {}
    for name in data.get("object_names", []):
        candidates = [data.get("object_joints", {}).get(name), name, f"{name}_free", f"{name}_joint0"]
        for joint in candidates:
            if not joint:
                continue
            try:
                addr = env.sim.model.get_joint_qpos_addr(joint)
                if isinstance(addr, tuple):
                    object_addrs[name] = (int(addr[0]), int(addr[1]))
                    break
            except Exception:
                pass

    contact_frames = 0
    missing: list[int] = []
    unintended: list[int] = []
    unintended_pairs: list[dict] = []
    per_object: dict[str, dict[str, int]] = {}
    robot_geoms = _robot_geom_names(env, robot)
    material_names = sorted(object_addrs, key=len, reverse=True)

    def _material_owner(geom: str) -> str | None:
        for material_name in material_names:
            if geom == material_name or geom.startswith(f"{material_name}_"):
                return material_name
        return None

    try:
        for index in held_indexes:
            frame = frames[index]
            held = str(frame["held_object"])
            bp = frame.get("base_pose", {})
            jp = frame.get("joint_positions", {})
            ori = bp.get("orientation_xyzw", [])
            if len(ori) >= 4:
                yaw = 2.0 * math.atan2(float(ori[2]), float(ori[3]))
                _set_base_world_yaw_direct(env, robot, yaw)
                _invalidate_base_xy_qpos_mapping(env)
            pos = bp.get("position", [])
            if len(pos) >= 2:
                _set_base_xy_direct(env, robot, np.asarray(pos[:2], dtype=float))
            for name, addr in joint_addrs.items():
                if name in jp:
                    env.sim.data.qpos[addr] = float(jp[name])
            for name, (start, end) in object_addrs.items():
                values = frame.get("object_positions", {}).get(name)
                if values is not None:
                    env.sim.data.qpos[start:end] = np.asarray(values, dtype=float)
            env.sim.forward()

            has_contact = False
            bad_pair: tuple[str, str] | None = None
            for contact_index in range(int(env.sim.data.ncon)):
                contact = env.sim.data.contact[contact_index]
                geom1 = env.sim.model.geom_id2name(int(contact.geom1)) or ""
                geom2 = env.sim.model.geom_id2name(int(contact.geom2)) or ""
                owner1 = _material_owner(geom1)
                owner2 = _material_owner(geom2)
                robot1 = geom1 in robot_geoms
                robot2 = geom2 in robot_geoms
                gripper1 = geom1.startswith("gripper0_")
                gripper2 = geom2.startswith("gripper0_")
                object1 = geom1 == held or geom1.startswith(f"{held}_")
                object2 = geom2 == held or geom2.startswith(f"{held}_")
                if (gripper1 and object2) or (gripper2 and object1):
                    has_contact = True
                if robot1 and owner2 is not None and owner2 != held:
                    bad_pair = (geom1, geom2)
                elif robot2 and owner1 is not None and owner1 != held:
                    bad_pair = (geom1, geom2)
                elif owner1 is not None and owner2 is not None and owner1 != owner2:
                    if held in {owner1, owner2}:
                        bad_pair = (geom1, geom2)

            stats = per_object.setdefault(held, {"held_frames": 0, "contact_frames": 0})
            stats["held_frames"] += 1
            if has_contact:
                contact_frames += 1
                stats["contact_frames"] += 1
            else:
                missing.append(index)
            if bad_pair is not None:
                unintended.append(index)
                if len(unintended_pairs) < 20:
                    unintended_pairs.append(
                        {"frame": index, "geom1": bad_pair[0], "geom2": bad_pair[1]}
                    )
    finally:
        backend.close()

    for stats in per_object.values():
        stats["contact_fraction"] = round(
            stats["contact_frames"] / max(1, stats["held_frames"]), 6
        )
    return {
        "held_frames": len(held_indexes),
        "contact_frames": contact_frames,
        "contact_fraction": round(contact_frames / len(held_indexes), 6),
        "missing_contact_frames": missing[:50],
        "unintended_contact_frames": unintended[:50],
        "unintended_contact_pairs": unintended_pairs,
        "per_object": per_object,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-base-step", type=float, default=0.06)
    parser.add_argument("--max-base-turn", type=float, default=0.08)
    parser.add_argument("--max-joint-step", type=float, default=0.35)
    parser.add_argument("--max-object-step", type=float, default=0.10)
    parser.add_argument("--max-object-turn", type=float, default=0.25)
    parser.add_argument("--min-held-contact", type=float, default=0.99)
    parser.add_argument("--skip-contact", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.trajectory.read_text(encoding="utf-8"))
    frames = data.get("frames", [])
    transition = _transition_metrics(frames)
    collision_indexes = [i for i, frame in enumerate(frames) if frame.get("has_collision")]
    contact = None if args.skip_contact else _contact_metrics(data)

    failures: list[str] = []
    if not frames:
        failures.append("trajectory contains no frames")
    if transition["max_base_step_m"] > args.max_base_step:
        failures.append("base step exceeds limit")
    if transition["max_base_turn_rad"] > args.max_base_turn:
        failures.append("base angular step exceeds limit")
    if transition["max_joint_step"] > args.max_joint_step:
        failures.append("robot joint step exceeds limit")
    if transition["max_object_step_m"] > args.max_object_step:
        failures.append("object displacement exceeds continuity limit")
    if transition["max_object_turn_rad"] > args.max_object_turn:
        failures.append("object angular step exceeds continuity limit")
    if collision_indexes:
        failures.append("trajectory contains recorded collisions")
    if contact is not None and contact["contact_fraction"] < args.min_held_contact:
        failures.append("held object lacks sustained gripper contact")
    if contact is not None and contact["unintended_contact_frames"]:
        failures.append("transport contacts an unheld material object")

    report = {
        "trajectory": str(args.trajectory.resolve()),
        "frames": len(frames),
        "limits": {
            "max_base_step_m": args.max_base_step,
            "max_base_turn_rad": args.max_base_turn,
            "max_joint_step": args.max_joint_step,
            "max_object_step_m": args.max_object_step,
            "max_object_turn_rad": args.max_object_turn,
            "min_held_contact_fraction": args.min_held_contact,
        },
        "transition": transition,
        "recorded_collision_frames": collision_indexes[:50],
        "contact": contact,
        "pass": not failures,
        "failures": failures,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
