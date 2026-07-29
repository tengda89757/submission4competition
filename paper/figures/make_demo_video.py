#!/usr/bin/env python
"""Render a REAL MuJoCo birdview simulation video of the robot executing a
FactorySorting task by replaying a perfect-score submission trajectory.

This uses the project's own, proven ``RobosuiteBackend.replay_trajectory()``
renderer (the exact code path the competition pipeline uses) and encodes the
rendered frames to an H.264 MP4 through the bundled imageio-ffmpeg binary.
It also dumps a handful of evenly-spaced keyframe PNGs that feed the paper's
"video demonstration" screenshot page.

No workarounds: real MuJoCo offscreen rendering + real ffmpeg encoding.

Usage (from the JCIIOT project root, with the project venv):
    .venv\\Scripts\\python.exe pipeline\\submissions_total\\paper\\figures\\make_demo_video.py [L1|L2|L3|L4|L5]

The default level is L5 (FactorySorting9, the 10-object flagship task).
Requires GL/GPU access (elevated sandbox permissions).
"""
from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────
FIG_DIR = Path(__file__).resolve().parent               # .../paper/figures
SUBMISSIONS = FIG_DIR.parents[1]                         # .../submissions_total
ROOT = FIG_DIR.parents[3]                                # .../JCIIOT
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

OUT_DIR = FIG_DIR / "demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── render configuration ───────────────────────────────────────────────────
LEVEL = (sys.argv[1] if len(sys.argv) > 1 else "L5").upper()
CAMERA = (sys.argv[2] if len(sys.argv) > 2 else "birdview").lower()  # birdview | follow
WIDTH = 720          # divisible by 16 -> no ffmpeg macroblock resize
HEIGHT = 544         # divisible by 16
FPS = 30
TARGET_FRAMES = 700  # ~23s video; bounds render time + memory
N_KEYFRAMES = 6

# Use the ffmpeg binary that ships with imageio-ffmpeg (installed in the venv).
os.environ.pop("MUJOCO_GL", None)  # default wgl backend on Windows (egl is invalid here)
import imageio_ffmpeg  # noqa: E402
os.environ["IMAGEIO_FFMPEG_EXE"] = imageio_ffmpeg.get_ffmpeg_exe()
import imageio.v2 as iio  # noqa: E402


def _find_zip(level: str) -> Path:
    matches = sorted(SUBMISSIONS.glob(f"{level}_*.zip"))
    if not matches:
        raise FileNotFoundError(f"No submission zip found for {level} in {SUBMISSIONS}")
    return matches[-1]


def _load_trajectory(zip_path: Path) -> tuple[dict, dict]:
    with zipfile.ZipFile(zip_path) as z:
        manifest = json.loads(z.read("submission_manifest.json"))
        traj = json.loads(z.read("trajectory.json"))
    return manifest, traj


def _subsample(traj: dict, target: int) -> dict:
    frames = traj.get("frames", [])
    n = len(frames)
    if n <= target:
        step = 1
        sub = frames
    else:
        step = max(1, round(n / target))
        sub = frames[::step]
        if sub[-1] is not frames[-1]:
            sub.append(frames[-1])  # always show the final placed state
    out = dict(traj)
    out["frames"] = sub
    print(f"[subsample] {n} -> {len(sub)} frames (step={step})")
    return out


def main() -> int:
    t0 = time.perf_counter()
    zip_path = _find_zip(LEVEL)
    print(f"[demo] level={LEVEL}  zip={zip_path.name}")
    manifest, traj = _load_trajectory(zip_path)
    env_name = manifest.get("env_name") or traj.get("robot_model")
    print(f"[demo] env_name={env_name}  frames={len(traj.get('frames', []))}"
          f"  objects={len(traj.get('object_names', []))}  camera={traj.get('camera')}")

    sub = _subsample(traj, TARGET_FRAMES)
    tmp_json = OUT_DIR / f"_{LEVEL.lower()}_subsampled.json"
    tmp_json.write_text(json.dumps(sub), encoding="utf-8")

    # ── build the env and replay through the project's proven renderer ──
    from robot_agent.environments import RobosuiteBackend

    # "follow" is a virtual chase-camera handled inside replay_trajectory; the
    # backend itself must be created with a real MuJoCo camera name.
    real_cameras = {"frontview", "birdview", "agentview", "sideview", "robot0_robotview"}
    backend_camera = CAMERA if CAMERA in real_cameras else "frontview"
    print(f"[demo] creating RobosuiteBackend(env_name={env_name}, camera={backend_camera}) "
          f"replay_camera={CAMERA} ...")
    backend = RobosuiteBackend(
        env_name=env_name, camera=backend_camera, drive_mode="direct", headless=True,
    )
    backend.reset()
    print("[demo] env ready; rendering frames (this can take a few minutes) ...")
    frames = backend.replay_trajectory(
        str(tmp_json), None, camera=CAMERA, width=WIDTH, height=HEIGHT,
    )
    backend.close()
    if not frames:
        print("[demo] ERROR: no frames rendered", file=sys.stderr)
        return 2
    print(f"[demo] rendered {len(frames)} frames @ {WIDTH}x{HEIGHT} "
          f"in {time.perf_counter() - t0:.1f}s")

    # ── encode MP4 ──
    tag = f"{LEVEL.lower()}_{CAMERA}"
    mp4_path = OUT_DIR / f"{tag}_demo.mp4"
    writer = iio.get_writer(
        str(mp4_path), format="FFMPEG", mode="I", fps=FPS,
        codec="libx264", quality=8, macro_block_size=16, pixelformat="yuv420p",
    )
    for f in frames:
        writer.append_data(f)
    writer.close()
    size_mb = mp4_path.stat().st_size / 1e6
    print(f"[demo] MP4 saved: {mp4_path}  ({size_mb:.1f} MB, {len(frames)/FPS:.1f}s)")

    # ── keyframe PNGs (evenly spaced across the task) ──
    n = len(frames)
    positions = [0.02, 0.20, 0.40, 0.60, 0.80, 0.98][:N_KEYFRAMES]
    for i, p in enumerate(positions, start=1):
        idx = min(n - 1, max(0, int(round(p * (n - 1)))))
        kf = OUT_DIR / f"{tag}_keyframe_{i}.png"
        iio.imwrite(str(kf), frames[idx])
        print(f"[demo] keyframe {i}: frame {idx} -> {kf.name}")

    print(f"[demo] DONE in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
