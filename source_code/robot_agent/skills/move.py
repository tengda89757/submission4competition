"""Move skill — navigate the robot base to a target via A* + backend."""

from __future__ import annotations

import logging
import re

import numpy as np

from robot_agent.core.types import ExecutionContext, SkillResult
from robot_agent.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class MoveSkill(BaseSkill):
    """Navigate the mobile base to a named station or world coordinate.

    Requires a backend, scene context, and occupancy grid — no mock fallback.
    """

    def __init__(
        self,
        *,
        backend,
        scene_context,
        grid: np.ndarray,
        path_spacing: float = 0.35,
    ) -> None:
        super().__init__(
            name="move",
            description="Move to a specified location",
            keywords=(
                "move", "go", "navigate",
                "move", "go", "navigate", "travel", "drive", "approach",
            ),
        )
        self._backend = backend
        self._scene = scene_context
        self._grid = grid
        self._path_spacing = path_spacing
        self._station_visits: dict[str, int] = {}

    # ── public API ──────────────────────────────────────────

    def run(self, context: ExecutionContext) -> SkillResult:
        target: str = (
            context.metadata.get("inputs", {}).get("target")
            or context.task
        )

        goal_xy = self._resolve_target(target)
        if goal_xy is None:
            return SkillResult(
                skill_name=self.name,
                success=False,
                message=f"Cannot resolve target location: {target}",
                payload={"action": "move", "target": target},
            )

        start_xy, start_yaw = self._backend.get_base_pose()
        initial_path = self._plan(start_xy, goal_xy)
        if initial_path is None:
            return SkillResult(
                skill_name=self.name,
                success=False,
                message=f"A* planning failed: {target}",
                payload={"action": "move", "target": target, "start": start_xy.tolist()},
            )
        departure_plan = self._transport_departure_plan(
            start_xy, goal_xy, route_hint=initial_path
        )
        if departure_plan is None:
            return SkillResult(
                skill_name=self.name,
                success=False,
                message=f"Could not construct a safe source-station departure: {target}",
                payload={
                    "action": "move",
                    "target": target,
                    "failure_reason": "invalid transport departure geometry",
                },
            )
        departure_path, departure_yaw = departure_plan
        planning_start = start_xy
        if departure_yaw is not None:
            if not self._payload_turn_is_clear(float(departure_yaw)):
                return SkillResult(
                    skill_name=self.name,
                    success=False,
                    message=f"Payload sweep is not clear for source departure: {target}",
                    payload={
                        "action": "move",
                        "target": target,
                        "failure_reason": "transport departure payload sweep blocked",
                    },
                )
            marker = getattr(self._backend, "_mark_trajectory_event", None)
            if callable(marker):
                marker(
                    "transport_departure_turn_start",
                    object_name=getattr(self._backend, "_held_crate_name", None),
                    target_yaw=float(departure_yaw),
                )
            turn = getattr(self._backend, "turn_base_to_yaw_physics", None)
            if not callable(turn) or not turn(float(departure_yaw)):
                return SkillResult(
                    skill_name=self.name,
                    success=False,
                    message=f"Could not align the payload for safe departure: {target}",
                    payload={
                        "action": "move",
                        "target": target,
                        "failure_reason": "transport departure turn failed",
                    },
                )
            if callable(marker):
                marker(
                    "transport_departure_turn_end",
                    object_name=getattr(self._backend, "_held_crate_name", None),
                )
        elif departure_path:
            marker = getattr(self._backend, "_mark_trajectory_event", None)
            if callable(marker):
                marker(
                    "transport_departure_start",
                    object_name=getattr(self._backend, "_held_crate_name", None),
                    retreat_xy=departure_path[0].tolist(),
                    lane_exit_xy=departure_path[-1].tolist(),
                )
            if not self._backend.follow_path(departure_path):
                return SkillResult(
                    skill_name=self.name,
                    success=False,
                    message=f"Could not clear the source station safely: {target}",
                    payload={
                        "action": "move",
                        "target": target,
                        "failure_reason": "transport departure failed",
                    },
                )
            planning_start, _ = self._backend.get_base_pose()
            if float(np.linalg.norm(planning_start - departure_path[-1])) > 0.06:
                return SkillResult(
                    skill_name=self.name,
                    success=False,
                    message=f"Source-station clearance was incomplete: {target}",
                    payload={
                        "action": "move",
                        "target": target,
                        "failure_reason": "transport departure pose mismatch",
                    },
                )
            if callable(marker):
                marker(
                    "transport_departure_end",
                    object_name=getattr(self._backend, "_held_crate_name", None),
                )

        path = self._plan(planning_start, goal_xy) if departure_path else initial_path
        if path is None:
            return SkillResult(
                skill_name=self.name,
                success=False,
                message=f"A* planning failed: {target}",
                payload={"action": "move", "target": target, "start": start_xy.tolist()},
            )

        reached = self._backend.follow_path(path)
        final_xy, final_yaw = self._backend.get_base_pose()
        return SkillResult(
            skill_name=self.name,
            success=reached,
            message=f"Moved to: {target}" if reached else f"Failed to reach: {target}",
            payload={
                "action": "move",
                "target": target,
                "goal_xy": goal_xy.tolist(),
                "start_base_pose": {
                    "xy": start_xy.tolist(),
                    "yaw": float(start_yaw),
                    "robot_base_pos": [float(start_xy[0]), float(start_xy[1]), 0.0],
                    "robot_base_ori": [0.0, 0.0, float(start_yaw)],
                },
                "final_base_pose": {
                    "xy": final_xy.tolist(),
                    "yaw": float(final_yaw),
                    "robot_base_pos": [float(final_xy[0]), float(final_xy[1]), 0.0],
                    "robot_base_ori": [0.0, 0.0, float(final_yaw)],
                },
                "waypoints": len(path) + len(departure_path),
                "transport_departure_waypoints": len(departure_path),
                "transport_departure_turn": departure_yaw is not None,
                "reached": reached,
            },
        )

    # ── internal ────────────────────────────────────────────

    def _resolve_target(self, target: str) -> np.ndarray | None:
        """Convert a target description to a (2,) world xy position.

        Resolution order:
        1. Known station name via ``SceneContext.approach_xy()``
        2. Direct (x, y) tuple in the target string
        """
        # 1) named station.  Resolve an exact name before accepting names
        # embedded in natural-language targets: ``output_1`` is otherwise a
        # substring of the official auxiliary port ``aux_output_1``.
        names = self._scene.all_port_names()
        exact = target.strip()
        if exact in names:
            return self._station_goal(exact)
        for name in sorted(names, key=len, reverse=True):
            if name in target:
                return self._station_goal(name)

        # 2) numeric "x, y"
        nums = re.findall(r"[-+]?\d*\.?\d+", target)
        if len(nums) >= 2:
            try:
                return np.array([float(nums[0]), float(nums[1])], dtype=float)
            except ValueError:
                pass

        return None

    def _station_goal(self, name: str) -> np.ndarray:
        """Return a physical approach goal, staggering L5's three drops."""
        goal = self._scene.approach_xy(name)
        if name != "aux_output_1":
            return goal

        visit = self._station_visits.get(name, 0)
        self._station_visits[name] = visit + 1
        # Tote width is about 0.60 m along this axis. A former +/-0.38 m
        # pattern overlapped adjacent drops and could catapult an earlier tote.
        lateral = (0.0, 0.65, -0.65)[visit % 3]
        station = self._scene.output_ports.get(name)
        if station is None or abs(lateral) < 1e-9:
            return goal
        toward_table = np.asarray(station.center[:2], dtype=float) - goal
        norm = float(np.linalg.norm(toward_table))
        if norm < 1e-9:
            return goal
        toward_table /= norm
        right = np.array([toward_table[1], -toward_table[0]], dtype=float)
        staggered = goal + lateral * right
        print(f"[MOVE] {name} visit {visit + 1}: lateral goal {lateral:+.2f}m", flush=True)
        return staggered

    def _transport_departure_plan(
        self,
        start_xy: np.ndarray,
        goal_xy: np.ndarray,
        *,
        route_hint: list[np.ndarray],
    ) -> tuple[list[np.ndarray], float | None] | None:
        """Return a safe translation path or a payload-alignment yaw.

        A direct route from a pick pose can run parallel to the source table
        while the carried object is still between the grippers and the table.
        First moving outward, then along the table in the direction selected by
        the global route, keeps the robot and payload clear of neighbouring
        source objects. Using the route direction matters when obstacles force
        A* to begin opposite the goal's straight-line bearing.
        """
        held = getattr(self._backend, "_held_crate_name", None)
        if not held:
            return [], None
        try:
            env = self._backend.env
            attachment = getattr(env, "_factory_sorting_transport_attachment", None)
            if not attachment or not attachment.get("active", False):
                logger.error("held object has no active transport constraint")
                return None
            body_id = env.obj_body_id[held]
            object_xy = np.asarray(env.sim.data.body_xpos[body_id][:2], dtype=float)
            outward = np.asarray(start_xy, dtype=float) - object_xy
            outward_norm = float(np.linalg.norm(outward))
            if not 0.25 <= outward_norm <= 1.50:
                logger.error(
                    "transport departure rejected: held-object offset %.3f m", outward_norm
                )
                return None
            outward /= outward_norm

            nav = getattr(self._backend, "_rp", {}).get("navigation", {})
            retreat_distance = float(nav.get("transport_retreat_distance", 1.0))
            lane_distance = float(nav.get("transport_lane_distance", 2.2))

            route_direction = np.asarray(goal_xy, dtype=float) - np.asarray(start_xy, dtype=float)
            for waypoint in route_hint:
                candidate = np.asarray(waypoint, dtype=float) - np.asarray(start_xy, dtype=float)
                if float(np.linalg.norm(candidate)) >= min(1.5, lane_distance):
                    route_direction = candidate
                    break
            tangent = route_direction - float(np.dot(route_direction, outward)) * outward
            tangent_norm = float(np.linalg.norm(tangent))
            if tangent_norm < 1e-6:
                if float(np.dot(route_direction, outward)) > 0.0:
                    tangent = outward.copy()
                else:
                    tangent = np.array([-outward[1], outward[0]], dtype=float)
                    if float(np.dot(tangent, route_direction)) < 0.0:
                        tangent *= -1.0
            else:
                tangent /= tangent_norm

            retreat = np.asarray(start_xy, dtype=float) + retreat_distance * outward
            lane_exit = retreat + lane_distance * tangent
            if not self._departure_segments_passable(start_xy, [retreat, lane_exit]):
                relative_xy = np.asarray(attachment.get("relative_xy", []), dtype=float)
                if relative_xy.size != 2 or float(np.linalg.norm(relative_xy)) < 0.25:
                    logger.error("transport departure has no valid payload offset")
                    return None
                route_norm = float(np.linalg.norm(route_direction))
                if route_norm < 1e-6:
                    logger.error("transport departure has no valid route direction")
                    return None
                trailing_world_angle = float(np.arctan2(-route_direction[1], -route_direction[0]))
                relative_angle = float(np.arctan2(relative_xy[1], relative_xy[0]))
                departure_yaw = float(
                    (trailing_world_angle - relative_angle + np.pi) % (2.0 * np.pi) - np.pi
                )
                logger.info(
                    "transport departure translation blocked; rotating payload to yaw %.3f",
                    departure_yaw,
                )
                return [], departure_yaw
            logger.info(
                "transport departure: object=%s offset=%.3f retreat=%s lane_exit=%s",
                held,
                outward_norm,
                np.round(retreat, 3),
                np.round(lane_exit, 3),
            )
            return [retreat, lane_exit], None
        except Exception:
            logger.exception("transport departure construction failed")
            return None

    def _departure_segments_passable(
        self, start_xy: np.ndarray, waypoints: list[np.ndarray]
    ) -> bool:
        """Check every 5 cm of a proposed lane exit against the raw map.

        A station approach pose can lie one grid cell inside the conservative
        fixture mask (A* deliberately exempts its endpoints). Permit only that
        short leading escape cell, then require the rest of both segments to
        remain passable. This lets the base move directly away from the source
        instead of rotating a wide payload arc beside neighbouring objects.
        """
        from robot_agent.core.navigation import PASSABLE, in_grid, world_to_grid

        previous = np.asarray(start_xy, dtype=float)
        sample_spacing = max(0.05, self._scene.resolution)
        endpoint_escape_steps = max(1, int(np.ceil(0.10 / sample_spacing)))
        for segment_index, waypoint in enumerate(waypoints):
            waypoint = np.asarray(waypoint, dtype=float)
            distance = float(np.linalg.norm(waypoint - previous))
            samples = max(1, int(np.ceil(distance / sample_spacing)))
            for index in range(1, samples + 1):
                point = previous + (index / samples) * (waypoint - previous)
                cell = world_to_grid(
                    float(point[0]),
                    float(point[1]),
                    self._scene.bounds,
                    self._scene.resolution,
                )
                passable = in_grid(self._grid, cell) and int(self._grid[cell]) in PASSABLE
                leading_endpoint_escape = (
                    segment_index == 0 and index <= endpoint_escape_steps
                )
                if not passable and not leading_endpoint_escape:
                    return False
            previous = waypoint
        return True

    def _payload_turn_is_clear(self, target_yaw: float) -> bool:
        """Reject an in-place turn whose carried-object arc approaches material."""
        held = getattr(self._backend, "_held_crate_name", None)
        if not held:
            return True
        try:
            env = self._backend.env
            attachment = getattr(env, "_factory_sorting_transport_attachment", None)
            if not attachment or not attachment.get("active", False):
                return False
            relative_xy = np.asarray(attachment.get("relative_xy", []), dtype=float)
            if relative_xy.size != 2:
                return False

            base_xy, current_yaw = self._backend.get_base_pose()
            delta = float((target_yaw - current_yaw + np.pi) % (2.0 * np.pi) - np.pi)
            samples = max(2, int(np.ceil(abs(delta) / 0.02)) + 1)
            angles = np.linspace(current_yaw, current_yaw + delta, samples)
            cos_a = np.cos(angles)
            sin_a = np.sin(angles)
            swept_xy = np.column_stack(
                (
                    base_xy[0] + cos_a * relative_xy[0] - sin_a * relative_xy[1],
                    base_xy[1] + sin_a * relative_xy[0] + cos_a * relative_xy[1],
                )
            )

            held_body = env.obj_body_id[held]
            held_z = float(env.sim.data.body_xpos[held_body][2])
            nav = getattr(self._backend, "_rp", {}).get("navigation", {})
            nominal_clearance = float(
                nav.get("transport_turn_min_object_clearance", 0.65)
            )
            material_names = list(getattr(env, "material_metadata", {}).keys())
            if not material_names:
                material_names = list(getattr(env, "obj_body_id", {}).keys())

            for other in material_names:
                if other == held or other not in env.obj_body_id:
                    continue
                other_pos = np.asarray(
                    env.sim.data.body_xpos[env.obj_body_id[other]], dtype=float
                )
                if abs(float(other_pos[2]) - held_z) > 0.75:
                    continue
                distances = np.linalg.norm(swept_xy - other_pos[:2], axis=1)
                initial_distance = float(distances[0])
                minimum_distance = float(np.min(distances))
                required = min(nominal_clearance, max(0.0, initial_distance - 0.05))
                if minimum_distance < required:
                    logger.error(
                        "payload turn rejected: held=%s other=%s min=%.3f required=%.3f",
                        held,
                        other,
                        minimum_distance,
                        required,
                    )
                    return False
            return True
        except Exception:
            logger.exception("payload turn clearance preflight failed")
            return False

    def _plan(
        self, start_xy: np.ndarray, goal_xy: np.ndarray,
    ) -> list[np.ndarray] | None:
        """Run A* and return a world-frame path, or None on failure."""
        from robot_agent.core.map_loader import plan_world_path

        try:
            scene_dict = {
                "bounds": self._scene.bounds,
                "resolution": self._scene.resolution,
            }
            return plan_world_path(
                scene_dict, self._grid, start_xy, goal_xy,
                min_spacing=self._path_spacing,
            )
        except Exception:
            logger.exception("A* planning failed")
            return None
