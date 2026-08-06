from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = ROOT / "TECHNICAL_REPORT.md"
LATEX_DIR = ROOT / "report" / "latex"
GENERATED = LATEX_DIR / "generated" / "body.tex"

CITATIONS = {
    "1": "hart1968astar",
    "2": "zhu2020robosuite",
    "3": "mandlekar2021robomimic",
    "4": "ross2011dagger",
    "5": "chi2023diffusion",
    "6": "zhao2023act",
    "7": "fu2025mobilealoha",
    "8": "mujoco2026computation",
}

TABLES = [
    (
        "Submitted navigation and safety parameters",
        "tab:navigation-profile",
        "Q[l,0.85] Q[c,0.58] Q[l,1.75]",
    ),
    (
        "Strict realism-audit acceptance limits",
        "tab:audit-limits",
        "Q[l,2.1] Q[c,0.75]",
    ),
    (
        "Participant implementation components",
        "tab:implementation",
        "Q[l,1.35] Q[l,2.35]",
    ),
    (
        "Software dependencies, roles, and licenses",
        "tab:software",
        "Q[l,0.72] Q[c,0.52] Q[l,1.05] Q[l,1.65]",
    ),
    (
        "Positioning relative to learned-policy methods",
        "tab:method-positioning",
        "Q[l,0.75] Q[l,1.55] Q[l,1.55]",
    ),
    (
        "Objective scores, trajectory sizes, and execution times",
        "tab:score-summary",
        "Q[c,0.42] Q[l,1.55] Q[c,0.50] Q[r,0.55] Q[r,0.72] Q[r,0.76]",
    ),
    (
        "Observed frame-to-frame continuity maxima",
        "tab:continuity",
        "Q[c,0.55] Q[r,0.82] Q[r,0.82] Q[r,0.78] Q[r,0.82]",
    ),
    (
        "Rotation, grasp-contact, and collision audit results",
        "tab:contact-audit",
        "Q[c,0.42] Q[r,0.72] Q[c,1.20] Q[c,0.68] Q[c,1.10] Q[c,0.48]",
    ),
    (
        "L5 per-object contact and terminal-placement results",
        "tab:l5-objects",
        "Q[l,0.62] Q[r,0.72] Q[r,0.82] Q[r,0.88] Q[r,1.05]",
    ),
    (
        "Full-frame video verification results",
        "tab:video-results",
        "Q[c,0.38] Q[l,1.42] Q[r,0.72] Q[c,0.38] Q[c,0.72] Q[c,0.58] Q[c,0.48]",
    ),
]

FIGURE_MACROS = {
    "system_architecture.png": r"\SystemArchitectureFigure",
    "architecture_detail.svg": r"\ArchitectureDetailFigure",
    "state_handoff.svg": r"\StateHandoffFigure",
    "l5_final_placement.png": r"\LFivePlacementFigure",
    "continuity_margins.png": r"\ContinuityMarginsFigure",
    "video_contact_sheet.png": r"\VideoEvidenceFigure",
}


