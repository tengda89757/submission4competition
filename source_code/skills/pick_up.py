"""Pick-up skill — grasp and lift a target object via backend."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np

from robot_agent.core.scene_context import SceneContext
from robot_agent.core.types import ExecutionContext, SkillResult
from robot_agent.skills.base import BaseSkill
from robot_agent.skills.scripted_grasp import (
    compute_rotated_base_pose,
    install_scripted_grasp_fallback,
    resolve_unmoved_override,
)

logger = logging.getLogger(__name__)

# Chinese-number → digit
_CN_DIGIT: dict[str, str] = {
    "一": "1", "二": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8",
    "九": "9", "十": "10",
}
# Chinese role → role prefix
_CN_ROLE: dict[str, str] = {
    "进料": "input", "输入": "input", "入料": "input",
    "出料": "output", "输出": "output",
}
# Digit-word → index
_CN_INDEX: dict[str, str] = {
    "1": "1", "2": "2", "3": "3", "4": "4",
    "一": "1", "二": "2", "三": "3", "四": "4",
}
# Station kind keywords to strip from target
_CN_KIND: list[str] = ["传送带", "架子", "桌子", "箱子", "料箱", "料斗",
                        "conveyor", "shelf", "table", "bin"]


def _config_grasp_pose(target: str) -> dict | None:
    """Calibrated grasp base pose for a station from knowledge/task_config.json.

    Poses are (re)calibrated per scene by pipeline/patch_grasp_pose.py using the
    object's own grasp-site geometry. Without this, the backend falls back to the
    nav approach pose, which does not match the BC policy's trained geometry
    outside the L1 layout (verified L2 grasp failure at the nav pose).
    """
    try:
        cfg_path = Path(__file__).resolve().parents[3] / "knowledge" / "task_config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        entry = cfg.get("grasp_poses", {}).get(target)
        if entry:
            return {
                "robot_base_pos": [float(entry["pos"][0]), float(entry["pos"][1]), 0.0],
                "robot_base_ori": [0.0, 0.0, float(entry["yaw"])],
            }
    except Exception:
        logger.exception("failed to load calibrated grasp pose for %s", target)
    return None


def _resolve_station_name(target: str, scene: SceneContext) -> str:
    """Resolve a natural-language target to a known station name.

    Examples of what this handles:
        "在1号进料口抓取目标物体" → "input_1"
        "把物品放到3号出料口"     → "output_3"
        "input_1"                  (pass-through — exact match)
    """
    known = scene.all_port_names()
    if not known:
        return target

    # 0) exact match
    if target in known:
        return target

    # 1) known name is a substring of target
    for name in known:
        if name in target:
            return name

    # 2) match by (role, index) — e.g. "1号进料口" → input station #1
    role, idx = _parse_role_index(target)
    if role and idx is not None:
        desired_idx = int(idx)
        for name in known:
            info = (scene.input_ports.get(name) or
                    scene.output_ports.get(name))
            if info is None:
                continue
            if info.role == role and info.index == desired_idx:
                return name

    return target


def _parse_role_index(text: str) -> tuple[str | None, int | None]:
    """Extract (role, index) from Chinese text like "1号进料口" → ("input", 1)."""
    # Normalise Chinese digits → Arabic
    s = text
    for cn, d in _CN_DIGIT.items():
        s = s.replace(cn, d)

    # Find a digit followed by optional characters then a role word
    m = re.search(r"(\d+)\s*[号#]?\s*([进出入输][料料入出])", s)
    if m:
        digit = m.group(1)
        role_cn = m.group(2)
        for cn_word, role_prefix in _CN_ROLE.items():
            if cn_word in role_cn:
                return role_prefix, int(digit)

    # Also try "input_N" / "output_N" pattern directly
    m = re.search(r"(input|output)\s*_?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1).lower(), int(m.group(2))

    return None, None


class PickUpSkill(BaseSkill):
    """Grasp a target object through the environment backend.

    Resolves natural-language target descriptions to known station names
    via ``SceneContext``, falling back to substring matching.
    """

    def __init__(self, *, backend, scene_context: SceneContext | None = None,
                 grid=None, path_spacing: float = 0.35) -> None:
        super().__init__(
            name="pick_up",
            description="Grasp or pick up an object",
            keywords=(
                "pick", "grasp", "grab", "lift",
                "grasp", "pick", "grab", "take", "lift", "collect",
            ),
        )
        self._backend = backend
        self._scene = scene_context
        self._grid = grid
        self._path_spacing = path_spacing
        self._place_seq = 0  # per-task drop counter (multi-object lateral spread)
        # BC-150 is overfit to L1; the scripted expert approach succeeds where BC
        # fails (validated 20/20 in L3/L4). Installed as a fallback at skill
        # construction (robosuite is fully loaded by now): BC runs first, so the
        # proven L1 path is untouched. See skills/scripted_grasp.py for modes.
        try:
            install_scripted_grasp_fallback()
        except Exception:
            logger.exception("scripted grasp fallback installation failed")

    def run(self, context: ExecutionContext) -> SkillResult:
        inputs: dict = context.metadata.get("inputs", {})
        raw_target: str = (
            inputs.get("target")
            or context.task
        )
        object_name = (
            inputs.get("object_name")
            or inputs.get("obj_name")
            or inputs.get("object")
            or inputs.get("target_object")
        )
        object_name = str(object_name).strip() if object_name else None
        _known_objects = list(getattr(getattr(self._backend, "env", None), "material_objects", []) or [])
        if object_name and _known_objects and object_name not in _known_objects:
            # The plan sometimes passes a NATURAL-LANGUAGE object ("white-rimmed
            # storage bin") — truthy, so it used to skip the fallbacks below, and
            # the rotated-approach pose could not be computed (verified L5 run 3:
            # pick 2 spawned at the previous tote's pose). Substring-match it to a
            # scene object, else discard and re-resolve.
            matched = next((n for n in _known_objects if object_name in n or n in object_name), None)
            logger.info("pick_up: inputs object %r not a scene object; matched=%r", object_name, matched)
            object_name = matched
        # Parse text fallback only fires when object_name is still empty after all above logic.
        # The LLM plan sometimes omits inputs.object_name even when the step
        # text names the object verbatim ("pick up white_tote_b01_left_front
        # at input_1"). Without it the rotated-approach pose can't be applied
        # and the wrapped env spawns at the config pose of a DIFFERENT tote
        # (verified L5 pick 2: base at center's pose, front unreachable).
        if not object_name or object_name not in _known_objects:
            # The LLM plan sometimes omits inputs.object_name even when the step
            # text names the object verbatim ("pick up white_tote_b01_left_front
            # at input_1"). Without it the rotated-approach pose can't be applied
            # and the wrapped env spawns at the config pose of a DIFFERENT tote
            # (verified L5 pick 2: base at center's pose, front unreachable).
            # Only trust the parse when it is UNAMBIGUOUS — the L5 full-task text
            # names all three totes; ambiguity is deferred to backend resolution.
            pass
        elif object_name not in _known_objects:
            # Plan gave an object name that's NOT on the scene (L5: right_group instead
            # of left_group). Discard it and force backend resolution which respects
            # the material_metadata spawn map.
            logger.debug("pick_up: discarding plan object %r (not in scene)", object_name)
            object_name = None
        if not object_name:
            # Only trust the parse when it is UNAMBIGUOUS — the L5 full-task text
            # names all three totes; ambiguity is deferred to backend resolution.
            _search_text = f"{raw_target} {context.task or ''}"
            _hits = [n for n in _known_objects if n and n in _search_text]
            if len(_hits) == 1:
                object_name = _hits[0]
                logger.info("pick_up: parsed object_name %r from step text", object_name)
            else:
                logger.debug("pick_up: no unique match for object in %r -> let backend resolve", _search_text)
        initial_base_pose = inputs.get("grasp_initial_base_pose")
        if initial_base_pose is None:
            initial_base_pose = inputs.get("initial_base_pose")
        if initial_base_pose is None:
            initial_base_pose = inputs.get("base_pose")
        target = raw_target
        if self._scene is not None:
            target = _resolve_station_name(raw_target, self._scene)
            logger.info("pick_up target: %r → %r", raw_target, target)
        # Validate object name: it must be in the scene's material_objects.
        # If plan gave an invalid name (right-center), force backend resolution.
        if object_name and _known_objects and object_name not in _known_objects:
            logger.warning("pick_up: discarding invalid object %r from plan", object_name)
            object_name = None
        elif object_name:
            logger.debug("pick_up: accepted plan object %r for %s", object_name, target)
        else:
            logger.debug("pick_up: object_name empty, will resolve from backend", target)
        if not object_name and hasattr(self._backend, "_resolve_grasp_object_name"):
            # Deterministic last resort: ask the backend which object it WILL
            # grasp at this source, so the rotated-approach pose targets the
            # same tote the grasp env will.
            try:
                object_name = self._backend._resolve_grasp_object_name(target, object_name=None)
                logger.info("pick_up: backend resolved object_name %r for %s", object_name, target)
            except Exception:
                logger.exception("pick_up: backend object resolution failed")
                object_name = None

        # The agent pipeline passes the nav approach pose as grasp_initial_base_pose,
        # but the BC policy must start from its trained relative geometry. Prefer the
        # calibrated pose (pipeline/patch_grasp_pose.py) whenever one exists — for L1
        # they coincide, so this is regression-free.
        calibrated = _config_grasp_pose(target)
        # Rotated-approach objects (L2/L5): the pose must be computed PER OBJECT
        # from live geometry — the config pose is keyed by source port and cannot
        # distinguish the three L5 totes (and its yaw predates the rotation).
        if object_name:
            rotated = compute_rotated_base_pose(getattr(self._backend, "env", None), object_name)
            if rotated is not None:
                logger.info("pick_up: rotated-approach pose for %s: %s", object_name, rotated)
                print(f"[PICK_UP] rotated grasp pose for {object_name}: "
                      f"{[round(v,3) for v in rotated['robot_base_pos'][:2]]} "
                      f"yaw={rotated['robot_base_ori'][2]:.3f}", flush=True)
                calibrated = rotated
        if calibrated is not None:
            if initial_base_pose is not None:
                logger.info("pick_up: overriding supplied base pose %s with calibrated %s",
                            initial_base_pose, calibrated)
            initial_base_pose = calibrated
            # CRITICAL: drive the NAV env base to the calibrated pose too. The grasp
            # happens in a separate wrapped env at the calibrated pose; the transport
            # attachment then holds the object at (object - nav_base) offset. If the
            # nav base stays at the port approach point, that offset is metres wrong
            # (verified L3: object swept a 19 m arc during the turn and landed on the
            # floor at (22.6,-12.1)). For L1 the poses coincide, so no regression.
            self._drive_nav_base_to(calibrated["robot_base_pos"][:2])

        # Physics grasp (only mode — no teleport fallback)
        if hasattr(self._backend, "grasp_object_physics"):
            try:
                # The wrapped grasp env resets ALL objects to their spawn poses and
                # the backend then syncs every material object back into the nav
                # env — which would teleport previously PLACED objects (L5 totes
                # 1 and 2) back to the source. Snapshot non-target objects now and
                # restore them after the grasp.
                snapshot = self._snapshot_other_objects(object_name)
                ok = self._backend.grasp_object_physics(
                    target,
                    object_name=object_name,
                    initial_base_pose=initial_base_pose,
                )
                self._restore_other_objects(snapshot, object_name)
                if ok:
                    self._normalize_transport_offset()
                resolved_object = getattr(self._backend, "_held_crate_name", None) or object_name
                return SkillResult(
                    skill_name=self.name,
                    success=ok,
                    message=f"Physics grasp {'OK' if ok else 'FAIL'}: {target}",
                    payload={
                        "action": "pick_up",
                        "target": target,
                        "object_name": resolved_object,
                        "grasp_initial_base_pose": initial_base_pose,
                        "method": "physics",
                        "ok": ok,
                    },
                )
            except Exception as exc:
                logger.exception("physics grasp crashed")
                return SkillResult(
                    skill_name=self.name, success=False,
                    message=f"Physics grasp error: {exc}",
                    payload={
                        "action": "pick_up",
                        "target": target,
                        "object_name": object_name,
                        "grasp_initial_base_pose": initial_base_pose,
                        "error": str(exc),
                    },
                )

        # No physics configured — teleport only
        try:
            self._backend.pick_object(target)
        except Exception:
            pass
        return SkillResult(
            skill_name=self.name, success=True,
            message=f"Grasped (snap): {target}",
            payload={"action": "pick_up", "target": target, "raw_target": raw_target, "method": "teleport"},
        )

    def _snapshot_other_objects(self, target_object: str | None) -> dict:
        """Free-joint qpos of every material object EXCEPT the grasp target."""
        out: dict = {}
        try:
            env = getattr(self._backend, "env", None)
            if env is None:
                return out
            for name in getattr(env, "material_objects", []):
                if target_object and (name == target_object):
                    continue
                for suffix in ("_free", "_joint0"):
                    try:
                        out[f"{name}{suffix}"] = np.array(
                            env.sim.data.get_joint_qpos(f"{name}{suffix}"), dtype=float)
                        break
                    except Exception:
                        continue
        except Exception:
            logger.exception("pick_up: object snapshot failed")
        return out

    def _restore_other_objects(self, snapshot: dict, target_object: str | None) -> None:
        """Undo the backend's blanket wrapped→nav object sync for non-targets."""
        if not snapshot:
            return
        try:
            env = getattr(self._backend, "env", None)
            if env is None:
                return
            changed = 0
            for joint, qpos in snapshot.items():
                try:
                    cur = np.array(env.sim.data.get_joint_qpos(joint), dtype=float)
                    # Restore unconditionally: the wrapped grasp env respawns and can
                    # NUDGE neighbours (verified L5: front tote rotated ~8 deg with
                    # <1 cm translation, which skewed the next rotated grasp pose by
                    # 0.23 m). Snapshot equals pre-grasp truth for every non-target.
                    if float(np.max(np.abs(cur - qpos))) > 1e-9:
                        env.sim.data.set_joint_qpos(joint, qpos)
                        changed += 1
                except Exception:
                    continue
            if changed:
                env.sim.forward()
                print(f"[PICK_UP] restored {changed} non-target object pose(s) after grasp sync",
                      flush=True)
        except Exception:
            logger.exception("pick_up: object restore failed")

    def _normalize_transport_offset(self) -> None:
        """Clamp the transport-attachment hold offset to straight-ahead 0.94 m.

        The attachment captures (object - nav_base) in the base frame at attach
        time. When the nav base isn't exactly at the calibrated grasp pose, that
        offset points sideways (verified L3: [0.245, -1.04]), so at the output
        station the object hangs off the table edge and drops to the floor. The
        L1-trained hold geometry is 0.94 m straight ahead — normalizing to that
        makes place_down release the object right over the station center.

        Multi-object tasks (L5) additionally spread successive drops laterally:
        releasing every tote at the same spot chain-pushes the earlier ones off
        the 0.80 m scoring radius (verified: first tote ended 0.92 m out). The
        first drop stays at 0.0 so single-object levels are untouched.
        """
        try:
            from robosuite.environments.factory_sorting.transport_attachment import (
                TRANSPORT_ATTACHMENT_ATTR,
            )
            raw = getattr(self._backend, "env", None) or getattr(self._backend, "_env", None)
            attachment = getattr(raw, TRANSPORT_ATTACHMENT_ATTR, None) if raw is not None else None
            if not attachment or not attachment.get("active", False):
                return
            lateral = (0.0, 0.38, -0.38)[self._place_seq % 3]
            self._place_seq += 1
            rel = np.asarray(attachment["relative_xy"], dtype=float)
            dist = float(np.linalg.norm(rel))
            normalized = np.array([0.941, lateral], dtype=float)
            if np.linalg.norm(rel - normalized) < 0.05:
                return
            attachment["relative_xy"] = normalized
            logger.info("pick_up: normalized transport offset %s (|%.3f|) -> %s",
                        np.round(rel, 3).tolist(), dist, normalized.tolist())
            print(f"[PICK_UP] transport offset normalized {np.round(rel,3).tolist()} -> [0.941, 0.0]",
                  flush=True)
        except Exception:
            logger.exception("pick_up: transport offset normalization failed")

    def _drive_nav_base_to(self, goal_xy) -> None:
        """Best-effort A* drive of the nav base to the calibrated grasp pose."""
        try:
            cur_xy, _ = self._backend.get_base_pose()
            goal = np.asarray(goal_xy, dtype=float)
            dist = float(np.linalg.norm(np.asarray(cur_xy, dtype=float) - goal))
            if dist <= 0.5:
                return
            if self._grid is None or self._scene is None:
                logger.warning("pick_up: nav base %.2fm from grasp pose but no grid — skipping pre-drive", dist)
                return
            from robot_agent.core.map_loader import plan_world_path
            scene_dict = {"bounds": self._scene.bounds, "resolution": self._scene.resolution}
            path = plan_world_path(scene_dict, self._grid, np.asarray(cur_xy, dtype=float), goal,
                                   min_spacing=self._path_spacing)
            if not path:
                logger.warning("pick_up: A* to grasp pose failed (%.2fm away)", dist)
                return
            reached = self._backend.follow_path(path)
            logger.info("pick_up: pre-drove nav base %.2fm to grasp pose, reached=%s", dist, reached)
        except Exception:
            logger.exception("pick_up: pre-drive to grasp pose failed")
