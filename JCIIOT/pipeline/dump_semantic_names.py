"""dump_semantic_names.py — List named regions in a scene's semantic map.
Usage: python pipeline\\dump_semantic_names.py [scene_prefix]
"""
import json
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
prefix = sys.argv[1] if len(sys.argv) > 1 else "factory_sorting_5_3fo3ertpxeut"
p = (APP_DIR / "robosuite" / "robosuite" / "environments" / "factory_sorting"
     / "generated_maps" / f"{prefix}_scene_regenerated_semantic_map.json")
m = json.loads(p.read_text(encoding="utf-8"))

print(f"map: {p.name}")
print("top-level keys:", list(m.keys()))


def walk(obj, path=""):
    if isinstance(obj, dict):
        name = obj.get("name") or obj.get("id")
        if name and any(k in str(obj) for k in ("center", "position", "pos", "bounds")):
            center = obj.get("center") or obj.get("position") or obj.get("pos")
            yield (str(name), center, path)
        for k, v in obj.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")


seen = set()
for name, center, path in walk(m):
    key = (name, str(center))
    if key in seen:
        continue
    seen.add(key)
    print(f"  {name:45s} center={center} @{path[:60]}")
