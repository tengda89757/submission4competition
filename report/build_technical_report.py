#!/usr/bin/env python3
"""Build figures and the typeset JCIIOT technical report from submitted evidence."""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = ROOT / "TECHNICAL_REPORT.md"
RESULTS = ROOT / "results" / "final_run_summary.json"
VIDEOS = ROOT / "videos"
ASSETS = ROOT / "report" / "assets"
OUTPUT_DIR = ROOT / "output" / "pdf"
OUTPUT = OUTPUT_DIR / "TECHNICAL_REPORT.pdf"

NAVY = colors.HexColor("#12344D")
BLUE = colors.HexColor("#176B91")
TEAL = colors.HexColor("#16877B")
ORANGE = colors.HexColor("#D8782C")
INK = colors.HexColor("#1D2A34")
MUTED = colors.HexColor("#60717E")
GRID = colors.HexColor("#C8D3DB")
PALE_BLUE = colors.HexColor("#EAF3F8")
PALE_TEAL = colors.HexColor("#E8F6F3")
PALE_ORANGE = colors.HexColor("#FFF0E3")
PALE_GRAY = colors.HexColor("#F3F6F8")


def _register_fonts() -> None:
    regular = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans"))
    bold = font_manager.findfont(
        font_manager.FontProperties(family="DejaVu Sans", weight="bold")
    )
    oblique = font_manager.findfont(
        font_manager.FontProperties(family="DejaVu Sans", style="oblique")
    )
    mono = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans Mono"))
    for name, path in (
        ("ReportSans", regular),
        ("ReportSans-Bold", bold),
        ("ReportSans-Oblique", oblique),
        ("ReportMono", mono),
    ):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, path))


_register_fonts()


