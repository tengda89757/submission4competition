"""Offline probe: compare A* path clearance before/after obstacle inflation.

Replays the L3/L4 nav legs (spawn -> input_6 approach) on the raw grids and
reports the minimum distance from each waypoint to the nearest impassable
cell.  The judge collision fired at base=(11.7, 6.8) with ~0.05m clearance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from robot_agent.core.map_loader import load_map_files, plan_world_path  # noqa: E402
from robot_agent.core.navigation import PASSABLE, astar, grid_to_world, simplify_path, world_to_grid  # noqa: E402

MAPS = APP / "robosuite" / "robosuite" / "environments" / "factory_sorting" / "generated_maps"

CASES = [
    # (prefix, start_xy from trajectory frame 0, goal = input_6 approach)
    ("factory_sorting_5_3fo3ertpxeut", "input_6"),
    ("factory_sorting_7_3fo3erfky9rn", "input_6"),
    ("factory_sorting_1_3fo3erfhisem", "input_1"),
]


def min_clearance(path, grid, bounds, res) -> float:
    """Min distance (m) from any waypoint to the nearest impassable cell."""
    imp = ~np.isin(grid, list(PASSABLE))
    rows, cols = np.nonzero(imp)
    occ = np.stack([rows, cols], axis=1).astype(float)
    worst = float("inf")
    for p in path:
        cell = np.array(world_to_grid(p[0], p[1], bounds, res), dtype=float)
        d = np.min(np.linalg.norm(occ - cell, axis=1)) * res
        worst = min(worst, d)
    return worst


def plan_raw(scene, grid, start_xy, goal_xy, min_spacing=0.35):
    bounds, res = scene["bounds"], float(scene["resolution"])
    sc = world_to_grid(start_xy[0], start_xy[1], bounds, res)
    gc = world_to_grid(goal_xy[0], goal_xy[1], bounds, res)
    cells = astar(grid, sc, gc)
    return simplify_path([grid_to_world(r, c, bounds, res) for r, c in cells], min_spacing=min_spacing)


def main() -> None:
    for prefix, port in CASES:
        sem = MAPS / f"{prefix}_scene_regenerated_semantic_map.json"
        npy = MAPS / f"{prefix}_scene_regenerated_occupancy_grid.npy"
        scene, grid = load_map_files(sem, npy)
        bounds, res = scene["bounds"], float(scene["resolution"])
        node = scene["input_ports"][port]
        approach = np.array(node["approach"][:2], dtype=float)
        spawn = np.array([13.4951, 0.0346], dtype=float)  # from trajectory frame 0
        legs = [("spawn->approach", spawn, approach)]
        if port == "input_6":
            # pre-drive leg to the calibrated side-table grasp pose (L3/L4);
            # judge collision fired mid-leg at base=(11.7, 6.8)
            legs.append(("approach->side_table", approach, np.array([-4.66, 8.49])))
        print(prefix)
        for label, start, goal in legs:
            old_path = plan_raw(scene, grid, start, goal)
            new_path = plan_world_path(scene, grid, start, goal)
            old_c = min_clearance(old_path, grid, bounds, res)
            new_c = min_clearance(new_path, grid, bounds, res)
            old_len = sum(np.linalg.norm(old_path[i + 1] - old_path[i]) for i in range(len(old_path) - 1))
            new_len = sum(np.linalg.norm(new_path[i + 1] - new_path[i]) for i in range(len(new_path) - 1))
            end_shift = float(np.linalg.norm(new_path[-1] - old_path[-1]))
            print(f"  {label}: old len={old_len:.2f}m clear={old_c:.3f}m | "
                  f"new len={new_len:.2f}m clear={new_c:.3f}m end_shift={end_shift:.3f}m")


if __name__ == "__main__":
    main()
