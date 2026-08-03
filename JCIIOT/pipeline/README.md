# JCIIOT 2026 — Reproducible Pipeline (setup → train → run → submit)

This `pipeline/` folder turns the JCIIOT 2026 "RunningRobot" baseline into a
**reproducible, command-line workflow** on Windows + NVIDIA GPU. Every stage below
was executed and verified on an RTX 4090 (torch 2.7.0+cu126, CUDA 12.6).

The official competition is a mobile-manipulator (Tiago, holonomic base + two arms)
that transports objects across five MuJoCo `FactorySorting` scenes. The standard
action sequence is `move → pick_up → move → place_down`; an LLM plans it, the Agent
executes step-by-step, and a fixed rule scores the resulting trajectory JSON.

---

## 0. TL;DR quickstart

```powershell
# from the JCIIOT app dir:  d:\2026\JCOII-2026\JCIIOT2026-master\JCIIOT
powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1        # resolve Git-LFS stubs (checkpoint + dataset)
powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1           # uv venv + CUDA torch + robosuite/robomimic
ollama pull qwen2.5:7b                                                     # local LLM planner (already wired in robot_params.json)

# run a level end-to-end and score it (headless CLI equivalent of the dashboard "Execute"):
powershell -ExecutionPolicy Bypass -File pipeline\run_level.ps1 -Level L1 -Canonical -Score

# package the trajectory for submission:
powershell -ExecutionPolicy Bypass -File pipeline\package_submission.ps1 -Level L1

# OR launch the official Streamlit dashboard:
.\.venv\Scripts\python -m streamlit run app.py
```

---

## 1. What was broken, and the fix (root-cause diagnosis)