def _load_results() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def _save_architecture() -> None:
    fig, ax = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    ax.axis("off")
    boxes = [
        (0.015, 0.39, 0.16, 0.24, "Official task\nidentifiers", "#DDECF4"),
        (0.215, 0.39, 0.16, 0.24, "Semantic plan\n+ A* route", "#D5ECE8"),
        (0.415, 0.39, 0.16, 0.24, "Bounded move\n+ physical grasp", "#F9E4CD"),
        (0.615, 0.39, 0.16, 0.24, "MuJoCo state\nper physics step", "#E6E0F1"),
        (0.815, 0.39, 0.17, 0.24, "Score + audit\n+ full video", "#DDECF4"),
    ]
    for x, y, width, height, label, color in boxes:
        rect = plt.Rectangle(
            (x, y), width, height, facecolor=color, edgecolor="#28475B", linewidth=1.8
        )
        ax.add_patch(rect)
        ax.text(
            x + width / 2,
            y + height / 2,
            label,
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="#203846",
        )
    for left, right in zip(boxes, boxes[1:]):
        ax.annotate(
            "",
            xy=(right[0] - 0.006, 0.51),
            xytext=(left[0] + left[2] + 0.006, 0.51),
            arrowprops=dict(arrowstyle="-|>", color="#385A6D", lw=2),
        )
    ax.text(
        0.5,
        0.82,
        "semantic map + live object geometry + payload-aware clearance",
        ha="center",
        fontsize=10.5,
        color="#536A77",
    )
    ax.annotate(
        "",
        xy=(0.5, 0.65),
        xytext=(0.5, 0.77),
        arrowprops=dict(arrowstyle="-|>", color="#536A77", lw=1.6),
    )
    ax.text(
        0.5,
        0.16,
        "Release gate: maximum score AND continuity/contact audit AND video integrity",
        ha="center",
        fontsize=10.7,
        color="#536A77",
        style="italic",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.savefig(ASSETS / "system_architecture.png", dpi=190, facecolor="white")
    plt.close(fig)


def _save_l5_placement(results: dict) -> None:
    l5 = next(row for row in results["levels"] if row["level"] == "L5")
    distances = l5["final_target_distances_m"]
    # Target-relative terminal XY values from the submitted trajectory.
    points = {
        "front": (0.1535 - 0.144, 8.538156 - 8.473),
        "center": (0.809918 - 0.144, 8.520620 - 8.473),
        "back": (-0.501914 - 0.144, 8.497040 - 8.473),
    }
    names = {
        "front": "white_tote_b01_left_front",
        "center": "white_tote_b01_left_center",
        "back": "white_tote_b01_left_back",
    }
    palette = {"front": "#16877B", "center": "#176B91", "back": "#D8782C"}
    fig, ax = plt.subplots(figsize=(6.4, 5.9), constrained_layout=True)
    ax.add_patch(
        plt.Circle(
            (0, 0), 0.8, fill=False, linestyle="--", linewidth=2.3, color="#D68A2A"
        )
    )
    ax.scatter([0], [0], marker="+", s=170, linewidths=2.2, color="#263B49")
    for label, (x, y) in points.items():
        ax.scatter(
            [x], [y], s=310, color=palette[label], edgecolors="white", linewidths=2, zorder=3
        )
        distance = distances[names[label]]
        ax.annotate(
            f"{label}: {distance:.3f} m",
            (x, y),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=9.5,
            color="#263B49",
        )
    ax.set_aspect("equal")
    ax.set_xlim(-0.9, 0.9)
    ax.set_ylim(-0.9, 0.9)
    ax.set_xlabel("X offset from official target center (m)")
    ax.set_ylabel("Y offset from official target center (m)")
    ax.set_title("L5 terminal placement from the submitted trajectory", fontweight="bold")
    ax.grid(alpha=0.22)
    ax.text(-0.86, -0.85, "dashed circle = 0.80 m score radius", fontsize=8.5, color="#667680")
    fig.savefig(ASSETS / "l5_final_placement.png", dpi=190, facecolor="white")
    plt.close(fig)


def _save_continuity(results: dict) -> None:
    rows = results["levels"]
    metrics = (
        ("base step", "max_base_step_m", "max_base_step_m"),
        ("base turn", "max_base_turn_rad", "max_base_turn_rad"),
        ("joint step", "max_joint_step", "max_joint_step"),
        ("object step", "max_object_step_m", "max_object_step_m"),
        ("object turn", "max_object_turn_rad", "max_object_turn_rad"),
    )
    matrix = np.array(
        [
            [
                float(row["realism"][observed]) / float(row["realism"]["limits"][limit])
                for _, observed, limit in metrics
            ]
            for row in rows
        ]
    )
    fig, ax = plt.subplots(figsize=(9.6, 4.5), constrained_layout=True)
    image = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(metrics)), [label for label, _, _ in metrics])
    ax.set_yticks(range(len(rows)), [row["level"] for row in rows])
    ax.set_title("Observed frame-to-frame maxima as a fraction of audit limits", fontweight="bold")
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            value = matrix[y, x]
            ax.text(
                x,
                y,
                f"{value:.2f}x",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if value > 0.57 else "#183746",
                fontweight="bold",
            )
    bar = fig.colorbar(image, ax=ax, shrink=0.88)
    bar.set_label("observed / limit")
    fig.savefig(ASSETS / "continuity_margins.png", dpi=190, facecolor="white")
    plt.close(fig)


def _read_video_frame(path: Path, frame_index: int) -> np.ndarray:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open {path}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError(f"cannot decode frame {frame_index} from {path.name}")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _save_video_contact_sheet() -> None:
    selected = {"L1": 1000, "L2": 800, "L3": 1400, "L4": 1500, "L5": 6700}
    fig, axes = plt.subplots(3, 2, figsize=(11.4, 6.8), constrained_layout=True)
    flat = axes.ravel()
    for index, (level, frame_index) in enumerate(selected.items()):
        frame = _read_video_frame(VIDEOS / f"{level}_dualview_full.mp4", frame_index)
        flat[index].imshow(frame)
        flat[index].set_title(f"{level} — source frame {frame_index}", fontsize=10, fontweight="bold")
        flat[index].axis("off")
    flat[-1].axis("off")
    flat[-1].text(
        0.5,
        0.62,
        "Overview + robot camera\nOne video frame per trajectory frame",
        ha="center",
        va="center",
        fontsize=13,
        color="#315365",
        fontweight="bold",
    )
    flat[-1].text(
        0.5,
        0.29,
        "18,332 / 18,332 frames decoded\n0 black frames in either view",
        ha="center",
        va="center",
        fontsize=10.5,
        color="#617580",
    )
    fig.savefig(ASSETS / "video_contact_sheet.png", dpi=180, facecolor="white")
    plt.close(fig)


