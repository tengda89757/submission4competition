# Reproducibility Guide — JCIIOT 2026 RunningRobot (Team BIPT-EDU)

This document lets an evaluator **reproduce our reported results (100/100)** with
minimal friction. It describes the exact environment, dependencies, and commands.

There are two reproduction paths:

| Path | What it proves | Needs LLM? | Needs GPU? | Time |
|------|----------------|:---------:|:----------:|------|
| **A. Verify reported scores** (recommended first) | The five submitted trajectories objectively score 10/15/20/25/30 = **100** under the official rule | No | No | seconds |
| **B. Full end-to-end re-run** | The agent regenerates trajectories from scratch and re-achieves the scores | Yes (Ollama) | Recommended | ~minutes/level |

> Path A is **deterministic** and self-contained (only needs the scene maps + the
> trajectory). Path B exercises the whole planning+control stack; because the LLM
> planner and physics contacts are stochastic, individual runs may vary, which is
> why the **canonical, per-level task prompts and object rulings are pinned** (see
> §6) so a passing run is reproducible.

---

## 1. System Requirements

- **OS:** Windows 10/11 (the automation scripts are PowerShell). Path A (Python
  verification) is OS-agnostic and also runs on Linux/macOS.
- **Python:** 3.11 (installed automatically by `uv`).
- **Package manager:** [`uv`](https://github.com/astral-sh/uv) (fast, reproducible installs).
- **GPU (Path B):** NVIDIA GPU with CUDA 12.x recommended for PyTorch/BC inference;
  a CPU-only fallback is supported (`setup_env.ps1 -Cpu`).
- **LLM planner (Path B):** [Ollama](https://ollama.com) serving `qwen2.5:7b` at
  `http://localhost:11434`.
- **Renderer:** MuJoCo 3.9.0. On Windows leave `MUJOCO_GL` **unset** (uses `wgl`);
  on Linux set `MUJOCO_GL=egl` for headless GL.

Everything else (the robosuite v1.5.2 fork with the FactorySorting scenes, the
Behavior-Cloning weights `model_epoch_150.pth`, `robomimic`, all meshes/maps) ships
inside the project repository — no external downloads are required at run time.

---

## 2. One-Time Environment Setup

From the project root `JCIIOT2026-master/JCIIOT/`:

```powershell
# creates .venv (Python 3.11), installs CUDA torch 2.7.0, the pinned deps,
# then editable robosuite + robot-agent; freezes exact versions to
# pipeline/requirements.resolved.txt
powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1

# variants:
powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1 -TorchIndex cu128   # 50-series / Blackwell GPUs
powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1 -Cpu                 # CPU-only PyTorch
```

The script verifies the toolchain and prints the resolved `numpy / mujoco / torch /
cuda` versions. The resulting interpreter is `JCIIOT\.venv\Scripts\python.exe`.

**Dependencies** are pinned in [`requirements.txt`](../../requirements.txt) (key
versions: `mujoco==3.9.0`, `numpy==1.26.4`, `torch==2.7.0`, `robosuite_models==1.0.0`,
`streamlit==1.58.0`) and the fully-resolved lockfile is written to
`pipeline/requirements.resolved.txt` after setup.

---

## 3. Path A — Verify the Reported Scores (deterministic, recommended)

This re-scores every submitted trajectory with the **exact** objective rule used
during the competition (`score_rule_version = grasp_success_gate_l5_multi_v2`,
implemented in `pipeline/score_trajectory.py`) and checks it against the
`score.json` packaged inside each ZIP and against the level maximum.

```powershell
# from the repository root
JCIIOT\.venv\Scripts\python.exe verify_submission.py
```

Expected output:

```
Level Package                      Reported  Recomputed  Max  Result
--------------------------------------------------------------------------
L1    L1_20260803_141824.zip             10          10   10  PASS
L2    L2_20260803_141825.zip             15          15   15  PASS
L3    L3_20260803_141826.zip             20          20   20  PASS
L4    L4_20260803_141827.zip             25          25   25  PASS
L5    L5_20260803_141828.zip             30          30   30  PASS
--------------------------------------------------------------------------
TOTAL                                   100         100  100

RESULT: [OK] All five levels reproduce their reported scores. Total = 100/100.
```

To score a single trajectory manually:

```powershell
.venv\Scripts\python.exe pipeline\score_trajectory.py --trajectory <path\to\trajectory.json> --level L1
# L3 current official candidates are the right-side blue transfer bins:
.venv\Scripts\python.exe pipeline\score_trajectory.py --trajectory <L3 traj.json> --level L3 --object blue_tote_b01_near_right
```

This path needs **no GPU, no LLM, no rendering** — only the scene maps bundled in
the robosuite fork.

---

## 4. Path B — Full End-to-End Re-run

Regenerates a trajectory by running the unified RobotAgent (plan → navigate →
grasp → place) headlessly, then scores it. Requires Ollama serving `qwen2.5:7b`.

```powershell
# start the planner once
ollama serve            # in a separate shell
ollama pull qwen2.5:7b

# run one level end-to-end with the canonical prompt, then score it
powershell -ExecutionPolicy Bypass -File pipeline\run_level.ps1 -Level L1 -Canonical -Score
# ... repeat for L2 L3 L4 L5

# or run + score + package every level in one shot
powershell -ExecutionPolicy Bypass -File pipeline\finalize_all.ps1
```

`run_level.ps1` writes the trajectory to `recordings\<Scene>\trajectory_<ts>_OK.json`
and (with `-Score`) a `score_<ts>.json` next to it. `finalize_all.ps1` additionally
packages each level into `pipeline\submissions\`.

**Per-level notes** (baked into the scripts so runs are reproducible):

- The task definition is pinned to official commit `129e94a9cff787031472045e19c24a4baeaefc48`.
- L3 runs `aux_input_1 → output_5` and grades
  `blue_tote_b01_far_right` / `blue_tote_b01_near_right`.
- L5 runs `input_1 → aux_output_1` and transports the three
  `white_tote_b01_left_*` bins one at a time in a fixed order.
- The BC checkpoint defaults to the official `model_epoch_150.pth`; `run_level.ps1
  -Checkpoint <path>` selects another.

---

## 5. What Each Submission ZIP Contains

The canonical final packages are in `submission_100_final_129e94a9/` and are
mirrored in `submissions/` for the default verifier. Each ZIP contains exactly:

- `trajectory.json` — full per-frame state log (base pose, joint angles, object poses, grasp events).
- `score.json` — objective breakdown under `grasp_success_gate_l5_multi_v2`.
- `submission_manifest.json` — level, `env_name`, method summary, source-trajectory path.

`verify_submission.py` reads `trajectory.json` + `score.json` straight from these ZIPs.

---

## 6. Determinism & Notes

- **Scoring is deterministic.** Given a trajectory, `score_trajectory.py` returns
  the same result every time (pure geometry over the recorded frames).
- **Canonical prompts** (verbatim in `run_level.ps1`) remove LLM station-name
  mapping fragility; the same instruction is sent every run.
- **Stochasticity in Path B** comes from (a) the LLM planner and (b) MuJoCo contact
  dynamics during grasp/place. The scripted-expert fallback
  (`skills/scripted_grasp.py`) makes grasping robust, but if a single run under-scores,
  re-running the level reproduces the reported result. The submitted trajectories are
  the archived passing runs.
- **Reproducing the objective 100/100 does not require Path B** — Path A verifies the
  exact submitted artifacts.

---

## 7. Repository Layout (deliverables at depth ≤ 2)

```
<repository root>/
├── README.md                           start here
├── REPRODUCIBILITY.md                  this guide
├── verify_submission.py                one-command 100/100 verification (Path A)
├── paper.pdf                           technical report (PDF)
├── TECHNICAL_SOLUTION.md               technical report (Markdown)
├── submissions/                        the FIVE official L1..L5_*.zip deliverables
├── videos/                             L1–L5 demo MP4s (follow + birdview)
├── paper/                              LaTeX sources + figures for paper.pdf
├── defense/                            defense slides + expert Q&A
├── source_code/                        curated view of the participant-edited layers
└── JCIIOT/                             full runnable project
    ├── .venv/                          created by setup_env.ps1
    ├── requirements.txt                pinned dependencies
    ├── src/robot_agent/                unified RobotAgent (planner, skills, backend, runner)
    ├── robosuite/                      v1.5.2 fork: FactorySorting scenes, maps (BC weights via fetch_assets.ps1)
    ├── robomimic/                      vendored (BC training/inference)
    ├── knowledge/task_config.json      per-level scene/source/target/object config
    └── pipeline/
        ├── setup_env.ps1               environment bootstrap
        ├── fetch_assets.ps1            sha256-verified download of gitignored large assets
        ├── run_level.ps1               headless single-level run + score
        ├── finalize_all.ps1            run + score + package all levels
        ├── score_trajectory.py         objective scorer (grasp_success_gate_l5_multi_v2)
        ├── patch_grasp_pose.py         per-scene grasp-pose calibration
        └── requirements.resolved.txt   frozen exact versions (after setup)
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `venv missing — run pipeline\setup_env.ps1 first` | Run §2 setup. |
| `invalid value for environment variable MUJOCO_GL: egl` (Windows) | `Remove-Item Env:\MUJOCO_GL` — Windows uses `wgl`. |
| MuJoCo offscreen render access denied / GL error | Ensure a real GPU/GL context is available; Path A (verification) needs no rendering. |
| Path B planning stalls | Confirm `ollama serve` is up and `qwen2.5:7b` is pulled at `http://localhost:11434`. |
| `torch.cuda.is_available() == False` | Reinstall with the matching CUDA wheel (`-TorchIndex cu126`/`cu128`) or use `-Cpu`. |

---

**Bottom line:** run **§3 Path A** (`verify_submission.py`) for a few-second,
dependency-light confirmation that every submitted trajectory objectively scores
the reported total of **100/100**; use **§4 Path B** to regenerate trajectories
end-to-end.
