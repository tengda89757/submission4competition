# 65 分根因与 100 分修复报告

## 结论

主办方的 **65/100** 可以用当前官方任务定义逐项精确复现，并不需要假设
`trajectory.json` 被手工修改。旧包的得分恰好是：

| 关卡 | 旧包得分 | 当前满分 | 根因 |
|---|---:|---:|---|
| L1 | 10 | 10 | 目标与当前官方定义一致。 |
| L2 | 15 | 15 | 目标与当前官方定义一致。 |
| L3 | 0 | 20 | 旧轨迹在 `input_6` 抓取 `blue_tote_b01_near_left`；当前官方定义已经是 `aux_input_1 → output_5`，且有效物体为 `blue_tote_b01_far_right` / `blue_tote_b01_near_right`。 |
| L4 | 25 | 25 | 目标与当前官方定义一致。 |
| L5 | 15 | 30 | 三次抓取有效，因此得到 15 分；旧轨迹释放在 `output_6`，当前官方目标是 `aux_output_1`，放置部分 0 分。 |
| **合计** | **65** | **100** | L3 丢 20 分，L5 丢 15 分。 |

本报告和最终包固定参考官方 commit
[`129e94a9cff787031472045e19c24a4baeaefc48`](https://github.com/JCIIOT2026/JCIIOT2026/commit/129e94a9cff787031472045e19c24a4baeaefc48)。
当前任务列表可直接查看官方
[`task_config.json`](https://github.com/JCIIOT2026/JCIIOT2026/blob/129e94a9cff787031472045e19c24a4baeaefc48/JCIIOT/knowledge/task_config.json)，
Case 3 的 Placement Point 1 更正见官方
[`ERRATUM.md`](https://github.com/JCIIOT2026/JCIIOT2026/blob/129e94a9cff787031472045e19c24a4baeaefc48/ERRATUM.md)。

## 为什么旧自测会显示 100

旧自测环境混用了过期任务信息：L3 被显式覆盖为左侧 `near_left`，L5 仍以
`output_6` 为目标；评分代码还存在“找不到指定物体时选择最近物体”的宽松回退。
因此它验证的是旧目标，而不是主办方更新后的 JSON 任务定义。主办方只按当前
任务定义重评提交 JSON，便稳定得到 65 分。

## 已完成的修复

- 将任务配置、L3/L5 语义地图、环境基类、官方 backend、核心类型、任务运行器
  和 `app.py` 与官方 commit 做逐字节同步。
- 严格评分器只接受当前关卡的官方候选物体，不再用“最近物体”掩盖配置错误。
- `aux_input_1` / `aux_output_1` 先做精确站点名解析，避免被错误匹配为
  `input_1` / `output_1`。
- 抓取位姿从运行中的物体与 grasp-site 几何实时计算；通过 A*、原地转向和直线
  接近完成物理运动。
- L5 的三个白色料箱分别释放到 `aux_output_1` 上三个互不重叠的有效点。
- `patch_grasp_pose.py` 改为只诊断，不再写入锁定的 `task_config.json`。

最终 L3、L5 均重新运行仿真，日志中没有 `judge_collision_detected`；五个最终轨迹
按严格规则得到 **10 + 15 + 20 + 25 + 30 = 100/100**。

## JSON 与“吸在手上”核查

- 最终 `trajectory.json` 是从仿真产生的 `trajectory_*_OK.json` **逐字节复制**进
  ZIP；打包流程没有改写轨迹内容。原始文件哈希与包内轨迹哈希一致。
- 代码没有直接写入或归一化 transport attachment 状态。抓取后的 attachment
  是官方 backend 自带的机制，可在官方
  [`robosuite_backend.py`](https://github.com/JCIIOT2026/JCIIOT2026/blob/129e94a9cff787031472045e19c24a4baeaefc48/JCIIOT/src/robot_agent/environments/robosuite_backend.py#L1166-L1176)
  中看到官方在抓取流水线成功后调用 `capture_transport_attachment`。
- 最终五个 ZIP 都只含 `trajectory.json`、`score.json`、
  `submission_manifest.json` 三个文件；清单引用相同官方 commit。
- 机器可读的逐包分数与 SHA-256 见
  [`submission_100_final_129e94a9/verification_report.json`](submission_100_final_129e94a9/verification_report.json)。

## 验证命令

```powershell
JCIIOT\.venv\Scripts\python.exe verify_submission.py `
  --submissions submission_100_final_129e94a9 `
  --json-out submission_100_final_129e94a9\verification_report.json
```

预期结果：五关均为 `PASS`，总分 `100/100`。
