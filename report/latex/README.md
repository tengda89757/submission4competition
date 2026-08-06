# LaTeX technical report

The final report uses `scrreprt` from KOMA-Script as its report-class foundation,
with CTeX/XeLaTeX for Unicode and Chinese-capable typesetting. TikZ and PGFPlots
render the architecture, state-handoff, placement, and continuity figures as
vector graphics.

`TECHNICAL_REPORT.md` remains the single content source. Do not edit
`generated/body.tex` directly; it is regenerated during every build.

From the repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File report/build_technical_report_latex.ps1
```

The stable output path is `output/pdf/TECHNICAL_REPORT.pdf`. The build script
runs XeLaTeX, Biber, and two final XeLaTeX passes, and fails if the log contains
undefined references, overfull boxes, or missing glyphs.

Template foundations:

- KOMA-Script `scrreprt`: <https://ctan.org/pkg/scrreprt>
- CTeX: <https://ctan.org/pkg/ctex>

Both foundations are distributed under LPPL 1.3c. The report-specific style and
figure sources in this directory are part of this repository's submission code.
