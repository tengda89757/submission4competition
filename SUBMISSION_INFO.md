# JCIIOT 2026 "RunningRobot" — Official Submission Information

## 基本信息 / Basic Information

| 项目 / Item | 内容 / Content |
|---|---|
| **参赛队伍 / Team** | BIPT-EDU |
| **竞赛 / Competition** | JCIIOT 2026 "RunningRobot" (Tsinghua CS × Siemens Industrial Intelligence & IoT Joint Research Center) |
| **代码仓库 / Repository Link** | <https://github.com/tengda89757/submission4competition> |
| **最终客观得分 / Final Objective Score** | **100 / 100** (L1 10 + L2 15 + L3 20 + L4 25 + L5 30, zero collisions) |
| **提交日期 / Submission Date** | 2026-08-03 |
| **官方基准 / Official Reference** | `129e94a9cff787031472045e19c24a4baeaefc48` |

## 方法摘要 / Method Summary

Unified RobotAgent (LLM plan → navigate → grasp → place) over the official
robosuite/MuJoCo baseline, with all improvements confined to the
participant-editable layers:

1. **Scripted-expert grasp fallback** — BC policy first, deterministic
   collector-primitive fallback on failure (`skills/scripted_grasp.py`).
2. **Live geometry-derived approach poses** — computes reachable base poses
   from current object/grasp-site geometry, including rotated L3/L5 approaches.
3. **Physical staging and exact auxiliary-station resolution** — uses A*,
   turning and straight approach motions without mutating attachment state.
4. **Graduated A\* obstacle inflation with endpoint exemption** — 0.45→0 m
   margin ladder; zero collision frames across all five submitted trajectories
   (`core/navigation.py`).
5. **Official-current routing** — L3 `aux_input_1 → output_5`; L5
   `input_1 → aux_output_1`, pinned to official commit `129e94a9`.

## 交付物清单 / Deliverables

| 官方要求 / Requirement | 位置 / Location (repository) |
|---|---|
| 五个关卡轨迹包 / Five final ZIPs | `submission_100_final_129e94a9/L1_20260803_141824.zip` … `L5_20260803_141828.zip` (mirrored in `submissions/`) |
| 可复现代码 / Reproducible code | `JCIIOT/` (full pipeline) + `source_code/` (participant-modified layers) |
| 技术报告 / Technical report | `paper.pdf` (PDF) + `TECHNICAL_SOLUTION.md` (Markdown), incl. dedicated **Novelty Statement** and **Results & Analysis** |
| 复现指南 / Reproducibility | `REPRODUCIBILITY.md` + `verify_submission.py` |
| 视频演示 / Video demonstration | `videos/` — L1–L5, follow + birdview MP4 (10 files) |

## 一键验证 / One-Command Verification

评估人员无需 GPU / LLM / 渲染，数秒内即可复核 100/100
(Evaluators can confirm 100/100 in seconds — no GPU, no LLM, no rendering):

```powershell
cd JCIIOT
powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1   # one-time env setup
cd ..
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

完整端到端重跑（LLM 规划 → 导航 → 抓取 → 放置）见仓库 `REPRODUCIBILITY.md` §4
(For a full end-to-end re-run, see `REPRODUCIBILITY.md` §4 in the repository).

## 备注 / Notes

- 两个大体积二进制（BC 权重 139 MB、演示数据集 564 MB）未入库，评估时由
  `JCIIOT/pipeline/fetch_assets.ps1` 从官方仓库下载并做 sha256 校验
  (Two large binaries are restored from the official repository with sha256
  verification via `fetch_assets.ps1`).
- 评分规则版本 / Score rule version: `grasp_success_gate_l5_multi_v2`
  (identical to the official dashboard scorer).
- 第三方组件 / Third-party components: MuJoCo 3.9.0, robosuite v1.5.2 (fork,
  provided baseline), robomimic (vendored), PyTorch 2.7.0, Ollama + Qwen2.5-7B,
  uv. Full pinned list in `JCIIOT/requirements.txt`.
