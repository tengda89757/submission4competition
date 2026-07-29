"""Probe scene-9 white tote grasp sites + AABB overlap (docx-first L5 audit)."""
import re
import sys
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "robosuite" / "robosuite"))
sys.path.insert(0, str(APP / "robosuite"))

import robosuite  # noqa: E402

TOTES = ["white_tote_b01_left_front", "white_tote_b01_left_center", "white_tote_b01_left_back"]

env = robosuite.make(
    "FactorySorting9_3FO3ERT2C5FP", robots="Tiago",
    has_renderer=False, has_offscreen_renderer=False,
    use_camera_obs=False, control_freq=20,
)
env.reset()

pts = {}
for t in TOTES:
    body = np.array(env.sim.data.body_xpos[env.obj_body_id[t]])
    r = np.array(env.sim.data.site_xpos[env.sim.model.site_name2id(f"{t}_right_grasp_site")])
    l = np.array(env.sim.data.site_xpos[env.sim.model.site_name2id(f"{t}_left_grasp_site")])
    print(f"{t}: obj={body.round(3).tolist()} r_site={r.round(3).tolist()} l_site={l.round(3).tolist()}")
    pts[t + "_r"] = (r[0], r[1], r[2])
    pts[t + "_l"] = (l[0], l[1], l[2])
env.close()

# AABB overlap check against scene-9 collision proxies
SRC = APP / "robosuite" / "robosuite" / "environments" / "factory_sorting" / "factory_sorting_9_3fo3ert2c5fp.py"
src = SRC.read_text(encoding="utf-8")
m = re.search(r"SCENE_AABB_COLLISION_BOXES = \((.*?)\n\)", src, re.S)
rows = re.findall(
    r'\(\s*"([\w]+)",\s*"([\w]+)",\s*\[([-\d.,\s]+)\],\s*\[([-\d.,\s]+)\]\s*\)', m.group(1))
H = {"station": (0.55, 0.55), "production_line_equipment": (0.95, 0.95),
     "production_line_belt": (0.55, 0.55), "production_line_local_protrusion": (0.55, 0.55),
     "production_line_local_equipment": (0.95, 0.95), "side_station": (0.55, 0.55),
     "right_side_device": (0.55, 0.55)}
ov = re.search(r"SCENE_AABB_COLLISION_HEIGHT_OVERRIDES = \{(.*?)\}", src, re.S)
overrides = {}
if ov:
    for name, zc, zh in re.findall(r'"([\w]+)":\s*\(([\d.]+),\s*([\d.]+)\)', ov.group(1)):
        overrides[name] = (float(zc), float(zh))

print("\nAABB overlaps (site inside a proxy whose top is above site z):")
for name, kind, c, s in rows:
    cx, cy = [float(v) for v in c.split(",")]
    sx, sy = [float(v) for v in s.split(",")]
    hx, hy = sx / 2, sy / 2
    zc, zh = overrides.get(name, H.get(kind, (0.55, 0.55)))
    ztop = zc + zh
    for pn, (px, py, pz) in pts.items():
        mx, my = hx - abs(px - cx), hy - abs(py - cy)
        if mx > -0.15 and my > -0.15:
            state = "INSIDE" if (mx > 0 and my > 0 and ztop > pz - 0.15) else "near"
            print(f"  {pn}(z={pz:.2f}) vs {name}: dx={mx:+.3f} dy={my:+.3f} ztop={ztop:.2f} {state}")