def build_figures() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    results = _load_results()
    _save_architecture()
    _save_l5_placement(results)
    _save_continuity(results)
    _save_video_contact_sheet()


def _inline(value: str) -> str:
    value = html.escape(value, quote=True)
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: (
            f'<link href="{match.group(2)}" color="#176B91">{match.group(1)}</link>'
        ),
        value,
    )
    value = re.sub(r"`([^`]+)`", r'<font face="ReportMono" color="#7A451F">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    # Emphasis markers must not consume the star in algorithm names such as
    # ``A*``.  A Markdown emphasis opener cannot immediately follow a word
    # character in the subset supported by this report parser.
    value = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"<i>\1</i>", value)
    return value


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=9.15,
            leading=13.0,
            textColor=INK,
            spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=sample["Heading1"],
            fontName="ReportSans-Bold",
            fontSize=15.5,
            leading=18.5,
            textColor=NAVY,
            spaceBefore=13,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "subsection": ParagraphStyle(
            "Subsection",
            parent=sample["Heading2"],
            fontName="ReportSans-Bold",
            fontSize=11.7,
            leading=14.5,
            textColor=BLUE,
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "subsubsection": ParagraphStyle(
            "Subsubsection",
            parent=sample["Heading3"],
            fontName="ReportSans-Bold",
            fontSize=10.1,
            leading=12.6,
            textColor=TEAL,
            spaceBefore=7,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=8.95,
            leading=12.3,
            leftIndent=14,
            firstLineIndent=-8,
            textColor=INK,
            spaceAfter=3,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=sample["BodyText"],
            fontName="ReportSans-Oblique",
            fontSize=8.0,
            leading=10.2,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=sample["Code"],
            fontName="ReportMono",
            fontSize=6.9,
            leading=8.9,
            leftIndent=8,
            rightIndent=8,
            textColor=colors.HexColor("#243746"),
            backColor=PALE_GRAY,
            borderColor=GRID,
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=9.7,
            leading=14,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _image_flowable(path: Path, caption: str, max_width: float, max_height: float) -> list:
    reader = ImageReader(str(path))
    width, height = reader.getSize()
    scale = min(max_width / width, max_height / height)
    return [
        Image(str(path), width=width * scale, height=height * scale),
        Paragraph(_inline(caption), _styles()["caption"]),
    ]


def _column_widths(rows: list[list[str]], page_width: float) -> list[float]:
    count = max(len(row) for row in rows)
    header = rows[0]
    weights = []
    for index in range(count):
        header_value = header[index] if index < len(header) else ""
        longest = max(
            [len(header_value)]
            + [min(len(row[index]), 30) for row in rows[1:] if index < len(row)]
        )
        weights.append(max(7.0, min(float(longest), 24.0)))
    total = sum(weights)
    return [page_width * weight / total for weight in weights]


def _table_flowable(rows: list[list[str]], page_width: float) -> Table:
    styles = _styles()
    count = max(len(row) for row in rows)
    font_size = 7.15 if count <= 4 else 6.35
    leading = 9.0 if count <= 4 else 8.0
    cell = ParagraphStyle(
        "TableCell",
        parent=styles["body"],
        fontName="ReportSans",
        fontSize=font_size,
        leading=leading,
        spaceAfter=0,
        textColor=INK,
    )
    head = ParagraphStyle(
        "TableHead",
        parent=cell,
        fontName="ReportSans-Bold",
        textColor=colors.white,
    )
    data = []
    for row_index, row in enumerate(rows):
        row = row + [""] * (count - len(row))
        style = head if row_index == 0 else cell
        data.append([Paragraph(_inline(item.strip()), style) for item in row])
    table = Table(data, colWidths=_column_widths(rows, page_width), repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.35, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GRAY]),
            ]
        )
    )
    return table