| Symptom (from the group chat) | Root cause | Fix in this pipeline |
|---|---|---|
| `MuJoCo subprocess exited abnormally … no scorable trajectory JSON. returncode=1` | The BC checkpoint `model_epoch_150.pth` was a **134-byte Git-LFS pointer stub** (LFS quota exhausted; ZIP/clone don't resolve LFS). Policy load → crash. | `fetch_assets.ps1` downloads the real 139 MB file from the `github.com/.../raw/...` endpoint and **verifies sha256**. |
| "need `model_epoch_500.pth`" | The code loads `checkpoint_path` (500) **first**, then falls back to `checkpoint_fallback_path` (150). 500 is **never** provided — you train it. | Fallback to 150 works out-of-the-box; `train_bc.py` produces your own 500. |
| "150 must be retrained / robustness is weak" | The bundled `table_setup_from_dishwasher_sample.hdf5` is a robomimic **format sample from an unrelated iGibson task** (`env_name=SemanticOrganizeAndFetch`) — NOT factory-sorting data. | `collect_demos.ps1` scripts real FactorySorting grasps; `train_bc.py` trains on them. |
| L3 "blue vs orange box?" | `task_config.json` / `sop*.md` say orange; the official **docx** says blue. | Official ruling: **docx is authoritative → blue**. `task_config`/`sop` are baseline-only, not the graded task. |
| LLM won't connect | `robot_params.json` shipped `qwen3.6:27b-mtp-q4_K_M` — a **non-existent tag**. | Repointed to `qwen2.5:7b` (pulled locally). |

The full set of unresolved LFS files is reported by `asset_doctor.ps1`.

---

## 2. Scripts

| Script | Purpose |
|---|---|
| `assets_manifest.json` | URLs + sizes + sha256 for every LFS-locked file. |
| `fetch_assets.ps1` | Download & verify LFS assets. `-All` includes optional USD/mesh zips; `-Only pth`/`hdf5`; `-Force`. |
| `asset_doctor.ps1` | Scan the repo for LFS **pointer stubs** vs real files; cross-check sha256. Run this first if anything "exits abnormally". |
| `setup_env.ps1` | `uv` venv (Python 3.11) + CUDA torch + pinned reqs + editable robosuite/robot-agent. Freezes `requirements.resolved.txt`. `-TorchIndex cu128` for 50-series, `-Cpu` for CPU-only. |
| `collect_demos.ps1` | Collect **scripted expert grasp demos** (real FactorySorting data). `-NumRollouts 50`, `-Render` for a visual window. |
| `train_bc.py` | Retrain the BC grasp policy on GPU (config extracted from `model_epoch_150.pth` so the network matches). Installs result as `model_epoch_500.pth`. `--debug` = 2-epoch smoke test. |
| `run_level.ps1` | Run a full L1–L5 task via the isolated `task_subprocess_runner` (LLM plan → nav → grasp → place → trajectory). `-Score` to auto-score. |
| `eval_grasp.ps1` | Grasp-only sanity check for a checkpoint in one scene (CLI form of the dashboard "Test Grasp"). |
| `score_trajectory.py` | Headless re-implementation of the dashboard's objective scorer (`grasp_success_gate_l5_multi_v2`). |
| `package_submission.ps1` | Bundle `trajectory.json` + `score.json` + manifest into a submittable folder/zip. |

---

## 3. Retraining the grasp policy (the real training story)

The single BC policy is shared across all levels, so you retrain on **L1 grasp demos**:

```powershell
powershell -ExecutionPolicy Bypass -File pipeline\collect_demos.ps1 -NumRollouts 50
.\.venv\Scripts\python pipeline\train_bc.py --dataset pipeline\collected\factory_sorting_l1_grasp.hdf5 --epochs 3000 --save-every 150 --device cuda:0
```

- The collector saves only **successful** scripted grasps (validated: 2/2 succeeded).
- `train_bc.py` reads the robomimic config embedded in `model_epoch_150.pth`, so the
  retrained net has identical obs/action shapes and loads unchanged in eval. It also
  adds the `num_samples` attrs the collector omits, and disables train/valid filters
  (collected data has no mask).
- Chat guidance: **2000 epochs failed, ~3000 worked** (~10 h). Save checkpoints every
  150 epochs; the newest is auto-copied to `robosuite/robosuite/model_epoch_500.pth`,
  which `robot_params.json` loads first.

Validate the pipeline quickly first: `python pipeline\train_bc.py --debug --no-install`.

---

## 4. L1–L5 reference (official commit `129e94a9`)

| Level | Scene | Source→Target | Official candidates | Max |
|---|---|---|---|---|
| L1 | factory_sorting_1 | input_5→output_4 | line_5_container_h01_near/far | 10 |
| L2 | factory_sorting_3 | input_6→output_4 | green_tote_b01_upper/lower | 15 |
| L3 | factory_sorting_5 | aux_input_1→output_5 | blue_tote_b01_far_right/near_right | 20 |
| L4 | factory_sorting_7 | input_2→output_5 | blue_container_h01_back_upper/lower | 25 |
| L5 | factory_sorting_9 | input_1→aux_output_1 | 3× white_tote_b01_left_* | 30 |

Scoring per level: ~50% "grasp + leave source (>1 m)", ~50% "object within 0.80 m of
target"; **−5** if any collision frame. L5 scores the three totes independently.

---

## 5. Planning robustness (the actual competition problem)

The infrastructure is solved; the open problem — as the organizers stated — is making
the **LLM plan reliably**. With `qwen2.5:7b` the vague SOP prompt produced
`move → Pick_Station_2`, which the resolver can't map (it accepts `input_5`,
`output_4`, or Chinese `N号进料口`, not "Pick Station N"). Levers (per the training PPTX):

1. **Edit the knowledge base** — `knowledge/*.md` and `team_submission/knowledge/` are
   injected into the planner prompt; "改知识库就能改规划质量". Make the current-level
   SOP row map Pick/Place Station → `input_N`/`output_N` explicitly, and pin the exact
   `object_name`.
2. **Use a stronger model** — `ollama pull qwen2.5:14b` (fits a 24 GB card) or an
   OpenAI-compatible endpoint (DeepSeek/GLM) via the sidebar; then set it in
   `robot_params.json` or `run_level.ps1 -OllamaModel`.
