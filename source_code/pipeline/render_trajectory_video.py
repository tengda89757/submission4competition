"""Render every frame of an audited trajectory to a streaming H.264 video.

Unlike the legacy demonstration helper, this script never subsamples the
trajectory.  It reuses ``RobosuiteBackend.replay_trajectory`` in bounded chunks
so long L5 recordings do not accumulate gigabytes of RGB frames in memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
for candidate in (
    APP_DIR / "src",
    APP_DIR,
    APP_DIR / "robomimic",
    APP_DIR / "robosuite" / "robosuite",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--camera",
        default="frontview,robot0_robotview",
        help="one camera or a comma-separated list combined left-to-right",
    )
    parser.add_argument("--width", type=int, default=384, help="width of each view")
    parser.add_argument("--height", type=int, default=288)
    parser.add_argument("--fps", type=float, default=20.0)
    parser.add_argument("--chunk-size", type=int, default=200)
    parser.add_argument("--keyframes-dir", type=Path)
    parser.add_argument("--keyframe-count", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    trajectory_path = args.trajectory.resolve()
    output_path = args.output.resolve()
    data = json.loads(trajectory_path.read_text(encoding="utf-8"))
    frame_count = len(data.get("frames", []))
    env_name = data.get("robot_model")
    cameras = [item.strip() for item in args.camera.split(",") if item.strip()]
    if not env_name or frame_count == 0:
        raise RuntimeError("trajectory must provide robot_model and at least one frame")
    if not cameras:
        raise ValueError("at least one camera is required")
    if args.width <= 0 or args.height <= 0 or args.fps <= 0 or args.chunk_size <= 0:
        raise ValueError("width, height, fps, and chunk-size must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.keyframes_dir:
        args.keyframes_dir.mkdir(parents=True, exist_ok=True)

    # Windows uses WGL for the project's offscreen renderer.  imageio-ffmpeg
    # supplies a known ffmpeg binary inside the project environment.
    os.environ.pop("MUJOCO_GL", None)
    import imageio_ffmpeg

    os.environ["IMAGEIO_FFMPEG_EXE"] = imageio_ffmpeg.get_ffmpeg_exe()
    import imageio.v2 as imageio

    from robot_agent.environments import RobosuiteBackend

    # Always construct the environment with its stable fixed front camera.
    # Requested replay cameras are selected per frame below; constructing some
    # generated scenes with agentview / sideview makes WGL return black frames.
    backend_camera = "frontview"
    backend = RobosuiteBackend(
        env_name=env_name,
        camera=backend_camera,
        drive_mode="direct",
        headless=True,
    )

    started = time.perf_counter()
    encoded = 0
    keyframe_indices: dict[int, int] = {}
    if args.keyframes_dir and args.keyframe_count > 0:
        count = min(args.keyframe_count, frame_count)
        if count == 1:
            keyframe_indices[0] = 1
        else:
            for number in range(count):
                index = round(number * (frame_count - 1) / (count - 1))
                keyframe_indices[int(index)] = number + 1

    writer = None
    try:
        backend.reset()
        from robosuite.utils.binding_utils import MjRenderContextOffscreen
        writer = imageio.get_writer(
            str(output_path),
            format="FFMPEG",
            mode="I",
            fps=args.fps,
            codec="libx264",
            quality=7,
            macro_block_size=16,
            pixelformat="yuv420p",
            ffmpeg_log_level="warning",
        )
        for start in range(0, frame_count, args.chunk_size):
            end = min(frame_count, start + args.chunk_size)
            rendered_views = []
            for camera in cameras:
                # Assign the chunk's first state before rebuilding the context.
                # On this robosuite / Windows WGL stack, a large replay-state
                # jump (including rewinding for the second camera) invalidates
                # the old context. The priming frame is intentionally ignored.
                backend.replay_trajectory(
                    trajectory_path,
                    None,
                    # Use a different fixed camera for the discarded priming
                    # render. Reusing the target camera during the state jump
                    # can leave that target's new WGL context black.
                    camera="frontview",
                    width=args.width,
                    height=args.height,
                    frame_start=start,
                    frame_end=start + 1,
                )
                # Rebuild-and-probe until this camera produces a real frame.
                # Scene 7 needs two WGL context initializations at some states;
                # the probe is discarded and therefore never changes the
                # output frame count.
                probe_ok = False
                for _attempt in range(4):
                    backend.env.sim.add_render_context(
                        MjRenderContextOffscreen(
                            backend.env.sim,
                            device_id=-1,
                            max_width=args.width,
                            max_height=args.height,
                        )
                    )
                    probe = backend.replay_trajectory(
                        trajectory_path,
                        None,
                        camera=camera,
                        width=args.width,
                        height=args.height,
                        frame_start=start,
                        frame_end=start + 1,
                    )
                    if probe and int(probe[0].max()) > 0:
                        probe_ok = True
                        break
                if not probe_ok:
                    raise RuntimeError(
                        f"camera {camera} remained black after context retries at frame {start}"
                    )
                view_frames = backend.replay_trajectory(
                    trajectory_path,
                    None,
                    camera=camera,
                    width=args.width,
                    height=args.height,
                    frame_start=start,
                    frame_end=end,
                )
                if len(view_frames) != end - start:
                    raise RuntimeError(
                        f"renderer returned {len(view_frames)} frames for "
                        f"{camera} range {start}:{end}"
                    )
                black_frames = [
                    start + index
                    for index, frame in enumerate(view_frames)
                    if int(frame.max()) == 0
                ]
                if black_frames:
                    raise RuntimeError(
                        f"camera {camera} returned black frame(s): {black_frames[:10]}"
                    )
                rendered_views.append(view_frames)

            for offset in range(end - start):
                if len(rendered_views) == 1:
                    frame = rendered_views[0][offset]
                else:
                    import numpy as np

                    frame = np.concatenate(
                        [view_frames[offset] for view_frames in rendered_views], axis=1
                    )
                absolute_index = start + offset
                writer.append_data(frame)
                encoded += 1
                keyframe_number = keyframe_indices.get(absolute_index)
                if keyframe_number is not None and args.keyframes_dir:
                    keyframe_path = args.keyframes_dir / (
                        f"{output_path.stem}_keyframe_{keyframe_number}.png"
                    )
                    imageio.imwrite(str(keyframe_path), frame)
            elapsed = time.perf_counter() - started
            print(
                f"[render] {encoded}/{frame_count} frames "
                f"({100.0 * encoded / frame_count:.1f}%) elapsed={elapsed:.1f}s",
                flush=True,
            )
    finally:
        if writer is not None:
            writer.close()
        backend.close()

    if encoded != frame_count:
        raise RuntimeError(f"encoded frame count mismatch: {encoded} != {frame_count}")

    metadata = {
        "format_version": 1,
        "source_trajectory": trajectory_path.name,
        "source_trajectory_sha256": _sha256(trajectory_path),
        "environment": env_name,
        "camera_views": cameras,
        "source_frames": frame_count,
        "encoded_frames": encoded,
        "subsample_step": 1,
        "fps": args.fps,
        "duration_seconds": round(encoded / args.fps, 3),
        "resolution": [args.width * len(cameras), args.height],
        "video_file": output_path.name,
        "video_sha256": _sha256(output_path),
        "video_bytes": output_path.stat().st_size,
        "render_wall_seconds": round(time.perf_counter() - started, 3),
    }
    metadata_path = output_path.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
