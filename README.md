# JCIIOT 2026 RunningRobot — BIPT-EDU Submission

本提交提供 JCIIOT 2026 RunningRobot L1–L5 的完整技术实现与评测证据，包括官方提交包、逐帧轨迹、现实性审计、双视角录像和技术报告。

## Verified result

| Level | Score | Realism audit | Full-frame video |
|---|---:|---|---|
| L1 | 10/10 | PASS | 1,793 / 1,793 frames, PASS |
| L2 | 15/15 | PASS | 1,674 / 1,674 frames, PASS |
| L3 | 20/20 | PASS | 2,402 / 2,402 frames, PASS |
| L4 | 25/25 | PASS | 2,324 / 2,324 frames, PASS |
| L5 | 30/30 | PASS | 10,139 / 10,139 frames, PASS |
| **Total** | **100/100** | **5/5 PASS** | **18,332 / 18,332 frames** |

所有评测轨迹均满足：记录碰撞帧为 0、夹持物与其他物料的非预期接触帧为 0、夹持期间机械手接触率不低于 99%。最大底盘位移为 0.035113 m/帧，没有隔空取物、瞬间移动或源点到终点的物体传送。

## Start here

- Comprehensive technical report: [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md)
- Typeset technical report: [output/pdf/TECHNICAL_REPORT.pdf](output/pdf/TECHNICAL_REPORT.pdf)
- LaTeX source and template notes: [report/latex/](report/latex/)
- Official L1–L5 ZIPs and checksums: [submission/](submission/)
- Per-level trajectories, scores, and realism audits: [evidence/](evidence/)
- Full L1–L5 dual-view videos: [videos/](videos/)
- Aggregate results and verification reports: [results/](results/)
- Participant source overlay: [source_code/](source_code/)

## Verify

From the extracted bundle root:

```powershell
python verify_submission.py
```

The verifier uses only Python's standard library. It checks that exactly one ZIP exists for every level, validates SHA-256, recomputes the objective score from the official semantic-map centers, and verifies the pinned reference and manifest fields.

## Build the technical report

The professional report edition uses KOMA-Script `scrreprt`, CTeX/XeLaTeX, TikZ, and PGFPlots. `TECHNICAL_REPORT.md` remains the single content source; the build regenerates the LaTeX body, resolves the bibliography, checks the log for missing references, glyphs, and overfull boxes, and writes the stable PDF path shown above.

```powershell
powershell -ExecutionPolicy Bypass -File report/build_technical_report_latex.ps1
```

If `python` is not directly available, set `JCIIOT_REPORT_PYTHON` to the full path of a Python 3 interpreter before running the command.

For complete reproducibility details, third-party acknowledgements, novelty claims, quantitative analysis, strengths, and limitations, see the technical report.

**Official reference commit:** `129e94a9cff787031472045e19c24a4baeaefc48`  
**Score rule:** `grasp_success_gate_l5_multi_v2`  
**Evaluation date:** 2026-08-05  
**Team:** BIPT-EDU
