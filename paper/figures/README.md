# JCIIOT 2026 Competition Technical Report - Figures Directory

## Overview

This directory contains all visual materials required for the high-standard technical report submission to JCIIOT 2026 RunningRobot competition by team **BIPT-EDU**.

## Generated Figures

All figures have been professionally generated using Python/Matplotlib and TikZ LaTeX. They demonstrate the four key innovations of our unified agent-based robotics system that achieved perfect scores (100/100).

### 1. system_architecture.png
**Purpose:** Unified RobotAgent Architecture Diagram  
**Location in Paper:** Section 3.1 System Architecture  
**Description:** Shows data flow between user task query → LLM planner → skill registry → environment, with memory/instrumentation/replay supporting mechanisms.

**File Details:**
- Format: PNG (lossless compression)
- Resolution: 300 DPI
- Size: 1200×900 pixels
- Color scheme: Professional color palette with clear distinction between core components (colored rectangles) and supporting mechanisms (pink clouds)

**To Generate:**
```python
python generate_charts.py
# or specifically:
python generate_charts.py --figure system_architecture
```

---

### 2. grasp_comparison.png
**Purpose:** Grasp Site Geometry Comparison (Default vs Virtual)  
**Location in Paper:** Section 4.2.1 East-Wall Virtual Grasp Sites  
**Description:** Two-panel figure comparing buried default grasp sites causing left-arm collisions vs. east-wall virtual sites enabling symmetric success.

**File Details:**
- Format: PNG
- Resolution: 300 DPI  
- Size: 1500×600 pixels (two subfigures side-by-side)
- Left panel: Red collision marker showing clipping inside AABB proxy box
- Right panel: Cyan virtual grasp points on open east wall face
- Includes rotation arrow annotated with $R_z(90°)$ transformation

**Key Information Shown:**
- Object AABB boundaries (gray transparent boxes)
- Gripper positions (blue/green circles)
- Collision indicators (red triangles with text annotation)
- Distance measurements confirming target tolerances (≤2mm position error)

---

### 3. astar_inflation.png
**Purpose:** Graduated A* Obstacle Inflation Ladder Visualization  
**Location in Paper:** Section 4.3.2 Multi-Stage Dilation Algorithm  
**Description:** Four-stage progressive refinement showing how obstacle inflation decreases from coarsest (0.45m) to original grid, with endpoint exemption preserving approach accuracy.

**File Details:**
- Format: PNG
- Resolution: 300 DPI
- Size: 1000×1200 pixels (vertical stack)
- Subfigures arranged vertically: stages 1→4
- Colormap: Blues_r (dark blue = obstacles, light = free space)
- Green circles marking goal region with endpoint exemption
- Orange dashed rectangles highlighting module obstacles
- Solid green path lines showing safe trajectories through each stage

**What Each Stage Shows:**
1. **Stage 1 (0.45m):** Coarsest inflation ensures global feasibility but blocks optimal paths
2. **Stage 2 (0.30m):** Moderate dilation begins recovery of some routes
3. **Stage 3 (0.15m):** Fine dilation near goals starts prioritizing precision
4. **Stage 4 (0.0m):** Original grid preserved only near goal cells where accuracy matters

**Performance Metrics Displayed:**
- Mid-route clearance improved from 0.05m → 0.46m (+820%)
- Collision events eliminated completely
- Latency overhead <5ms negligible impact

---

### 4. placement_comparison.png
**Purpose:** Multi-Object Placement Strategy Comparison  
**Location in Paper:** Section 4.4.2 Temporal Multiplexing Formula  
**Description:** Side-by-side comparison demonstrating chain-push effect during simultaneous release (FAIL) vs. spread placement with ±0.38m lateral separation (PASS).

**File Details:**
- Format: PNG
- Resolution: 300 DPI
- Size: 1600×700 pixels
- Scoring radius indicator: orange dashed circle at r=0.80m threshold
- Object colors: #FF6B6B (red), #4ECDC4 (teal), #FFE66D (yellow)

**Left Panel - Simultaneous Release (FAIL):**
- Three objects clumped together displaced >0.92m outside scoring zone
- Red chain-push vector indicating displacement direction
- FAILED status banner at bottom with ❌ emoji
- Warning annotations pointing to out-of-bounds object

**Right Panel - Sequential Spread Placement (PASS):**
- Objects distributed along y-axis with offsets [0.0, +0.38, -0.38]m
- All three within 0.80m scoring radius (verified distance measurements)
- PASSED status banner at bottom with ✓ emoji
- Green success indicators and spacing annotations

**Mathematical Formulas Included:**
- Lateral offset calculation: $\Delta x_i = \frac{W}{N}\cdot(i - \frac{N-1}{2})$
- Individual object distances from centroid displayed inline

---

### 5. performance_results.png
**Purpose:** Competition Results Bar Chart  
**Location in Paper:** Section 5 Experimental Results  
**Description:** Comprehensive bar chart showing max vs. achieved scores across all five levels, emphasizing perfect 100/100 total achievement.

**File Details:**
- Format: PNG
- Resolution: 300 DPI
- Size: 1000×600 pixels
- X-axis: Levels L1-L5 labeled clearly
- Y-axis: Score ranging from 0 to 35 (slightly above max possible 30)
- Gray bars: Maximum achievable scores per level
- Green bars: Our achieved scores (identical heights proving perfection)
- Score labels on top of each bar
- Total score annotation with arrow pointing to stacked bars
- Legend identifying gray vs. green bars

