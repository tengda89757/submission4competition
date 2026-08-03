"""Move skill — navigate the robot base to a target via A* + backend."""

from __future__ import annotations

import logging
import re

import numpy as np

from robot_agent.core.types import ExecutionContext, SkillResult
from robot_agent.skills.base import BaseSkill

logger = logging.getLogger(__name__)


def _inflate_obstacles(grid: np.ndarray, margin_cells: int) -> np.ndarray:
    """Dilate impassable cells without modifying the official grid."""
    from robot_agent.core.navigation import OBSTACLE, PASSABLE

    if margin_cells <= 0:
        return grid
    impassable = ~np.isin(grid, list(PASSABLE))
    dilated = impassable.copy()
    for dr in range(-margin_cells, margin_cells + 1):
        for dc in range(-margin_cells, margin_cells + 1):
            if (dr == 0 and dc == 0) or dr * dr + dc * dc > margin_cells * margin_cells:
                continue
            src_r = slice(max(0, -dr), impassable.shape[0] - max(0, dr))
            dst_r = slice(max(0, dr), impassable.shape[0] - max(0, -dr))
            src_c = slice(max(0, -dc), impassable.shape[1] - max(0, dc))
            dst_c = slice(max(0, dc), impassable.shape[1] - max(0, -dc))
            dilated[dst_r, dst_c] |= impassable[src_r, src_c]
    inflated = grid.copy()
    inflated[dilated & ~impassable] = OBSTACLE
    return inflated


def plan_clearance_world_path(
    scene: dict,
    grid: np.ndarray,
    start_xy: np.ndarray,
    goal_xy: np.ndarray,
    *,
    min_spacing: float = 0.35,
) -> list[np.ndarray]:
    """Plan in the editable skill layer using a conservative-to-raw ladder.

    Endpoint neighborhoods are restored from the official occupancy grid so a
    legitimate station approach is not swallowed by obstacle dilation. If a
    conservative margin is infeasible, the next smaller margin is attempted;
    the final attempt is the unmodified official grid.
    """
    from robot_agent.core.navigation import (
        astar,
        grid_to_world,
        simplify_path,
        world_to_grid,
    )

    bounds = scene.get("bounds") or {}
    resolution = float(scene.get("resolution", 0.05))
    start_cell = world_to_grid(start_xy[0], start_xy[1], bounds, resolution)
    goal_cell = world_to_grid(goal_xy[0], goal_xy[1], bounds, resolution)
    last_error: Exception | None = None

    for margin_m in (0.45, 0.30, 0.15, 0.0):
        margin_cells = int(round(margin_m / resolution))
        candidate = _inflate_obstacles(grid, margin_cells)
        if margin_cells > 0:
            candidate = candidate.copy()
            for cell in (start_cell, goal_cell):
                r0 = max(0, cell[0] - margin_cells - 2)
                r1 = min(grid.shape[0], cell[0] + margin_cells + 3)
                c0 = max(0, cell[1] - margin_cells - 2)
                c1 = min(grid.shape[1], cell[1] + margin_cells + 3)
                candidate[r0:r1, c0:c1] = grid[r0:r1, c0:c1]
        try:
            cells = astar(candidate, start_cell, goal_cell)
            world = [
                grid_to_world(row, col, bounds, resolution)
                for row, col in cells
            ]
            logger.info("skill-layer A*: margin=%.2fm cells=%d", margin_m, len(cells))
            return simplify_path(world, min_spacing=min_spacing)
        except RuntimeError as exc:
            last_error = exc

    raise RuntimeError(f"A* failed at every clearance margin: {last_error}")


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
        path = self._plan(start_xy, goal_xy)
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
                "waypoints": len(path),
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
        lateral = (0.0, 0.38, -0.38)[visit % 3]
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

    def _plan(
        self, start_xy: np.ndarray, goal_xy: np.ndarray,
    ) -> list[np.ndarray] | None:
        """Run A* and return a world-frame path, or None on failure."""
        try:
            scene_dict = {
                "bounds": self._scene.bounds,
                "resolution": self._scene.resolution,
            }
            return plan_clearance_world_path(
                scene_dict, self._grid, start_xy, goal_xy,
                min_spacing=self._path_spacing,
            )
        except Exception:
            logger.exception("A* planning failed")
            return None
