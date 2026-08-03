# Auditable Skill-Layer Robotics for Factory Sorting

**Team:** BIPT-EDU  
**Official reference:** `129e94a9cff787031472045e19c24a4baeaefc48`
**Recomputed objective score:** **100/100** (`10 + 15 + 20 + 25 + 30`)

> “100/100” in this document means the deterministic rescore of the packaged
> trajectories under the task definition pinned above. Final acceptance remains
> subject to the organizer’s source-code audit.

## Abstract

This report describes a unified RobotAgent and an auditable chain from the
official task definition to the submitted trajectory bytes. The previous package
reproduces exactly **65/100**: L3 used the obsolete `input_6` / left-blue route,
and L5 released at obsolete `output_6`. The corrected system binds execution to
the current official routes, synthesizes grasp approach frames from live official
object sites, performs clearance-aware positioning entirely in the editable
skill layer, and preserves L5 state across three physical grasp/place cycles.

No final trajectory JSON, transport attachment, locked task configuration, map,
core file, or environment file is post-processed by participant code.

## 1. Official task definition

| Level | Source | Target | Accepted candidates | Max |
|---|---|---|---|---:|
| L1 | `input_5` | `output_4` | `line_5_container_h01_near/far` | 10 |
| L2 | `input_6` | `output_4` | `green_tote_b01_upper/lower` | 15 |
| L3 | `aux_input_1` | `output_5` | `blue_tote_b01_far_right/near_right` | 20 |
| L4 | `input_2` | `output_5` | `blue_container_h01_back_upper/lower` | 25 |
| L5 | `input_1` | `aux_output_1` | three `white_tote_b01_left_*` objects | 30 |

The source of truth is the official `knowledge/task_config.json` at commit
`129e94a9`; Case 3’s Placement Point 1 wording is consistent with the official
erratum.

## 2. Why the previous package scored 65

| Level | Previous | Final | Explanation |
|---|---:|---:|---|
| L1 | 10 | 10 | Already matched the current route. |
| L2 | 15 | 15 | Already matched the current route. |
| L3 | 0 | 20 | Old trajectory grasped `blue_tote_b01_near_left` at `input_6`; both source and candidate set are now different. |
| L4 | 25 | 25 | Already matched the current route. |
| L5 | 15 | 30 | Three grasps were valid, but releases were near stale `output_6`, not `aux_output_1`. |
| **Total** | **65** | **100** | L3 recovered 20 and L5 recovered 15. |

The old self-test mixed stale routes with a nearest-object fallback. It therefore
validated a different task from the one used by the current organizer-facing
JSON evaluation.

## 3. Architecture and compliance boundary

Qwen2.5:7B produces a short move/grasp/move/place plan. Deterministic skills then
resolve stations, select objects, plan base motion, and invoke the official
physics backend. Verification is isolated from runtime and reads the final ZIP
bytes only.

The final tree observes this boundary:

| Area | Status | Role |
|---|---|---|
| `app.py`, `knowledge/task_config.json`, `src/robot_agent/core/`, `src/robot_agent/environments/` | No Git content diff from pinned official commit | Locked runtime |
| Shared official robosuite files and generated maps present in the submission | No Git content diff | Simulator baseline |
| `src/robot_agent/skills/` | Participant edits | Geometry, navigation staging, multi-object continuity |
| `knowledge/robot_params.json` | Participant-editable | Controller parameters |
| `pipeline/`, `verify_submission.py` | Added tooling | Runs, scoring, packaging, integrity |

An earlier draft placed the clearance ladder in forbidden `core/map_loader.py`
and `core/navigation.py`. The final implementation relocates the same planning
policy to `skills/move.py` and restores the entire core directory to the pinned
official version.

The comparison is content-based and intentionally ignores checkout-only LF/CRLF
conversion on Windows; raw on-disk SHA-256 is therefore not used for this claim.

## 4. Method

### 4.1 Exact auxiliary-station resolution

