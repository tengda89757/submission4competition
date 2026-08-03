# BIPT-EDU Final Submission — 100/100

Official reference:
[`129e94a9cff787031472045e19c24a4baeaefc48`](https://github.com/JCIIOT2026/JCIIOT2026/commit/129e94a9cff787031472045e19c24a4baeaefc48)

| Level | Package | Verified score |
|---|---|---:|
| L1 | `L1_20260803_141824.zip` | 10/10 |
| L2 | `L2_20260803_141825.zip` | 15/15 |
| L3 | `L3_20260803_141826.zip` | 20/20 |
| L4 | `L4_20260803_141827.zip` | 25/25 |
| L5 | `L5_20260803_141828.zip` | 30/30 |
| **Total** |  | **100/100** |

Each level ZIP contains exactly `trajectory.json`, `score.json`, and
`submission_manifest.json`. The packaged trajectory is a byte-for-byte copy of
the raw simulator `trajectory_*_OK.json`; it is not post-processed. Raw and
packaged trajectory SHA-256 values match.

The locked task configuration, generated L3/L5 maps, environment base/backend,
core types, task runner, and app were audited byte-for-byte against the pinned
official commit. Runtime fixes are in the skill and pipeline layers and do not
directly mutate transport attachment state.

From the repository root, verify with:

```powershell
JCIIOT\.venv\Scripts\python.exe verify_submission.py `
  --submissions submission_100_final_129e94a9
```

See `verification_report.json` for machine-readable scores and hashes, and
`../SCORE_DIAGNOSIS.md` for the reproduced 65-point root cause.
