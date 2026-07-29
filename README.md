#  "RunningRobot" — Team BIPT-EDU Submission

**Final objective score: 100 / 100 (L1 10 + L2 15 + L3 20 + L4 25 + L5 30, zero collisions)**

This repository is the complete competition submission of team **BIPT-EDU**:
reproducible code, the five official trajectory packages, a technical report with
a dedicated Novelty Statement, and video demonstrations of all five levels.
**Every deliverable sits at the repository root or one folder deep.**

---

## 1. Submission Contents (per official requirements)

| Requirement | Where |
|---|---|
| **Five official deliverable ZIPs** (one per level: `trajectory.json` + `score.json` + `submission_manifest.json`) | [`submissions/`](submissions/) — `L1_20260723_213458.zip` … `L5_20260723_213501.zip` |
| **Technical report** (Technology Description · Novelty Statement · Results & Analysis) | [`paper.pdf`](paper.pdf) (full report, root) · Markdown version [`TECHNICAL_SOLUTION.md`](TECHNICAL_SOLUTION.md) · LaTeX sources in [`paper/`](paper/) |
| **Reproducibility** | [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) + [`verify_submission.py`](verify_submission.py) — one command re-scores all five trajectories to 100/100 |
| **Video demonstration** | [`videos/`](videos/) — follow + birdview MP4 renders of L1–L5 (10 files) |
| **Reproducible code** | [`JCIIOT/`](JCIIOT/) — full runnable pipeline; [`source_code/`](source_code/) — curated view of just the participant-modified layers |
| **Defense material** | [`defense/`](defense/) — slides + expert Q&A |

## 2. Verify the Reported 100/100 in Seconds (no GPU, no LLM)

```powershell

powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1     # one-time: uv venv + pinned deps
cd ..
JCIIOT\.venv\Scripts\python.exe verify_submission.py
```

Expected output: every level `PASS`, `TOTAL 100/100`. This re-scores the five
ZIPs in `submissions/` with the exact objective rule
(`grasp_success_gate_l5_multi_v2`, implemented in `JCIIOT/pipeline/score_trajectory.py`).

## 3. Full End-to-End Re-run

Two large binaries are gitignored (upstream Git-LFS quota exhaustion made LFS
unreliable) and restored with sha256 verification from the official repository:

```powershell

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
robosuite/MuJoCo baseline, with all improvements confined to the
participant-editable layers:

- **Scripted-expert grasp fallback** (`source_code/skills/scripted_grasp.py`) —
  BC policy first, deterministic collector-primitive fallback on failure.
- **Rotated east-wall virtual grasp sites** — makes the geometrically blocked
  L2/L5 left-group totes reachable.
- **Transport offset normalization** (`source_code/skills/pick_up.py`) — clamps
  the carry offset so placement releases over the target station.
- **Graduated A\* obstacle inflation with endpoint exemption**
  (`source_code/core/navigation.py`) — 0.45→0 m margin ladder; zero collision
  frames across all five submitted trajectories.
- **Erratum-synced task configs** — official docx rulings (e.g. L3 blue bin,
  side-table pick point) pinned into canonical prompts.

Details, ablations, prior-work comparison: see the **Novelty Statement** section
of [`paper.pdf`](paper.pdf).

## 5. Repository Layout (deliverables at depth ≤ 2)

```
├── README.md                ← this file (start here)
├── paper.pdf                ← technical report (PDF)
├── TECHNICAL_SOLUTION.md    ← technical report (Markdown)
├── REPRODUCIBILITY.md       ← how to reproduce 100/100
├── verify_submission.py     ← one command re-scores all five ZIPs
├── submissions/             ← ★ the FIVE official ZIPs (L1–L5)
├── videos/                  ← L1–L5 demos (follow + birdview MP4)
├── paper/                   ← LaTeX sources + figures for paper.pdf
├── defense/                 ← defense slides + expert Q&A
├── source_code/             ← curated participant-modified layers only
│                              (core / skills / environments / pipeline)
├── JCIOT/                  ← full runnable project (agent, robosuite fork,
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

**Team:** BIPT-EDU · **Competition:**   "RunningRobot" (Tsinghua CS ×
Siemens Industrial Intelligence & IoT Joint Research Center)
