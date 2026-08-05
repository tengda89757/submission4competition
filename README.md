# JCIIOT 2026 RunningRobot — BIPT-EDU Final Bundle

这是清理后的最终交付包。L1–L5 均使用冻结后的现实性约束代码重新完整运行；旧的失败轨迹、旧录像和过时的高风险加速结果不在本包中。

## Final result

| Level | Score | Realism audit | Full-frame video |
|---|---:|---|---|
| L1 | 10/10 | PASS | 1,793 / 1,793 frames, PASS |
| L2 | 15/15 | PASS | 1,674 / 1,674 frames, PASS |
| L3 | 20/20 | PASS | 2,402 / 2,402 frames, PASS |
| L4 | 25/25 | PASS | 2,324 / 2,324 frames, PASS |
| L5 | 30/30 | PASS | 10,139 / 10,139 frames, PASS |
| **Total** | **100/100** | **5/5 PASS** | **18,332 / 18,332 frames** |

所有最终轨迹均满足：记录碰撞帧为 0、夹持物与其他物料的非预期接触帧为 0、夹持期间机械手接触率不低于 99%。最大底盘位移为 0.035113 m/帧，没有隔空取物、瞬间移动或源点到终点的物体传送。

## Start here

- Comprehensive technical report: [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md)
- Typeset technical report: [output/pdf/TECHNICAL_REPORT.pdf](output/pdf/TECHNICAL_REPORT.pdf)
- Official L1–L5 ZIPs and checksums: [submission/](submission/)
- Per-level trajectories, scores, and realism audits: [evidence/](evidence/)
- Full L1–L5 dual-view videos: [videos/](videos/)
- Aggregate results and verification reports: [results/](results/)
- Participant source overlay: [source_code/](source_code/)

## Verify

From the extracted bundle root:

```powershell
python verify_submission.py --json-out results/package_verification_rerun.json
```

The verifier uses only Python's standard library. It checks that exactly one ZIP exists for every level, validates SHA-256, recomputes the objective score from the official semantic-map centers, and verifies the frozen reference and manifest fields.

For complete reproducibility details, third-party acknowledgements, novelty claims, quantitative analysis, strengths, and limitations, see the technical report.

**Official reference commit:** `129e94a9cff787031472045e19c24a4baeaefc48`  
**Score rule:** `grasp_success_gate_l5_multi_v2`  
**Final run date:** 2026-08-05  
**Team:** BIPT-EDU
