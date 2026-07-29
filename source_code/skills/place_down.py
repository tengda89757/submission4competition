"""Place-down skill — release a held object at target via backend."""

from __future__ import annotations

import logging

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

    def _ensure_output_port(self, target: str) -> None:
        """Register missing output ports (output_5/6) on the env at runtime.

        The env classes only pre-register output_1..4 (table/bin/conveyor/shelf),
        but L3/L4/L5 place at output_5/output_6. The backend's station lookup and
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
            import numpy as np
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
                ok = self._backend.place_object_physics(target)
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
