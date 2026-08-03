#!/usr/bin/env python
"""verify_submission.py -- Reproduce and verify the reported competition scores.

Re-scores each level's submitted trajectory (extracted from the five official
ZIPs in submissions/) with the exact objective scorer used by the pipeline
(JCIIOT/pipeline/score_trajectory.py, score_rule_version =
grasp_success_gate_l5_multi_v2) and checks that the recomputed score matches
BOTH the score.json stored inside the ZIP AND the level's maximum.

This check is deterministic and requires NO LLM, NO GPU and NO MuJoCo rendering:
it only needs the scene occupancy/semantic maps plus the trajectory, so any
evaluator can confirm the reported 100/100 in a few seconds.

Usage (from the repository root, after JCIIOT/pipeline/setup_env.ps1):
    JCIIOT\\.venv\\Scripts\\python.exe verify_submission.py
    JCIIOT\\.venv\\Scripts\\python.exe verify_submission.py \
        --submissions submission_100_final_129e94a9 \
        --json-out submission_100_final_129e94a9/verification_report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent               # repository root
PIPELINE = ROOT / "JCIIOT" / "pipeline"
sys.path.insert(0, str(PIPELINE))
import score_trajectory as st  # noqa: E402  (adds src/robomimic/robosuite to sys.path on import)

LEVELS = [("L1", 0), ("L2", 1), ("L3", 2), ("L4", 3), ("L5", 4)]
MAX = {0: 10, 1: 15, 2: 20, 3: 25, 4: 30}

OFFICIAL_REFERENCE_COMMIT = "129e94a9cff787031472045e19c24a4baeaefc48"
EXPECTED_MEMBERS = {"trajectory.json", "score.json", "submission_manifest.json"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--submissions",
        type=Path,
        default=ROOT / "submissions",
        help="Directory containing one L1_*.zip through L5_*.zip",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional machine-readable verification report path",
    )
    args = parser.parse_args(argv)
    submissions = args.submissions.resolve()

    rows: list[dict] = []
    ok_all = True
    grand_reported = 0
    grand_recomputed = 0

    for lvl, idx in LEVELS:
        zips = sorted(submissions.glob(f"{lvl}_*.zip"))
        if not zips:
            rows.append({
                "level": lvl, "package": "<missing zip>", "reported": None,
                "recomputed": None, "max": MAX[idx], "status": "FAIL",
                "reason": "package missing",
            })
            ok_all = False
            continue
        zpath = zips[-1]
        try:
            package_bytes = zpath.read_bytes()
            with zipfile.ZipFile(zpath) as z:
                members = set(z.namelist())
                members_ok = members == EXPECTED_MEMBERS
                traj_bytes = z.read("trajectory.json")
                json.loads(traj_bytes)
                score_doc = json.loads(z.read("score.json"))
                manifest = json.loads(z.read("submission_manifest.json"))
                reported = int(score_doc.get("score"))

            with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tf:
                tf.write(traj_bytes)
                tmp = Path(tf.name)
            try:
                result = st.score(idx, tmp)
            finally:
                tmp.unlink(missing_ok=True)
        except Exception as exc:
            rows.append({
                "level": lvl, "package": zpath.name, "reported": None,
                "recomputed": None, "max": MAX[idx], "status": "FAIL",
                "reason": f"invalid package: {exc}",
            })
            ok_all = False
            continue

        recomputed = int(result.get("total", -1))
        mx = MAX[idx]
        reference_ok = manifest.get("official_reference_commit") == OFFICIAL_REFERENCE_COMMIT
        row_ok = (
            recomputed == mx
            and reported == mx
            and members_ok
            and reference_ok
            and manifest.get("level") == lvl
        )
        ok_all = ok_all and row_ok
        grand_reported += reported or 0
        grand_recomputed += recomputed
        rows.append({
            "level": lvl,
            "package": zpath.name,
            "package_sha256": _sha256(package_bytes),
            "trajectory_sha256": _sha256(traj_bytes),
            "members": sorted(members),
            "reported": reported,
            "recomputed": recomputed,
            "max": mx,
            "manifest_reference": manifest.get("official_reference_commit"),
            "status": "PASS" if row_ok else "FAIL",
        })

    print()
    print(f"{'Level':<6}{'Package':<28}{'Reported':>9}{'Recomputed':>12}{'Max':>5}  Result")
    print("-" * 74)
    for row in rows:
        print(
            f"{row['level']:<6}{row['package']:<28}"
            f"{str(row['reported']):>9}{str(row['recomputed']):>12}"
            f"{row['max']:>5}  {row['status']}"
        )
    print("-" * 74)
    print(f"{'TOTAL':<34}{grand_reported:>9}{grand_recomputed:>12}{sum(MAX.values()):>5}")
    print()
    print(f"Official scoring reference: {OFFICIAL_REFERENCE_COMMIT}")

    success = ok_all and grand_recomputed == 100
    if args.json_out:
        report_path = args.json_out.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "official_reference_commit": OFFICIAL_REFERENCE_COMMIT,
            "submissions_directory": str(submissions),
            "reported_total": grand_reported,
            "recomputed_total": grand_recomputed,
            "maximum_total": sum(MAX.values()),
            "result": "PASS" if success else "FAIL",
            "packages": rows,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Verification report: {report_path}")

    if success:
        print("RESULT: [OK] All five levels reproduce their reported scores. Total = 100/100.")
        return 0
    print("RESULT: [FAIL] Score mismatch detected -- see the table above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
