"""
Load semantic maps and occupancy grids; plan world-frame paths.

Thin orchestration layer that ties ``navigation.py`` to file I/O.
Does **not** import robosuite — pure numpy + stdlib.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from robot_agent.core.navigation import (
    PASSABLE,
    astar,
    grid_to_world,
    inflate_obstacles,
    nearest_passable_cell,
    simplify_path,
    world_to_grid,
)


# ── map loading ─────────────────────────────────────────────

def load_semantic_map(path: str | Path) -> dict:
    """Load a semantic-map JSON file (e.g. ``factory_sorting_semantic_map.json``)."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_occupancy_grid(path: str | Path) -> np.ndarray:
    """Load an occupancy grid ``.npy`` file."""
    return np.load(str(path))


def load_map_files(
    semantic_map: str | Path,
    occupancy_grid: str | Path,
) -> tuple[dict, np.ndarray]:
    """Convenience: load both semantic map and occupancy grid at once.

    Returns ``(scene_dict, grid_array)``.
    """
    return load_semantic_map(semantic_map), load_occupancy_grid(occupancy_grid)


# ── path planning (world-frame) ─────────────────────────────

def plan_world_path(
    scene: dict,
    grid: np.ndarray,
    start_xy: np.ndarray,
    goal_xy: np.ndarray,
    min_spacing: float = 0.35,
) -> list[np.ndarray]:
    """Plan a world-frame path from *start_xy* to *goal_xy*.

    1. Convert world → grid
    2. Run A*
    3. Convert grid → world
    4. Simplify (down-sample)

    Args:
        scene: Semantic map dict (must contain ``bounds`` and ``resolution``).
        grid: 2D occupancy grid (uint8).
        start_xy: (2,) world position.
        goal_xy:  (2,) world position.
        min_spacing: Minimum spacing (m) between consecutive waypoints.

    Returns:
        List of (2,) numpy arrays in world frame.
    """
    bounds = scene["bounds"]
    resolution = float(scene["resolution"])

    start_cell = world_to_grid(start_xy[0], start_xy[1], bounds, resolution)
    goal_cell = world_to_grid(goal_xy[0], goal_xy[1], bounds, resolution)

    # Prefer paths that keep clearance from obstacle AABBs: the base fits
    # through 1-cell gaps but the arms stick out ~0.4 m and clip modules
    # (judge collision → -5).  Degrade the margin gracefully so tight
    # approach corridors never become unreachable.
    def _ladder(goal):
        for margin_m in (0.45, 0.30, 0.15, 0.0):
            margin_cells = int(round(margin_m / resolution))
            inflated = inflate_obstacles(grid, margin_cells)
            if margin_cells > 0:
                # Exempt endpoints: approach points sit right next to station
                # tables and would be swallowed by the dilation, which shifts
                # the snapped goal and degrades placement accuracy.
                for cell in (start_cell, goal):
                    r0 = max(0, cell[0] - margin_cells - 2)
                    r1 = min(grid.shape[0], cell[0] + margin_cells + 3)
                    c0 = max(0, cell[1] - margin_cells - 2)
                    c1 = min(grid.shape[1], cell[1] + margin_cells + 3)
                    inflated[r0:r1, c0:c1] = grid[r0:r1, c0:c1]
            try:
                return astar(inflated, start_cell, goal)
            except RuntimeError:
                continue
        return None

    cell_path = _ladder(goal_cell)
    if cell_path is None:
        # Goal may sit in a sealed-off passable pocket (scene 9 output_6):
        # re-target the nearest cell reachable from the start.
        snapped = _snap_goal_into_start_component(grid, start_cell, goal_cell)
        if snapped is not None:
            cell_path = _ladder(snapped)
            if cell_path is not None:
                print(f"[NAV] goal cell {tuple(goal_cell)} unreachable; snapped to "
                      f"{snapped} in start's component", flush=True)
    if cell_path is None:
        # Surface the original planner error for the raw grid
        cell_path = astar(grid, start_cell, goal_cell)
    world_path = [
        grid_to_world(row, col, bounds, resolution) for row, col in cell_path
    ]
    return simplify_path(world_path, min_spacing=min_spacing)


def _snap_goal_into_start_component(
    grid: np.ndarray,
    start_cell: tuple[int, int],
    goal_cell: tuple[int, int],
):
    """Nearest cell to *goal_cell* reachable from *start_cell*, or None.

    Some generated maps contain passable pockets sealed off by obstacle rings
    (scene 9: output_6's approach point sits in a 39-cell island), so A* snaps
    the goal INTO the pocket and then fails. Planning to the closest cell of
    the start's connected component gets the base as near the station as the
    map allows — the transport attachment holds the object 0.94 m ahead, which
    still lands it within the 0.80 m scoring radius.
    """
    try:
        from scipy import ndimage
    except ImportError:
        return None
    try:
        start = nearest_passable_cell(grid, start_cell)
    except RuntimeError:
        return None
    passable = np.isin(grid, list(PASSABLE))
    labels, _ = ndimage.label(passable, structure=np.ones((3, 3), dtype=bool))
    comp = labels[start[0], start[1]]
    if comp == 0:
        return None
    rows, cols = np.nonzero(labels == comp)
    d2 = (rows - goal_cell[0]) ** 2 + (cols - goal_cell[1]) ** 2
    i = int(np.argmin(d2))
    snapped = (int(rows[i]), int(cols[i]))
    return None if snapped == tuple(goal_cell) else snapped


# ── station summary (for LLM) ───────────────────────────────

def summarize_map_for_llm(scene: dict) -> dict:
    """Extract a compact station summary suitable for an LLM prompt.

    Returns ``{name: {role, kind, center, approach, display_name, image_position}}``.
    """
    nodes: dict[str, dict] = {}
    for group in ("input_ports", "output_ports"):
        for name, obj in scene.get(group, {}).items():
            nodes[name] = {
                "role": obj.get("role"),
                "kind": obj.get("kind"),
                "center": obj.get("center"),
                "approach": obj.get("approach"),
                "display_name": obj.get("display_name", name),
                "image_position": obj.get("image_position"),
            }
    return nodes