`output_1` is a substring of `aux_output_1`, and similarly for input names. The
resolver therefore checks an exact known name first, then embedded names in
decreasing length order. This prevents L3/L5 from navigating to an ordinary port
when the plan correctly specifies an auxiliary port.

```python
names = scene.all_port_names()
exact = target.strip()
if exact in names:
    return station_goal(exact)
for name in sorted(names, key=len, reverse=True):
    if name in target:
        return station_goal(name)
```

### 4.2 Runtime geometry-derived grasp frame

The official BC checkpoint remains the first attempt in fallback mode. If it
fails, a deterministic expert invokes the official collector’s physical lift,
XY approach, descent, settle, close, and post-grasp lift primitives.

For object centre `c` and official right/left model sites `s_R`, `s_L`:

```text
u = normalize((s_R + s_L)/2 - c)
b = c + 0.941 u
```

For a blocked standing side, the skill uses:

```text
u' = Rz(theta) u
p_R,L = c + 0.315 u' ± 0.11 Rz(90°)u'
```

`theta` is `+90°` for selected L2/L5 totes and `-90°` for selected L3
right-side totes. These are controller targets for the current call. The code
does not rewrite XML sites, task config, maps, or trajectory frames.

### 4.3 Skill-layer clearance ladder and physical staging

`skills/move.py` creates temporary in-memory occupancy views with margins
`0.45 → 0.30 → 0.15 → 0.0 m`. Start and goal neighborhoods are restored from
the official grid so a legitimate station approach is not removed. The final
stage is exactly the unmodified official grid.

Before grasping, the base moves to a point `0.65 m` behind the computed pose,
turns through the official turn controller, and follows a short straight physical
approach. L5 keeps `0.10 m` additional table clearance. This avoids sweeping an
extended arm through a table during a large turn and preserves the relative
base/object frame used by the official backend.

### 4.4 L5 state continuity and three physical drops

The official grasp helper uses a wrapped environment and synchronizes every
material object back afterward. In a three-object task, that blanket sync can
overwrite earlier placements. `PickUpSkill` snapshots only non-target free-joint
states before the official call and restores those same non-target states after
it. It does not move the selected target, declare grasp success, or write
transport attachment state.

The three place calls use target-centre lateral offsets `0`, `+0.38`, and
`-0.38 m`. Only temporary station metadata consumed by the official place
controller is changed, then immediately restored. Physics determines the final
object pose.

## 5. Revised Novelty Statement

The previous report overstated several claims. This revision does **not** claim
a new imitation-learning algorithm, a general proof of safety, or unsupported
SOTA/latency/ablation numbers. Its innovation claims are narrower and directly
traceable:

1. **Runtime site-relative grasp-frame synthesis** — official model sites become
   measurements rather than files to patch; one formulation supports natural
   and rotated approaches across L2, L3, and L5.
2. **Physically consistent two-stage base positioning** — a skill-local
   clearance ladder, safe staging pose, official physical turn, and straight
   approach jointly address collision exposure and frame consistency without
   attachment mutation.
3. **Transaction-scoped multi-object continuity** — non-target state
   preservation prevents later wrapped grasps from erasing earlier placements;
   three target-table points turn a single-object primitive into an L5 sequence.
4. **Versioned evidence chain** — the official commit, accepted candidates, ZIP
   members, raw/package hashes, and independently recomputed scores are checked
   together, making stale-task success and trajectory post-processing detectable.

| Baseline gap | Added mechanism | Direct evidence |
|---|---|---|
| BC distribution shift | Site-relative deterministic fallback | Successful official grasp/lift events for selected L2–L5 objects |
| Table-adjacent approach | Skill-local clearance ladder and staged motion | Zero collision markers in all five final trajectories |
| Wrapped reset during L5 | Non-target transaction plus three drop points | Three named grasp events and three target placements |
| Stale local scoring | Commit-pinned verifier and SHA-256 report | Exact 65 reproduction, followed by 100 on the final set |

## 6. Experimental protocol

