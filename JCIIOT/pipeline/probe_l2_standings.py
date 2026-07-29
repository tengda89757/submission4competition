"""Probe candidate base standings around green_tote_b01_upper in scene 3."""
import sys
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from robot_agent.core.map_loader import load_map_files
from robot_agent.core.navigation import PASSABLE, world_to_grid

MAPS = APP / "robosuite" / "robosuite" / "environments" / "factory_sorting" / "generated_maps"
scene, grid = load_map_files(
    MAPS / "factory_sorting_3_3fo3errph7x9_scene_regenerated_semantic_map.json",
    MAPS / "factory_sorting_3_3fo3errph7x9_scene_regenerated_occupancy_grid.npy",
)
bounds, res = scene["bounds"], float(scene["resolution"])

# object green_tote_b01_upper at (11.87, 4.62, 1.20); sites y=4.41 (south rim), z=1.40
# candidates: base 0.941m from object in each direction
CANDS = {
    "lower_south (tried, failed)": (11.87, 2.25),
    "upper_south (between totes)": (11.87, 3.68),
    "upper_north": (11.87, 5.56),
    "upper_east": (12.81, 4.62),
    "upper_west": (10.93, 4.62),
}
for name, (x, y) in CANDS.items():
    r, c = world_to_grid(x, y, bounds, res)
    ok = 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]
    v = int(grid[r, c]) if ok else -1
    vals = grid[max(0, r - 3):r + 4, max(0, c - 3):c + 4]
    free = float(np.isin(vals, list(PASSABLE)).mean())
    state = "PASSABLE" if v in PASSABLE else "BLOCKED"
    print(f"{name}: ({x},{y}) cell={v} {state} 7x7-free={free:.0%}")
