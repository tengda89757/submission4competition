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
    cloud(0.83, 0.22, 0.26, 0.11, "#D81B60", "Strict Verifier\n+ SHA-256")
    cloud(0.17, 0.22, 0.26, 0.11, "#D81B60", "Official Task Config\n(read-only)")

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
            "Boxes = Runtime Components   |   Ellipses = Read-only / Audit Inputs   |   Arrows = Data Flow",
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
    lim = (-1.05, 1.05)

    for ax in (ax1, ax2):
        ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
        ax.grid(True, alpha=0.3); ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")

    for ax in (ax1, ax2):
        ax.add_patch(Rectangle((-0.19, -0.24), 0.38, 0.48, facecolor="#B0BEC5",
                               alpha=0.45, edgecolor="#455A64", linewidth=2))
        ax.add_patch(Circle((0, 0), 0.035, facecolor="#263238"))
        ax.text(0, 0.30, "object centre", ha="center", fontsize=9, fontweight="bold")

    # Natural frame is measured from the official model sites.
    ax1.set_title("(a) Official-Site-Derived Natural Frame", fontsize=12, fontweight="bold")
    for x in (-0.11, 0.11):
        ax1.add_patch(Circle((x, -0.215), 0.045, facecolor="#42A5F5",
                             edgecolor="#0D47A1", linewidth=1.5))
    ax1.add_artist(FancyArrowPatch((0, 0), (0, -0.78), arrowstyle="->",
                                   mutation_scale=18, color="#6A1B9A", lw=2.5))
    ax1.add_patch(Circle((0, -0.941), 0.08, facecolor="#66BB6A",
                         edgecolor="#1B5E20", linewidth=2))
    ax1.text(0.08, -0.72, r"$u$", fontsize=12, color="#6A1B9A", fontweight="bold")
    ax1.text(0, -0.93, "base", ha="center", va="center", fontsize=8, fontweight="bold")
    ax1.text(0, -0.33, "official model sites", ha="center", fontsize=8, color="#0D47A1")

    # The skill rotates the measured direction and creates controller targets only.
    ax2.set_title("(b) Runtime Rotated Open-Face Frame", fontsize=12, fontweight="bold")
    ax2.add_artist(FancyArrowPatch((0, 0), (0.78, 0), arrowstyle="->",
                                   mutation_scale=18, color="#6A1B9A", lw=2.5))
    for y in (-0.11, 0.11):
        ax2.add_patch(Circle((0.315, y), 0.045, facecolor="#26C6DA",
                             edgecolor="#006064", linewidth=1.5))
    ax2.add_patch(Circle((0.941, 0), 0.08, facecolor="#66BB6A",
                         edgecolor="#1B5E20", linewidth=2))
    ax2.text(0.52, 0.07, r"$u'=R_z(\theta)u$", fontsize=11, color="#6A1B9A", fontweight="bold")
    ax2.text(0.941, 0, "base", ha="center", va="center", fontsize=8, fontweight="bold")
    ax2.text(0.315, 0.23, "runtime controller targets", ha="center", fontsize=8, color="#006064")
    ax2.text(0, -0.36, "XML sites and locked files remain unchanged", ha="center", fontsize=8)

    fig.suptitle("Runtime Geometry-Derived Grasp Approach", fontsize=14, fontweight="bold")
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

    fig.suptitle("Skill-Layer A* Clearance Ladder with Endpoint Exemption",
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

    # (a) real final positions from the previous 65-point package.
    old_aux = np.array([0.144, 8.473])
    old_output6 = np.array([10.03, -7.27])
    old_positions = np.array([[10.374096, -7.240515], [9.988338, -6.559996], [10.199182, -7.661235]])
    ax1.set_xlim(-1.5, 11.5); ax1.set_ylim(-8.7, 10.0); ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)
    ax1.add_patch(Circle(old_aux, R, facecolor="none", edgecolor="orange", linewidth=3, linestyle="--"))
    ax1.add_patch(Circle(old_output6, R, facecolor="none", edgecolor="#78909C", linewidth=2, linestyle=":"))
    for i, (x, y) in enumerate(old_positions):
        ax1.add_patch(Circle((x, y), 0.16, facecolor=colors[i], edgecolor="black", linewidth=1.2))
    ax1.text(*old_aux, "official\naux_output_1", ha="center", va="center", fontsize=8, fontweight="bold")
    ax1.text(*old_output6, "stale output_6", ha="center", va="center", fontsize=8)
    ax1.set_title("(a) Previous Package: Correct Grasp, Wrong Target (15/30)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Factory X (m)"); ax1.set_ylabel("Factory Y (m)")

    # (b) real final L5 positions relative to aux_output_1.
    final_relative = np.array([[0.150347, 0.110250], [0.354154, 0.043981], [-0.372031, 0.096636]])
    ax2.set_xlim(-1.0, 1.0); ax2.set_ylim(-1.0, 1.0); ax2.set_aspect("equal")
    ax2.grid(True, alpha=0.3)
    ax2.add_patch(Circle((0, 0), R, facecolor="none", edgecolor="orange", linewidth=3, linestyle="--"))
    for i, (x, y) in enumerate(final_relative):
        ax2.add_patch(Circle((x, y), 0.11, facecolor=colors[i], edgecolor="black", linewidth=1.5))
        ax2.text(x, y + 0.16, f"{np.hypot(x, y):.2f}m", ha="center", fontsize=8, color="blue")
    ax2.text(0, 0, "aux_output_1", ha="center", va="center", fontsize=8, fontweight="bold")
    ax2.set_title("(b) Final Package: Three Physical Drops (30/30)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("X relative to target (m)"); ax2.set_ylabel("Y relative to target (m)")

    fig.suptitle("L5 Target Alignment from Recorded Trajectories", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save(fig, "placement_comparison.png")


# =====================================================================
# 5. Performance Results Bar Chart
# =====================================================================
def create_results_performance_chart():
    fig, ax = plt.subplots(figsize=(10, 6))
    levels = ["L1", "L2", "L3", "L4", "L5"]
    max_scores = [10, 15, 20, 25, 30]
    previous = [10, 15, 0, 25, 15]
    final = [10, 15, 20, 25, 30]
    x = np.arange(len(levels)); w = 0.25

    ax.bar(x - w, max_scores, w, label="Maximum", color="lightgray", edgecolor="black", alpha=0.65)
    ax.bar(x, previous, w, label="Previous package (65)", color="#EF5350", edgecolor="#B71C1C")
    ax.bar(x + w, final, w, label="Official-aligned final (100)", color="#43A047", edgecolor="darkgreen")
    for i, values in enumerate(zip(max_scores, previous, final)):
        for dx, value, color in ((-w, values[0], "#333333"), (0, values[1], "#B71C1C"), (w, values[2], "#1B5E20")):
            ax.text(i + dx, value + 0.4, str(value), ha="center", fontsize=9, fontweight="bold", color=color)

    ax.set_ylabel("Score", fontsize=12, fontweight="bold")
    ax.set_title("Objective Rescore: Previous vs Official-Aligned Final",
                 fontsize=14, fontweight="bold", pad=14)
    ax.set_xticks(x); ax.set_xticklabels(levels, fontsize=12)
    ax.set_ylim(0, 35); ax.legend(fontsize=11, loc="upper left")
    ax.yaxis.grid(True, alpha=0.3); ax.set_axisbelow(True)
    ax.text(2, 33, "65 / 100  ->  100 / 100", ha="center", fontsize=14, fontweight="bold",
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