**Data Summary:**
| Level | Max | Achieved | Status |
|-------|-----|----------|--------|
| L1    | 10  | 10       | ✓      |
| L2    | 15  | 15       | ✓      |
| L3    | 20  | 20       | ✓      |
| L4    | 25  | 25       | ✓      |
| L5    | 30  | 30       | ✓      |
| **Total** | **100** | **100** | **Perfect** |

---

## Alternative Generation Methods

### Method A: Using Python Script (Recommended)
```bash
cd figures
python generate_charts.py
# All 5 figures will be generated automatically
```

### Method B: Manual PDF/LaTeX Compilation (TikZ diagram only)
```bash
pdflatex create_figures.tex
# Generates system_architecture.pdf (vector graphics format)
```

### Method C: Overleaf Online Editor
For users without local Python/TikZ installation:
1. Visit [overleaf.com](https://overleaf.com)
2. Create new project named "JCIIOT-Figures"
3. Upload `paper.tex` and `references.bib` from parent directory
4. Copy figure generation code snippets directly into main document
5. Use "Recompile" button to render figures inline
6. Export final PDF including all visuals

---

## Image Quality Standards

All generated images meet publication-quality standards:
- **Resolution:** Minimum 300 DPI for sharp printing
- **Format:** PNG with lossless compression (no quality degradation)
- **Color Space:** sRGB compatible for universal display compatibility
- **Text Rendering:** Vector-smooth fonts (Arial family) ensuring legibility at any zoom level
- **Backgrounds:** Pure white backgrounds (#FFFFFF) for professional appearance

---

## Usage Instructions in Paper

Include figures using standard LaTeX syntax in `paper.tex`:

```latex
\begin{figure}[H]
\centering
\includegraphics[width=0.9\textwidth]{figures/system_architecture.png}
\caption{\textbf{Unified RobotAgent Architecture}}
\label{fig:architecture}
\end{figure}
```

For multi-panel figures (grasp_comparison and placement_comparison):

```latex
\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{figures/grasp_comparison.png}
\caption{\textbf{Grasp Site Geometry Comparison}}
\label{fig:grasp_comparison}
\end{figure}
```

---

## Compiling the Report PDF

The report is compiled with **XeLaTeX** (for Unicode symbols). From the `paper/` directory:

```bash
xelatex paper.tex
xelatex paper.tex   # 2nd pass resolves the table of contents and cross-references
```

The bibliography is embedded via `thebibliography`, so no BibTeX pass is required. Output: `paper.pdf` (16 pages).

---

## File Locations Summary

```
JCIIOT2026-master/
└── JCIIOT/
    └── pipeline/
        └── submissions_total/
            ├── figures/                    ← This directory
            │   ├── README.md               ← Documentation you're reading now
            │   ├── generate_charts.py     ← Python script to regenerate figures
            │   ├── create_figures.tex     ← TikZ source for architecture diagram
            │   ├── make_demo_video.py    ← Renders MuJoCo demo videos (real ffmpeg)
            │   ├── system_architecture.png
            │   ├── grasp_comparison.png
            │   ├── astar_inflation.png
            │   ├── placement_comparison.png
            │   ├── performance_results.png
            │   └── demo/                    ← Rendered videos: l1..l5 follow + birdview .mp4 + 60 keyframes
            ├── paper.tex                   ← Main LaTeX document
            ├── references.bib              ← Bibliography database
            ├── TECHNICAL_SOLUTION.md       ← Markdown alternative version
            └── README.md                   ← Submission overview
```

---

## Video Demonstration

We provide **real simulation videos of all five levels (L1–L5)** of the robot executing each task. Frames are rendered directly from the perfect-score trajectories inside the MuJoCo physics simulation using the project's own `RobosuiteBackend.replay_trajectory()` pipeline, then encoded to H.264 MP4 with FFmpeg (bundled via `imageio-ffmpeg`). L5 is the flagship task (`FactorySorting9_3FO3ERT2C5FP`, 10 objects).

**Rendered assets (in `demo/`), two camera views per level:**
- `l1_follow_demo.mp4` … `l5_follow_demo.mp4` — chase camera tracking the mobile base (robot close-up)
- `l1_birdview_demo.mp4` … `l5_birdview_demo.mp4` — top-down `birdview` used by the scoring pipeline
- `l1..l5` × `follow`/`birdview` `_keyframe_[1-6].png` — evenly-spaced keyframes (L5's feed the paper's L5 figures; the L1–L4 follow frames feed the paper's all-levels figure)

Total: **10 MP4s + 60 keyframe PNGs**.

**To regenerate** (from the JCIIOT project root, using the project venv):

```bash
cd pipeline/submissions_total/paper/figures
# render both camera views for every level (L1 shown; repeat for L2 L3 L4 L5)
python make_demo_video.py L1 follow      # robot close-up chase camera
python make_demo_video.py L1 birdview    # top-down scoring overview
```

Rendering uses real MuJoCo offscreen rendering (requires GL/GPU access) and the `imageio-ffmpeg` H.264 encoder — no manual keyframe extraction needed.

---

## Contact & Support

Questions about figure generation or usage? Please refer to:
- Python dependencies list in `requirements.txt` (parent directory)
- LaTeX compilation guide in parent `TECHNICAL_SOLUTION.md`
- Team communication channels established during competition phase

Generated by **BIPT-EDU** team for JCIIOT 2026 RunningRobot competition. 🎉