The canonical set contains one successful simulator trajectory per level. L1,
L2, and L4 retain valid earlier trajectories because their routes did not
change. L3 and L5 were rerun using the corrected routes.

For every level, `verify_submission.py`:

1. requires exactly `trajectory.json`, `score.json`, and
   `submission_manifest.json`;
2. validates the manifest’s official commit and level;
3. hashes package and trajectory bytes;
4. recomputes the score using strict current candidates;
5. requires reported score, recomputed score, and level maximum to agree.

The verifier does not need an LLM, MuJoCo, GPU, or rendering. This makes the
rescore deterministic, but it does not replace final organizer review.

## 7. Results

| Level | Maximum | Previous | Final | Delta |
|---|---:|---:|---:|---:|
| L1 | 10 | 10 | 10 | 0 |
| L2 | 15 | 15 | 15 | 0 |
| L3 | 20 | 0 | 20 | +20 |
| L4 | 25 | 25 | 25 | 0 |
| L5 | 30 | 15 | 30 | +15 |
| **Total** | **100** | **65** | **100** | **+35** |

Recorded evidence from the final packages:

| Level | Selected object(s) | Frames | Recorded span | Final target distance |
|---|---|---:|---:|---|
| L1 | `line_5_container_h01_near` | 1308 | 66.25 s | 0.11 m |
| L2 | `green_tote_b01_lower` | 1153 | 52.05 s | 0.09 m |
| L3 | `blue_tote_b01_far_right` | 1915 | 110.87 s | 0.05 m |
| L4 | `blue_container_h01_back_upper` | 1842 | 85.20 s | 0.15 m |
| L5 | centre/front/back left white totes | 8211 | 438.03 s | 0.19 / 0.36 / 0.38 m |

No final packaged trajectory contains `judge_collision_detected` or a true
collision marker.

These numbers are not presented as controlled per-component ablations. The
old-to-final comparison is an end-to-end correction with two known causal
defects: L3 task alignment and L5 target/multi-object alignment.

## 8. Integrity and reproducibility

- Packaged `trajectory.json` is a byte-for-byte copy of the raw simulator
  `trajectory_*_OK.json`.
- Packaging writes only `score.json` and `submission_manifest.json` around it.
- Participant skills do not write the official transport-attachment structure.
- Machine-readable hashes and results are in
  `submission_100_final_129e94a9/verification_report.json`.
- Combined archive SHA-256:
  `a866718e44314ce5ffe7844a3b8a4d8b060765c077a8b6ff056d0d19a33cb8c0`.

Verification command:

```powershell
JCIIOT\.venv\Scripts\python.exe verify_submission.py `
  --submissions submission_100_final_129e94a9
```

Expected result: five `PASS` rows and `TOTAL 100/100`.

## 9. Traceability

| Claim | Implementation |
|---|---|
| Live/rotated grasp geometry | `skills/scripted_grasp.py` |
| Exact auxiliary names and clearance ladder | `skills/move.py` |
| Safe staging and non-target transaction | `skills/pick_up.py` |
| Three L5 target points | `skills/place_down.py` |
| Strict current candidate scoring | `pipeline/score_trajectory.py` |
| ZIP, manifest, score, and hash checks | `verify_submission.py` |

## 10. Limitations

1. The 100/100 result is one selected trajectory per level, not a repeated-trial
   success-rate estimate.
2. Rotated approach constants are validated on named competition objects, not
   arbitrary unseen geometry.
3. Non-target restoration compensates for the official wrapper’s blanket sync;
   a target-only backend synchronization API would be cleaner.
4. Static occupancy maps do not cover dynamic obstacles.
5. Final acceptance remains subject to organizer code audit.

## Conclusion

The 65-point discrepancy was the exact consequence of stale task routing, not
evidence of edited trajectory JSON. The corrected system recomputes to 100/100
while preserving official core, environment, task, and map files. The revised
innovation is an auditable set of skill-layer mechanisms: runtime grasp-frame
synthesis, clearance-aware staged motion, transaction-scoped multi-object
continuity, and integrity-bound verification.