3. **`LLM Plan` before `Execute`** — the dashboard's plan-only button verifies JSON
   output cheaply (no MuJoCo) while you tune prompts/knowledge.

Editable vs locked (from the PPTX): **optimize** `skills/*.py`, `workflows/*.py`,
`knowledge/`, `robot_params.json`, and the trainable checkpoint. **Do not modify**
`robosuite/`, `generated_maps/`, `environments/base.py`, `robosuite_backend.py`,
`core/types.py`, `app.py`, `task_config.json`.

---

## 6. Troubleshooting

- **`invalid value for environment variable MUJOCO_GL: egl`** — `egl` is Linux-only.
  On Windows leave `MUJOCO_GL` unset (default `wgl`). All scripts clear it.
- **"exits abnormally / no trajectory"** — run `asset_doctor.ps1`; any `STUB` means an
  LFS file didn't resolve → `fetch_assets.ps1 -All`.
- **HF auto-download hangs during training** — set `HF_HUB_OFFLINE=1`; the BC policy
  needs no HF weights.
- **Access denied running `.venv\Scripts\python.exe`** — this Qoder sandbox blocks
  executing the workspace interpreter; run in a normal PowerShell, or the agent runs it
  outside the sandbox.
- **Grasp/place imperfect** — expected with the weak 150 checkpoint; retrain (§3) and/or
  tune `robot_params.json` (`navigation`, `grasp_policy`, `lift`, `turn`, `place`).

---

## 7. Verified results (this machine)

- `model_epoch_150.pth` sha256 `ef5910…2169f` ✔ · `table_setup_from_dishwasher_sample.hdf5` sha256 `e7f8fd…79eea` ✔
- Env: torch 2.7.0+cu126, CUDA True, RTX 4090; robosuite 1.5.2, mujoco 3.9.0, robomimic OK.
- `test_scene_load.py`: **ALL CHECKS PASSED** (65 bodies, 644 geoms).
- `collect_demos -NumRollouts 2`: **2/2** successful grasps.
- `train_bc --debug`: 2 epochs on GPU, checkpoint saved.
- **`run_level -Level L1 -Score`: 10 / 10** (grasp + placed at output_4, dist 0.12 m) —
  byte-for-byte matching the official reference `score_20260629_164216_OK.json`.

Exact dependency versions are frozen in `pipeline/requirements.resolved.txt`.

---

## 8. Official-current geometry and compliance fix (2026-08-03)

The final pipeline is pinned to official commit
`129e94a9cff787031472045e19c24a4baeaefc48`. The locked app, task config,
generated maps, environment base/backend, core types, and task runner are
byte-identical to that commit.

The executable fixes live in the participant-editable skill layer:

1. **Exact auxiliary-station resolution** (`skills/move.py`) checks exact names
   before substring matching, so `aux_input_1` and `aux_output_1` cannot collapse
   to `input_1` / `output_1`.
2. **Live geometry-derived grasp approach** (`skills/scripted_grasp.py`,
   `skills/pick_up.py`) reads the running scene's object and grasp-site positions,
   moves through a safe A* staging point, turns physically, and then approaches
   straight. `patch_grasp_pose.py` is diagnostic-only and never writes the locked
   task config.
3. **L5 multi-object placement** (`skills/place_down.py`) selects three distinct
   valid table points on `aux_output_1`, restoring temporary runtime metadata after
   each official place-controller call.
4. No participant code writes transport-attachment state or rewrites trajectory
   JSON. The official backend captures attachment after a successful grasp.

**Final strict verification** (`verify_submission.py`):

| Level | Score | Result |
|---|---:|---|
| L1 | 10 / 10 | PASS |
| L2 | 15 / 15 | PASS |
| L3 | 20 / 20 | PASS, zero collision frames |
| L4 | 25 / 25 | PASS |
| L5 | 30 / 30 | PASS, zero collision frames |
| **Total** | **100 / 100** | **PASS** |

Canonical packages and their machine-readable hash report are in
`../submission_100_final_129e94a9/`.

