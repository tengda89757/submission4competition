#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate all figures and charts for JCIIOT 2026 Competition Technical Report
Team: BIPT-EDU
Run from the figures/ directory using the project venv python.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyArrow, FancyArrowPatch, Polygon

# ---- Global style ----
try:
    plt.style.use("seaborn-v0_8-whitegrid")
except Exception:
    plt.style.use("ggplot")
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["figure.dpi"] = 300
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["savefig.bbox"] = "tight"

HERE = os.path.dirname(os.path.abspath(__file__))


def _save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  created:", name)


# =====================================================================
# 1. System Architecture Diagram
# =====================================================================
def create_system_architecture_diagram():
    fig, ax = plt.subplots(figsize=(10, 7))

    def box(cx, cy, w, h, color, label):
        r = Rectangle((cx - w / 2, cy - h / 2), w, h, facecolor=color,
                      edgecolor="black", linewidth=2, alpha=0.9, zorder=3)
        ax.add_patch(r)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=11,
                fontweight="bold", color="white", zorder=4)

    def cloud(cx, cy, w, h, color, label):
        e = plt.matplotlib.patches.Ellipse((cx, cy), w, h, facecolor=color,
                                           edgecolor="black", linewidth=2, alpha=0.85, zorder=3)
        ax.add_patch(e)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=9,
                fontweight="bold", color="white", zorder=4)

    # Nodes
    box(0.50, 0.55, 0.20, 0.13, "#43A047", "RobotAgent\nCoordinator")
    box(0.50, 0.86, 0.18, 0.10, "#1E88E5", "User Task Query")
    box(0.50, 0.24, 0.18, 0.10, "#FB8C00", "Skill Registry")
    box(0.17, 0.55, 0.20, 0.13, "#00ACC1", "LLM Planner\n(Qwen2.5:7B)")
    box(0.83, 0.55, 0.20, 0.13, "#8E24AA", "Environment\n(MuJoCo/Robosuite)")
    cloud(0.83, 0.22, 0.26, 0.11, "#D81B60", "Memory /\nInstrumentation")
    cloud(0.17, 0.22, 0.24, 0.11, "#D81B60", "Replay Buffer")

    def arrow(x1, y1, x2, y2, label="", lx=None, ly=None):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=2, color="#333333"), zorder=2)
        if label:
            if lx is None:
                lx = (x1 + x2) / 2
            if ly is None:
                ly = (y1 + y2) / 2
            ax.text(lx, ly, label, fontsize=8.5, ha="center", va="center", color="#222222",
                    bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="#cccccc", alpha=0.95), zorder=5)

    # vertical (user -> agent -> skills)
    arrow(0.50, 0.81, 0.50, 0.62, "task query")
    arrow(0.50, 0.48, 0.50, 0.29, "step list")
    # LLM planner <-> RobotAgent: two arrows separated vertically, labels centred in the gap
    arrow(0.40, 0.595, 0.27, 0.595, "observations", lx=0.335, ly=0.640)
    arrow(0.27, 0.505, 0.40, 0.505, "LLM plan", lx=0.335, ly=0.460)
    # RobotAgent <-> Environment
    arrow(0.60, 0.595, 0.73, 0.595, "commands", lx=0.665, ly=0.640)
    arrow(0.73, 0.505, 0.60, 0.505, "state obs", lx=0.665, ly=0.460)
    # diagonals to supporting clouds
    arrow(0.60, 0.49, 0.75, 0.30, "")
    arrow(0.40, 0.49, 0.25, 0.30, "")

    ax.text(0.5, 0.04,
            "Boxes = Core Components   |   Ellipses = Supporting Mechanisms   |   Arrows = Data Flow",
            ha="center", fontsize=9, style="italic", color="#555555")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Unified RobotAgent Architecture", fontsize=16, fontweight="bold", pad=16)
    _save(fig, "system_architecture.png")


