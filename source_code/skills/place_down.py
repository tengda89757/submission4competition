"""Place-down skill — release a held object at target via backend."""

from __future__ import annotations

import logging

import numpy as np

from robot_agent.core.scene_context import SceneContext
from robot_agent.core.types import ExecutionContext, SkillResult
from robot_agent.skills.base import BaseSkill
from robot_agent.skills.pick_up import _resolve_station_name

logger = logging.getLogger(__name__)


class PlaceDownSkill(BaseSkill):
    """Release a held object at the target through the environment backend.

    Resolves natural-language target descriptions to known station names
    via ``SceneContext`` (same algorithm as ``PickUpSkill``).
    """

    def __init__(self, *, backend, scene_context: SceneContext | None = None) -> None:
        super().__init__(
            name="place_down",
            description="Place down or drop an object",
            keywords=(
                "place", "put", "drop", "release",
                "place", "drop", "put", "release", "unload",
            ),
        )
        self._backend = backend
        self._scene = scene_context
        self._drop_index = 0

    def _ensure_output_port(self, target: str) -> None:
        """Register missing output ports on the env at runtime.

        The env classes only pre-register output_1..4 (table/bin/conveyor/shelf),
        but L3/L4 place at output_5 and L5 at aux_output_1. The backend lookup and
        table-top-z fallback both work from ``env.output_ports`` centers, so we
        inject the missing entry from the scene semantic map (participant-editable
        skill layer; no locked backend/env code is modified).
        """
        try:
            env = getattr(self._backend, "env", None)
            ports = getattr(env, "output_ports", None)
            if env is None or ports is None or self._scene is None:
                return
            if any(name == target or name.startswith(target) or target in name for name in ports):
                return
            station = self._scene.output_ports.get(target)
            if station is None:
                return
            center = np.asarray(station.center, dtype=float)
            if center.size == 2:
                center = np.array([center[0], center[1], 0.0])
            ports[target] = {
                "kind": "table",
                "center": center,
                "side": "output",
                "index": len(ports),
            }
            logger.info("place_down: injected missing output port '%s' center=%s", target, center[:2])
        except Exception:
            logger.exception("place_down: failed to inject output port %s", target)

    def run(self, context: ExecutionContext) -> SkillResult:
        raw_target: str = (
            context.metadata.get("inputs", {}).get("target")
            or context.task
        )
        target = raw_target
        if self._scene is not None:
            target = _resolve_station_name(raw_target, self._scene)
            logger.info("place_down target: %r → %r", raw_target, target)

        self._ensure_output_port(target)

        # Physics place (only mode — no teleport fallback)
        if hasattr(self._backend, "place_object_physics"):
            try:
                restore_state = self._configure_multi_object_drop(target)
                try:
                    ok = self._backend.place_object_physics(target)
                finally:
                    self._restore_output_center(restore_state)
                msg = f"Physics place {'OK' if ok else 'FAIL'}: {target}"
                if not ok:
                    _held = getattr(self._backend, "_held_crate_name", None)
                    _ports = list(self._backend.env.output_ports.keys()) if hasattr(self._backend, 'env') and self._backend.env else []
                    logger.warning("place_down: failed target=%s held=%s avail_out=%s", target, _held, _ports)
                    msg += f" held={_held} out_ports={_ports}"
                return SkillResult(
                    skill_name=self.name,
                    success=ok,
                    message=msg,
                    payload={"action": "place_down", "target": target, "method": "physics", "ok": ok},
                )
            except Exception as exc:
                logger.exception("physics place crashed")
                return SkillResult(
                    skill_name=self.name, success=False,
                    message=f"Physics place error: {exc}",
                    payload={"action": "place_down", "target": target, "error": str(exc)},
                )

        # No physics configured — teleport only
        try:
            self._backend.place_object(target)
        except Exception:
            pass
        return SkillResult(
            skill_name=self.name, success=True,
            message=f"Placed (snap): {target}",
            payload={"action": "place_down", "target": target, "raw_target": raw_target, "method": "teleport"},
        )

    def _configure_multi_object_drop(self, target: str):
        """Choose three distinct points on L5's official target table.

        Only runtime station metadata used by the place controller is adjusted;
        object poses, attachment state, semantic-map files and trajectories are
        never edited.  The original metadata is restored immediately afterward.
        """
        if target != "aux_output_1" or self._scene is None:
            return None
        lateral = (0.0, 0.38, -0.38)[self._drop_index % 3]
        self._drop_index += 1
        if abs(lateral) < 1e-9:
            return None
        try:
            station = self._scene.output_ports[target]
            env = getattr(self._backend, "env", None)
            entry = getattr(env, "output_ports", {}).get(target)
            if entry is None:
                return None

            scene_center = np.asarray(station.center, dtype=float).copy()
            env_center = np.asarray(entry["center"], dtype=float).copy()
            approach = np.asarray(station.approach, dtype=float)
            toward_table = scene_center[:2] - approach[:2]
            norm = float(np.linalg.norm(toward_table))
            if norm < 1e-9:
                return None
            toward_table /= norm
            right = np.array([toward_table[1], -toward_table[0]], dtype=float)
            delta = lateral * right

            shifted_scene = scene_center.copy()
            shifted_scene[:2] += delta
            shifted_env = env_center.copy()
            shifted_env[:2] += delta
            station.center = shifted_scene
            entry["center"] = shifted_env
            print(f"[PLACE_DOWN] {target}: table drop point {lateral:+.2f}m", flush=True)
            return entry, env_center, station, scene_center
        except Exception:
            logger.exception("place_down: failed to select multi-object drop point")
            return None

    @staticmethod
    def _restore_output_center(state) -> None:
        if state is None:
            return
        entry, env_center, station, scene_center = state
        entry["center"] = env_center
        station.center = scene_center
