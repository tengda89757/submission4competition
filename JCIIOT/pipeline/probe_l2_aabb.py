"""Which scene-3 AABB proxies overlap the L2 upper-tote grasp geometry?"""
import re

SRC = (r"d:\2026\JCOII-2026\JCIIOT2026-master\JCIIOT\robosuite\robosuite"
       r"\environments\factory_sorting\factory_sorting_3_3fo3errph7x9.py")
src = open(SRC, encoding="utf-8").read()

m = re.search(r"SCENE_AABB_COLLISION_BOXES = \((.*?)\n\)", src, re.S)
rows = re.findall(
    r'\(\s*"([\w]+)",\s*"([\w]+)",\s*\[([-\d.,\s]+)\],\s*\[([-\d.,\s]+)\]\s*\)',
    m.group(1))
H = {"station": (0.55, 0.55), "production_line_equipment": (0.95, 0.95),
     "production_line_belt": (0.55, 0.55), "production_line_local_protrusion": (0.55, 0.55),
     "production_line_local_equipment": (0.95, 0.95), "side_station": (0.55, 0.55),
     "right_side_device": (0.55, 0.55)}
ov = re.search(r"SCENE_AABB_COLLISION_HEIGHT_OVERRIDES = \{(.*?)\}", src, re.S)
overrides = {}
if ov:
    for name, zc, zh in re.findall(r'"([\w]+)":\s*\(([\d.]+),\s*([\d.]+)\)', ov.group(1)):
        overrides[name] = (float(zc), float(zh))

PTS = {"left_site": (11.703, 4.41), "right_site": (12.033, 4.41),
       "upper_tote": (11.87, 4.62), "base_best": (12.018, 3.434)}

for name, kind, c, s in rows:
    cx, cy = [float(v) for v in c.split(",")]
    sx, sy = [float(v) for v in s.split(",")]
    hx, hy = sx / 2, sy / 2
    zc, zh = overrides.get(name, H[kind])
    ztop = zc + zh
    for pn, (px, py) in PTS.items():
        mx, my = hx - abs(px - cx), hy - abs(py - cy)
        if mx > -0.35 and my > -0.35:
            state = "INSIDE" if (mx > 0 and my > 0) else "near"
            print(f"{pn} vs {name}: dx_margin={mx:+.3f} dy_margin={my:+.3f} ztop={ztop:.2f} {state}")