# =====================================================================
# 2. Grasp Site Geometry Comparison
# =====================================================================
def create_grasp_comparison():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    lim = (-0.32, 0.32)

    for ax in (ax1, ax2):
        ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
        ax.grid(True, alpha=0.3); ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")

    # (a) default buried
    ax1.set_title("(a) Default Buried Site  (Left Arm Clips)", fontsize=12, fontweight="bold")
    ax1.add_patch(Rectangle((-0.15, -0.15), 0.30, 0.30, facecolor="gray", alpha=0.3,
                            edgecolor="black", linewidth=2))
    ax1.add_patch(Circle((0, 0), 0.05, facecolor="red", alpha=0.8))
    ax1.add_patch(Circle((0, -0.10), 0.12, facecolor="blue", alpha=0.45))
    ax1.add_patch(Circle((0, 0.10), 0.12, facecolor="green", alpha=0.45))
    ax1.add_patch(Polygon([[0, -0.04], [-0.035, -0.11], [0.035, -0.11]],
                          facecolor="red", edgecolor="darkred", linewidth=2, alpha=0.9))
    ax1.annotate("COLLISION", xy=(0, -0.14), ha="center", fontsize=10,
                 bbox=dict(boxstyle="round,pad=0.3", fc="red", alpha=0.75, ec="darkred"))
    ax1.text(0, 0.22, "Object AABB Proxy", ha="center", fontsize=11, fontweight="bold")
    ax1.text(0, 0.0, "buried\nsite", ha="center", va="center", fontsize=7, color="white")

    # (b) virtual east-wall
    ax2.set_title("(b) Virtual East-Wall Sites  (Both Arms Succeed)", fontsize=12, fontweight="bold")
    ax2.add_patch(Rectangle((-0.15, -0.15), 0.30, 0.30, facecolor="gray", alpha=0.3,
                            edgecolor="black", linewidth=2))
    ax2.add_patch(Circle((0.155, -0.05), 0.045, facecolor="#00CED1", edgecolor="darkcyan", linewidth=2))
    ax2.add_patch(Circle((0.155, 0.05), 0.045, facecolor="#00CED1", edgecolor="darkcyan", linewidth=2))
    ax2.add_patch(Circle((0.02, -0.10), 0.12, facecolor="blue", alpha=0.45))
    ax2.add_patch(Circle((0.02, 0.10), 0.12, facecolor="green", alpha=0.45))
    ax2.add_artist(FancyArrowPatch((0.0, 0.0), (0.12, 0.05), arrowstyle="->",
                                   mutation_scale=18, color="purple", lw=2, linestyle="--"))
    ax2.text(0.06, -0.16, r"$R_z(90^\circ)$", ha="center", fontsize=11, color="purple", fontweight="bold")
    ax2.text(0, 0.22, "Object AABB Proxy", ha="center", fontsize=11, fontweight="bold")
    ax2.text(0.155, 0.13, "virtual\nsites", ha="center", fontsize=8, color="darkcyan", fontweight="bold")

    fig.suptitle("Grasp Site Geometry Comparison", fontsize=14, fontweight="bold")
    fig.tight_layout()
    _save(fig, "grasp_comparison.png")


