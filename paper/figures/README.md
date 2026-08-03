# Technical-report figures

These figures support the auditable August 3, 2026 revision of the BIPT-EDU
technical report. They are explanatory diagrams or plots of recorded submission
evidence; they are not independent experimental results.

## Current figures

- `system_architecture.png` — official read-only task definition and verifier,
  BC-first agent, and participant-editable skill layer.
- `grasp_comparison.png` — official object-site frame versus a runtime
  geometry-derived rotated approach frame. No XML or model site is modified.
- `astar_inflation.png` — illustrative clearance ladder used in `skills/move.py`.
  Each panel is a temporary planning view; the official occupancy grid remains
  unchanged. The final panel shows the original grid fallback.
- `placement_comparison.png` — old and corrected L5 final positions taken from
  recorded trajectory frames, measured relative to the applicable target.
- `performance_results.png` — deterministic official-definition rescore:
  previous package 65/100, corrected package 100/100.

The source is `generate_charts.py`. Regenerate all five figures from this
directory in a Python environment with Matplotlib and NumPy:

```powershell
python generate_charts.py
```

## Evidence boundary

The report does **not** claim benchmark-wide state of the art, a controlled
ablation study, fixed navigation-clearance measurements, or timing speedups.
The score plot is based only on the strict local verifier pinned to official
commit `129e94a9cff787031472045e19c24a4baeaefc48`. Organizer acceptance remains
subject to source review.

Files under `demo/` and `make_demo_video.py` are retained as legacy qualitative
artifacts from earlier runs. They are not cited by the revised paper and must
not be treated as evidence for the corrected L3/L5 packages.

## Compile the paper

Run XeLaTeX twice from `paper/`:

```powershell
xelatex -interaction=nonstopmode -halt-on-error paper.tex
xelatex -interaction=nonstopmode -halt-on-error paper.tex
```

The bibliography is embedded in `paper.tex`; BibTeX is not required.