def _escape_plain(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "%": r"\%",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _plain_with_citations(value: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in re.finditer(r"\[([1-8])\]", value):
        parts.append(_escape_plain(value[cursor : match.start()]))
        parts.append(rf"\cite{{{CITATIONS[match.group(1)]}}}")
        cursor = match.end()
    parts.append(_escape_plain(value[cursor:]))
    return "".join(parts)


def _escape_code(value: str) -> str:
    """Escape inline code while adding safe breakpoints for paths and identifiers."""
    result: list[str] = []
    for char in value:
        if char == "_":
            result.append(r"\_\allowbreak{}")
        elif char in {"/", ".", "-"}:
            result.append(_escape_plain(char) + r"\allowbreak{}")
        elif char == " ":
            result.append(r" \allowbreak{}")
        else:
            result.append(_escape_plain(char))
    return "".join(result)


TOKEN = re.compile(
    r"`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|(?<!\w)\*([^*\n]+)\*(?!\w)"
)


def _inline(value: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in TOKEN.finditer(value):
        result.append(_plain_with_citations(value[cursor : match.start()]))
        code, link_text, link_url, bold, italic = match.groups()
        if code is not None:
            result.append(r"\CodeInline{" + _escape_code(code) + "}")
        elif link_text is not None:
            result.append(
                r"\href{" + _escape_plain(link_url) + "}{" + _inline(link_text) + "}"
            )
        elif bold is not None:
            result.append(r"\textbf{" + _inline(bold) + "}")
        elif italic is not None:
            result.append(r"\emph{" + _inline(italic) + "}")
        cursor = match.end()
    result.append(_plain_with_citations(value[cursor:]))
    return "".join(result)


def _slug(value: str) -> str:
    value = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "section"


def _heading_title(value: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", value).strip()


def _table_tex(rows: list[list[str]], index: int) -> str:
    if index >= len(TABLES):
        raise ValueError(f"unexpected Markdown table #{index + 1}")
    caption, label, colspec = TABLES[index]
    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    table_rows = [" & ".join(_inline(cell.strip()) for cell in row) + r" \\" for row in normalized]
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"  \centering",
            rf"  \caption{{{caption}}}",
            rf"  \label{{{label}}}",
            r"  \begin{tblr}{",
            r"    width=\linewidth,",
            rf"    colspec={{{colspec}}},",
            r"    row{1}={bg=ReportNavy,fg=white,font=\bfseries},",
            r"    row{even}={bg=ReportMist},",
            r"    cells={font=\footnotesize,valign=m},",
            r"    hlines={0.35pt,ReportRule},",
            r"    vlines={0.25pt,ReportRule},",
            r"    colsep=3.2pt,rowsep=3.2pt",
            r"  }",
            *["    " + row for row in table_rows],
            r"  \end{tblr}",
            r"\end{table}",
        ]
    )


def convert(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = [
        "% Generated from TECHNICAL_REPORT.md. Do not edit this file directly.",
        "% Run report/build_technical_report_latex.py after editing the Markdown source.",
        "",
    ]
    paragraph: list[str] = []
    list_kind: str | None = None
    table_index = 0
    index = 0

    while index < len(lines) and not lines[index].startswith("## 1."):
        index += 1

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            output.append(rf"\end{{{list_kind}}}")
            output.append("")
            list_kind = None

    def flush_paragraph() -> None:
        if paragraph:
            close_list()
            output.append(_inline(" ".join(part.strip() for part in paragraph)))
            output.append("")
            paragraph.clear()

    while index < len(lines):
        stripped = lines[index].strip()

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            content = "\n".join(code)
            output.extend([r"\begin{ReportCode}", content, r"\end{ReportCode}", ""])
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            index += 1
            continue

        heading = re.match(r"^(#{2,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            depth = len(heading.group(1))
            raw_title = heading.group(2)
            title = _heading_title(raw_title)
            slug = _slug(raw_title)
            if depth == 2 and title == "References":
                output.extend(
                    [
                        r"\FloatBarrier",
                        r"\chapter{References}\label{chap:references}",
                        r"\printbibliography[heading=none]",
                        "",
                    ]
                )
                break
            command = {2: "chapter", 3: "section", 4: "subsection"}[depth]
            prefix = {2: "chap", 3: "sec", 4: "subsec"}[depth]
            if depth == 2:
                output.append(r"\FloatBarrier")
            output.append(rf"\{command}{{{_inline(title)}}}\label{{{prefix}:{slug}}}")
            output.append("")
            index += 1
            continue

        image_match = re.match(r"!\[([^]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush_paragraph()
            close_list()
            filename = Path(image_match.group(2)).name
            macro = FIGURE_MACROS.get(filename)
            if not macro:
                raise ValueError(f"no formal LaTeX figure mapping for {filename}")
            output.extend([macro, ""])
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and re.match(
            r"^\s*\|?\s*:?-", lines[index + 1]
        ):
            flush_paragraph()
            close_list()
            table_lines = [stripped]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = [[cell.strip() for cell in row.strip("|").split("|")] for row in table_lines]
            output.extend([_table_tex(rows, table_index), ""])
            table_index += 1
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if bullet or numbered:
            flush_paragraph()
            desired = "itemize" if bullet else "enumerate"
            if list_kind != desired:
                close_list()
                output.append(rf"\begin{{{desired}}}")
                list_kind = desired
            value = bullet.group(1) if bullet else numbered.group(1)
            output.append(r"  \item " + _inline(value))
            index += 1
            continue

        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    close_list()
    if table_index != len(TABLES):
        raise ValueError(f"expected {len(TABLES)} tables, converted {table_index}")
    return "\n".join(output).rstrip() + "\n"


def main() -> int:
    GENERATED.parent.mkdir(parents=True, exist_ok=True)
    source = MARKDOWN.read_text(encoding="utf-8")
    GENERATED.write_text(convert(source), encoding="utf-8", newline="\n")
    print(GENERATED)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