# =====================================================================
# 3. Graduated A* Obstacle Inflation Ladder
# =====================================================================
def create_astar_inflation_ladder():
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()
    n = 40
    base = np.zeros((n, n))
    obstacles = [(16, 22), (20, 22), (24, 22), (28, 22)]
    for ox, oy in obstacles:
        base[oy:oy + 4, ox:ox + 3] = 1

    margins = [9, 6, 3, 0]
    labels = ["Stage 1: 0.45m (Coarse)", "Stage 2: 0.30m", "Stage 3: 0.15m", "Stage 4: 0.0m (Original)"]

    def dilate(g, k):
        out = g.copy()
        for _ in range(k):
            nxt = out.copy()
            nxt[1:, :] = np.maximum(nxt[1:, :], out[:-1, :])
            nxt[:-1, :] = np.maximum(nxt[:-1, :], out[1:, :])
            nxt[:, 1:] = np.maximum(nxt[:, 1:], out[:, :-1])
            nxt[:, :-1] = np.maximum(nxt[:, :-1], out[:, 1:])
            out = nxt
        return out

    goal = (34, 20)
    for i, (k, lab) in enumerate(zip(margins, labels)):
        ax = axes[i]
        g = dilate(base, k) if k > 0 else base.copy()
        if k >= 6:  # endpoint exemption near goal
            gx, gy = goal
            g[gy - 3:gy + 4, gx - 3:gx + 4] = base[gy - 3:gy + 4, gx - 3:gx + 4]
        ax.imshow(g, cmap="Blues", origin="lower", vmin=0, vmax=1.4)
        ax.set_title(lab, fontsize=12, fontweight="bold")
        ax.set_xlabel("Grid Cells"); ax.set_ylabel("Grid Cells")
        ax.add_patch(Circle(goal, 1.5, facecolor="green", alpha=0.65))
        ax.text(goal[0], goal[1], "GOAL", ha="center", va="center", fontsize=8,
                fontweight="bold", color="white")
        if i < 3:
            px = [2, 2, 10, 10, 22, 30, 34]
            py = [8, 14, 14, 30, 30, 22, 20]
            ax.plot(px, py, "g-o", lw=2, ms=5, alpha=0.85)
        ax.set_xlim(0, n); ax.set_ylim(0, n)

    fig.suptitle("Graduated A* Obstacle Inflation Ladder with Endpoint Exemption",
                 fontsize=15, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    _save(fig, "astar_inflation.png")


# =====================================================================
# 4. Multi-Object Placement Strategy Comparison
# =====================================================================
def create_placement_comparison():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    R = 0.80
    colors = ["#FF6B6B", "#4ECDC4", "#FFD93D"]

    for ax in (ax1, ax2):
        ax.set_xlim(-1.2, 1.2); ax.set_ylim(-1.2, 1.2); ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.add_patch(Circle((0, 0), R, facecolor="none", edgecolor="orange",
                            linewidth=3, linestyle="--", alpha=0.8))
        ax.text(0, R + 0.05, "Scoring Radius (<0.80m)", ha="center", fontsize=9, color="darkorange")

    # (a) simultaneous release - FAIL
    ax1.set_title("(a) Simultaneous Release  (Chain-Push - FAIL)", fontsize=13, fontweight="bold")
    for i, (x, y) in enumerate([(0.05, 0.02), (0.10, 0.06), (0.02, -0.03)]):
        ax1.add_patch(Circle((x, y), 0.11, facecolor=colors[i], edgecolor="black", linewidth=1.5, alpha=0.85))
    ax1.annotate("", xy=(0.92, 0.16), xytext=(0.08, 0.03),
                 arrowprops=dict(arrowstyle="-|>", lw=2.5, color="red"))
    ax1.add_patch(Circle((0.92, 0.16), 0.11, facecolor=colors[0], edgecolor="red", linewidth=2.5, alpha=0.6))
    ax1.text(0.95, 0.30, ">0.92m", fontsize=10, color="red", fontweight="bold")
    ax1.text(0, -1.05, "STATUS: FAILED", ha="center", fontsize=14, fontweight="bold", color="red")

    # (b) spread placement - PASS
    ax2.set_title("(b) Sequential Spread ($\\pm$0.38m)  (PASS)", fontsize=13, fontweight="bold")
    for i, (x, y) in enumerate([(0.55, 0.0), (0.50, 0.38), (0.50, -0.38)]):
        ax2.add_patch(Circle((x, y), 0.11, facecolor=colors[i], edgecolor="black", linewidth=1.5, alpha=0.85))
        d = np.hypot(x, y)
        ax2.text(x, y + 0.16, f"{d:.2f}m", ha="center", fontsize=8, color="blue")
    ax2.text(-0.95, 0.38, "+0.38m", fontsize=9, color="blue", fontweight="bold")
    ax2.text(-0.95, -0.40, "-0.38m", fontsize=9, color="blue", fontweight="bold")
    ax2.text(0, -1.05, "STATUS: PASSED", ha="center", fontsize=14, fontweight="bold", color="green")

    fig.suptitle("Multi-Object Release Strategy Comparison", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save(fig, "placement_comparison.png")


# =====================================================================
# 5. Performance Results Bar Chart
# =====================================================================
def create_results_performance_chart():
    fig, ax = plt.subplots(figsize=(10, 6))
    levels = ["L1", "L2", "L3", "L4", "L5"]
    max_scores = [10, 15, 20, 25, 30]
    achieved = [10, 15, 20, 25, 30]
    x = np.arange(len(levels)); w = 0.38

    ax.bar(x - w / 2, max_scores, w, label="Max Score", color="lightgray", edgecolor="black", alpha=0.6)
    ax.bar(x + w / 2, achieved, w, label="Achieved", color="#43A047", edgecolor="darkgreen")
    for i, (m, a) in enumerate(zip(max_scores, achieved)):
        ax.text(i - w / 2, m + 0.4, str(m), ha="center", fontsize=10, fontweight="bold")
        ax.text(i + w / 2, a + 0.4, str(a), ha="center", fontsize=10, fontweight="bold", color="darkgreen")

    ax.set_ylabel("Score", fontsize=12, fontweight="bold")
    ax.set_title("Competition Results: Perfect Scores Across All Levels (100/100)",
                 fontsize=14, fontweight="bold", pad=14)
    ax.set_xticks(x); ax.set_xticklabels(levels, fontsize=12)
    ax.set_ylim(0, 35); ax.legend(fontsize=11, loc="upper left")
    ax.yaxis.grid(True, alpha=0.3); ax.set_axisbelow(True)
    ax.text(2, 33, "TOTAL: 100 / 100", ha="center", fontsize=14, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", fc="#FFF3CD", ec="orange"))
    fig.tight_layout()
    _save(fig, "performance_results.png")


def main():
    print("=" * 60)
    print("Generating figures for JCIIOT 2026 Technical Report")
    print("=" * 60)
    create_system_architecture_diagram()
    create_grasp_comparison()
    create_astar_inflation_ladder()
    create_placement_comparison()
    create_results_performance_chart()
    print("=" * 60)
    print("All figures generated successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
