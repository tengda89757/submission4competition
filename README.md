# JCIIOT 2026 "RunningRobot" — Team BIPT-EDU Submission

**Final objective score: 100 / 100 (L1 10 + L2 15 + L3 20 + L4 25 + L5 30, zero collisions)**

The final set is pinned to official commit
[`129e94a9`](https://github.com/JCIIOT2026/JCIIOT2026/commit/129e94a9cff787031472045e19c24a4baeaefc48)
and has been independently re-scored from the packaged trajectories.

This repository is the complete competition submission of team **BIPT-EDU**:
reproducible code, the five official trajectory packages, a technical report with
a dedicated Novelty Statement, and video demonstrations of all five levels.
**Every deliverable sits at the repository root or one folder deep.**

---

## 1. Submission Contents (per official requirements)

| Requirement | Where |
|---|---|
| **Five final deliverable ZIPs** (one per level: `trajectory.json` + `score.json` + `submission_manifest.json`) | [`submission_100_final_129e94a9/`](submission_100_final_129e94a9/) — `L1_20260803_141824.zip` … `L5_20260803_141828.zip` (also mirrored in [`submissions/`](submissions/)); all-in-one handoff: [`submission_100_final_129e94a9.zip`](submission_100_final_129e94a9.zip) |
| **Technical report** (Technology Description · Novelty Statement · Results & Analysis) | [`paper.pdf`](paper.pdf) (full report, root) · Markdown version [`TECHNICAL_SOLUTION.md`](TECHNICAL_SOLUTION.md) · LaTeX sources in [`paper/`](paper/) |
| **Reproducibility** | [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) + [`verify_submission.py`](verify_submission.py) — one command re-scores all five trajectories to 100/100 |
| **Video demonstration** | [`videos/`](videos/) — follow + birdview MP4 renders of L1–L5 (10 files) |
| **Reproducible code** | [`JCIIOT/`](JCIIOT/) — full runnable pipeline; [`source_code/`](source_code/) — curated view of just the participant-modified layers |
| **Defense material** | [`defense/`](defense/) — slides + expert Q&A |

## 2. Verify the Reported 100/100 in Seconds (no GPU, no LLM)

```powershell
cd JCIIOT
powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1     # one-time: uv venv + pinned deps
cd ..
JCIIOT\.venv\Scripts\python.exe verify_submission.py
```

Expected output: every level `PASS`, `TOTAL 100/100`. This re-scores the five
ZIPs in `submissions/` with the exact objective rule
(`grasp_success_gate_l5_multi_v2`, implemented in `JCIIOT/pipeline/score_trajectory.py`)
and checks package membership, manifest reference, and hashes. See
[`SCORE_DIAGNOSIS.md`](SCORE_DIAGNOSIS.md) for the reproduced 65-point root cause.

## 3. Full End-to-End Re-run

Two large binaries are gitignored (upstream Git-LFS quota exhaustion made LFS
unreliable) and restored with sha256 verification from the official repository:

```powershell
cd JCIIOT
powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1   # BC checkpoint + demo dataset
ollama pull qwen2.5:7b                                                # local LLM planner
powershell -ExecutionPolicy Bypass -File pipeline\run_level.ps1 -Level L1 -Canonical -Score
```

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the full guide (system
requirements, per-level notes, troubleshooting) and
[`JCIIOT/pipeline/README.md`](JCIIOT/pipeline/README.md) for the complete
pipeline documentation (root-cause diagnoses, retraining, erratum sync).

## 4. Method Summary

Unified RobotAgent (LLM plan → navigate → grasp → place) over the official
robosuite/MuJoCo baseline. Runtime adaptations are confined to the skill and
pipeline layers; locked core/config/map files are byte-identical to the pinned
official commit:

- **Scripted-expert grasp fallback** (`source_code/skills/scripted_grasp.py`) —
  BC policy first, deterministic collector-primitive fallback on failure.
- **Live geometry-derived approach poses** (`source_code/skills/scripted_grasp.py`)
  — computes reachable base poses from the current object and grasp-site geometry,
  including the rotated L3/L5 approaches.
- **Physical staging and station disambiguation** (`source_code/skills/move.py`,
  `source_code/skills/pick_up.py`) — resolves `aux_*` names exactly, then uses A*,
  turning, and straight approach motions without mutating attachment state.
- **Distinct L5 release slots** (`source_code/skills/place_down.py`) — places the
  three white totes at separate valid points on `aux_output_1`.
- **Graduated A\* obstacle inflation with endpoint exemption**
  (`source_code/core/navigation.py`) — 0.45→0 m margin ladder; zero collision
  frames across all five submitted trajectories.
- **Official-current task routing** — L3 uses `aux_input_1 → output_5` and the
  right-side blue totes; L5 uses `input_1 → aux_output_1`, matching commit
  `129e94a9` and the published erratum.

Details, ablations, prior-work comparison: see the **Novelty Statement** section
of [`paper.pdf`](paper.pdf).

## 5. Repository Layout (deliverables at depth ≤ 2)

```
├── README.md                ← this file (start here)
├── paper.pdf                ← technical report (PDF)
├── TECHNICAL_SOLUTION.md    ← technical report (Markdown)
├── REPRODUCIBILITY.md       ← how to reproduce 100/100
├── SCORE_DIAGNOSIS.md       ← why the old package scored exactly 65/100
├── verify_submission.py     ← one command re-scores all five ZIPs
├── submission_100_final_129e94a9/ ← ★ canonical final ZIPs + verification report
├── submissions/             ← final ZIPs mirrored here for default verification
├── videos/                  ← L1–L5 demos (follow + birdview MP4)
├── paper/                   ← LaTeX sources + figures for paper.pdf
├── defense/                 ← defense slides + expert Q&A
├── source_code/             ← curated participant-modified layers only
│                              (core / skills / environments / pipeline)
├── JCIIOT/                  ← full runnable project (agent, robosuite fork,
│                              robomimic, knowledge base, pipeline scripts)
└── competition description/ ← official problem statement, SOPs, template
```

## 6. Third-Party Components

MuJoCo 3.9.0 · robosuite v1.5.2 (fork, provided baseline) · robomimic (vendored)
· PyTorch 2.7.0 · Ollama + Qwen2.5-7B (planner) · uv (env management) ·
python-docx / streamlit (tooling). Full pinned list:
[`JCIIOT/requirements.txt`](JCIIOT/requirements.txt) and
`JCIIOT/pipeline/requirements.resolved.txt`.

---

**Team:** BIPT-EDU · **Competition:** JCIIOT 2026 "RunningRobot" (Tsinghua CS ×
Siemens Industrial Intelligence & IoT Joint Research Center)