def markdown_story(markdown: str, page_width: float) -> list:
    styles = _styles()
    lines = markdown.splitlines()
    story: list = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False
    index = 0
    while index < len(lines) and not lines[index].startswith("## 1."):
        index += 1

    def flush_paragraph() -> None:
        if paragraph:
            story.append(
                Paragraph(_inline(" ".join(part.strip() for part in paragraph)), styles["body"])
            )
            paragraph.clear()

    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Preformatted("\n".join(code), styles["code"] if code else styles["code"]))
                code.clear()
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code.append(lines[index])
            index += 1
            continue
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        image_match = re.match(r"!\[([^]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush_paragraph()
            story.extend(
                _image_flowable(
                    ROOT / image_match.group(2), image_match.group(1), page_width, 112 * mm
                )
            )
            index += 1
            continue
        heading = re.match(r"^(#{2,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            depth = len(heading.group(1))
            style = {2: styles["section"], 3: styles["subsection"], 4: styles["subsubsection"]}[depth]
            story.append(Paragraph(_inline(heading.group(2)), style))
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and re.match(
            r"^\s*\|?\s*:?-", lines[index + 1]
        ):
            flush_paragraph()
            table_lines = [stripped]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = [[cell.strip() for cell in row.strip("|").split("|")] for row in table_lines]
            story.append(_table_flowable(rows, page_width))
            story.append(Spacer(1, 7))
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if bullet or numbered:
            flush_paragraph()
            marker = "•" if bullet else f"{numbered.group(1)}."
            value = bullet.group(1) if bullet else numbered.group(2)
            story.append(Paragraph(f"<b>{marker}</b> {_inline(value)}", styles["bullet"]))
            index += 1
            continue
        paragraph.append(stripped)
        index += 1
    flush_paragraph()
    return story


class TechnicalReportDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=17 * mm,
            rightMargin=17 * mm,
            topMargin=18 * mm,
            bottomMargin=16 * mm,
            title="Reality-Constrained Mobile Manipulation for JCIIOT 2026",
            author="Team BIPT-EDU",
            subject="Technical description, novelty, results, limitations, and verification",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=self._decorate_page)])
        self._outline_counter = 0

    def beforeDocument(self):
        self._outline_counter = 0

    def _decorate_page(self, canvas, doc):
        page = canvas.getPageNumber()
        canvas.saveState()
        if page > 1:
            canvas.setStrokeColor(GRID)
            canvas.setLineWidth(0.5)
            canvas.line(17 * mm, A4[1] - 12 * mm, A4[0] - 17 * mm, A4[1] - 12 * mm)
            canvas.setFont("ReportSans", 7.3)
            canvas.setFillColor(MUTED)
            canvas.drawString(17 * mm, A4[1] - 9.5 * mm, "JCIIOT 2026 RunningRobot — Team BIPT-EDU")
            canvas.drawRightString(A4[0] - 17 * mm, 8.5 * mm, f"Page {page}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        if flowable.style.name not in {"Section", "Subsection", "Subsubsection"}:
            return
        level = {"Section": 0, "Subsection": 1, "Subsubsection": 2}[flowable.style.name]
        text = flowable.getPlainText()
        key = f"heading-{self._outline_counter}"
        self._outline_counter += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


def build_pdf() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = TechnicalReportDoc(str(OUTPUT))
    story: list = [Spacer(1, 21 * mm)]
    story.append(
        Paragraph(
            "Reality-Constrained Mobile Manipulation<br/>"
            "<font color='#176B91'>for JCIIOT 2026 RunningRobot</font>",
            ParagraphStyle(
                "CoverTitle",
                fontName="ReportSans-Bold",
                fontSize=23,
                leading=29,
                alignment=TA_CENTER,
                textColor=NAVY,
                spaceAfter=10,
            ),
        )
    )
    story.append(
        Paragraph(
            "A full-score solution with per-step continuity, reconstructed contacts, and source-complete videos",
            ParagraphStyle(
                "CoverSubtitle",
                fontName="ReportSans",
                fontSize=11.8,
                leading=17,
                alignment=TA_CENTER,
                textColor=MUTED,
                spaceAfter=17,
            ),
        )
    )
    card_style = ParagraphStyle(
        "Card", parent=styles["meta"], fontName="ReportSans", fontSize=9, leading=13
    )
    story.append(
        Table(
            [
                [
                    Paragraph("<b><font size='16'>100 / 100</font></b><br/>objective score", card_style),
                    Paragraph("<b><font size='16'>5 / 5</font></b><br/>realism audits PASS", card_style),
                ],
                [
                    Paragraph("<b><font size='16'>18,332</font></b><br/>recorded physics frames", card_style),
                    Paragraph("<b><font size='16'>5 / 5</font></b><br/>full-frame videos PASS", card_style),
                ],
            ],
            colWidths=[doc.width / 2] * 2,
            rowHeights=[29 * mm, 29 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), PALE_BLUE),
                    ("BACKGROUND", (1, 0), (1, 0), PALE_TEAL),
                    ("BACKGROUND", (0, 1), (0, 1), PALE_ORANGE),
                    ("BACKGROUND", (1, 1), (1, 1), PALE_GRAY),
                    ("BOX", (0, 0), (-1, -1), 0.7, GRID),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            ),
        )
    )
    story.append(Spacer(1, 15 * mm))
    story.append(
        Paragraph(
            "<b>Team BIPT-EDU</b><br/>Report date: 2026-08-05<br/>"
            "Official reference: 129e94a9cff787031472045e19c24a4baeaefc48",
            styles["meta"],
        )
    )
    story.append(Spacer(1, 13 * mm))
    story.append(
        Paragraph(
            "Evidence note: every evaluated level reaches its maximum objective score, passes the independent "
            "realism audit, and has a one-to-one trajectory/video frame mapping. Novelty claims are limited "
            "to this fixed competition setting.",
            ParagraphStyle(
                "CoverNote",
                parent=styles["body"],
                fontSize=8.8,
                leading=12.5,
                alignment=TA_CENTER,
                textColor=MUTED,
                leftIndent=18 * mm,
                rightIndent=18 * mm,
                backColor=PALE_GRAY,
                borderPadding=8,
            ),
        )
    )
    story.append(PageBreak())
    story.append(
        Paragraph(
            "Contents",
            ParagraphStyle("ContentsTitle", parent=styles["section"], spaceBefore=0, spaceAfter=6),
        )
    )
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOC0", fontName="ReportSans-Bold", fontSize=9.2, leading=11.5, textColor=NAVY, spaceBefore=2
        ),
        ParagraphStyle(
            "TOC1", fontName="ReportSans", fontSize=8.4, leading=10.4, leftIndent=12, textColor=INK
        ),
        ParagraphStyle(
            "TOC2", fontName="ReportSans", fontSize=7.8, leading=9.7, leftIndent=24, textColor=MUTED
        ),
    ]
    story.extend([toc, PageBreak()])
    story.extend(markdown_story(MARKDOWN.read_text(encoding="utf-8"), doc.width))
    doc.multiBuild(story)

    reader = PdfReader(str(OUTPUT))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.add_metadata(
        {
            "/Title": "Reality-Constrained Mobile Manipulation for JCIIOT 2026",
            "/Author": "Team BIPT-EDU",
            "/Subject": "Technical description, novelty, results, limitations, and verification",
            "/Keywords": "JCIIOT, MuJoCo, robosuite, mobile manipulation, realism audit",
        }
    )
    normalized = OUTPUT.with_suffix(".normalized.pdf")
    with normalized.open("wb") as stream:
        writer.write(stream)
    normalized.replace(OUTPUT)
    PdfReader(str(OUTPUT))
    return OUTPUT


def main() -> int:
    build_figures()
    output = build_pdf()
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
