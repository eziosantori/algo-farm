#!/usr/bin/env python3
"""Transform design report MD files for MkDocs Material presentation.

Applies:
1. Status admonition after H1 title (from Run Log last row)
2. Summary section → compact table inside admonition
3. Phase 2 Debate → collapsible ??? block
4. Run notes → collapsible ??? block

Usage:
    python transform_design.py <input.md> <output.md>
    python transform_design.py <input.md>          # prints to stdout
"""
import re
import sys
from pathlib import Path


def extract_status(lines: list[str]) -> dict:
    """Parse the Run Log table and return status info from the last data row."""
    in_run_log = False
    last_row = None

    for line in lines:
        if line.strip().startswith("## Run Log"):
            in_run_log = True
            continue
        if in_run_log and re.match(r"^\|\s*\d+\s*\|", line):
            last_row = line

    if not last_row:
        return {"status": "draft", "admonition_type": "info", "detail": "Not yet run through workflow"}

    cols = [c.strip() for c in last_row.split("|")]
    # cols: ['', '#', 'Date', 'Instruments', 'TF', 'IS Window', 'Goal', 'Outcome', 'IS Sharpe', 'Robustness', 'File', '']
    run_num = cols[1] if len(cols) > 1 else "?"
    date = cols[2] if len(cols) > 2 else "?"
    outcome = cols[7].strip("`") if len(cols) > 7 else "unknown"
    sharpe = cols[8] if len(cols) > 8 else "?"
    robustness = cols[9] if len(cols) > 9 else "?"

    type_map = {
        "validated": "success",
        "fail-robustness": "warning",
        "rejected": "failure",
        "in-progress": "info",
    }
    adm_type = type_map.get(outcome, "note")
    detail = f"IS Sharpe: {sharpe} | Robustness: {robustness}"

    return {
        "status": outcome,
        "admonition_type": adm_type,
        "run_num": run_num,
        "date": date,
        "detail": detail,
    }


def build_status_admonition(status: dict) -> list[str]:
    """Build status admonition lines."""
    if status["status"] == "draft":
        return [
            f'!!! info "Status: draft"',
            f"    {status['detail']}",
            "",
        ]
    return [
        f'!!! {status["admonition_type"]} "Status: {status["status"]} (Run {status["run_num"]}, {status["date"]})"',
        f"    {status['detail']}",
        "",
    ]


def build_summary_table(lines: list[str], start: int, end: int) -> list[str]:
    """Convert Summary lines to a compact admonition table."""
    result = ['!!! abstract "Strategy Summary"', ""]
    fields = []
    for i in range(start, end):
        line = lines[i].strip()
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)", line)
        if m:
            fields.append((m.group(1), m.group(2)))

    if fields:
        result.append("    | Field | Value |")
        result.append("    |-------|-------|")
        for key, val in fields:
            val_escaped = val.replace("|", "\\|")
            result.append(f"    | **{key}** | {val_escaped} |")
        result.append("")
    return result


def make_collapsible(lines: list[str], start: int, end: int, title: str, style: str = "note") -> list[str]:
    """Wrap a section in a MkDocs collapsible ??? block."""
    result = [f'??? {style} "{title}"', ""]
    for i in range(start, end):
        line = lines[i]
        if line.strip() == "":
            result.append("")
        else:
            result.append("    " + line)
    result.append("")
    return result


def find_sections(lines: list[str]) -> list[tuple[int, int, int, str, int]]:
    """Find all ## and ### sections.

    Returns list of (heading_line, content_start, content_end, title, level).
    content_end excludes trailing blank lines and --- separators.
    """
    headings = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3})\s+(.+)", line)
        if m:
            headings.append((i, m.group(2).strip(), len(m.group(1))))

    result = []
    for idx, (start, title, level) in enumerate(headings):
        content_start = start + 1
        # End at next same-or-higher-level heading, or EOF
        end = len(lines)
        for j in range(idx + 1, len(headings)):
            if headings[j][2] <= level:
                end = headings[j][0]
                break
        # Strip trailing --- separators and blank lines
        while end > content_start and lines[end - 1].strip() in ("---", ""):
            end -= 1
        result.append((start, content_start, end, title, level))

    return result


def transform(content: str) -> str:
    lines = content.split("\n")
    status = extract_status(lines)
    sections = find_sections(lines)

    # Build section lookup
    section_map = {}
    for hs, cs, ce, title, level in sections:
        section_map[title] = (hs, cs, ce, level)

    # Plan replacements: (start_line, end_line_exclusive, replacement_lines)
    # Higher end = actual replacement; end==start = insertion
    replacements = []

    # 1 + 2. Status admonition + Summary → combined replacement
    # Find H1 end (after title + blockquote)
    h1_end = 0
    for i, line in enumerate(lines):
        if line.startswith("# ") and i < 5:
            h1_end = i + 1
            while h1_end < len(lines) and (lines[h1_end].startswith(">") or lines[h1_end].strip() == ""):
                h1_end += 1
            break

    status_lines = build_status_admonition(status)

    if "Summary" in section_map:
        hs, cs, ce, _ = section_map["Summary"]
        summary_lines = build_summary_table(lines, cs, ce)
        # Combined: replace from h1_end (or summary heading) through summary content end
        replace_start = min(h1_end, hs)
        combined = [""] + status_lines + summary_lines
        replacements.append((replace_start, ce, combined))
    else:
        # No summary section, just insert status after H1
        replacements.append((h1_end, h1_end, [""] + status_lines))

    # 3. Phase 2 — Debate → collapsible
    for title, (hs, cs, ce, level) in section_map.items():
        if "Debate" in title and level == 2:
            collapsed = make_collapsible(lines, cs, ce, title, "note")
            replacements.append((hs, ce, collapsed))
            break

    # 4. Run notes → collapsible
    if "Run notes" in section_map:
        hs, cs, ce, _ = section_map["Run notes"]
        collapsed = make_collapsible(lines, cs, ce, "Run Notes", "abstract")
        replacements.append((hs, ce, collapsed))

    # Apply replacements in reverse order (highest start first, larger spans first for ties)
    replacements.sort(key=lambda r: (r[0], r[1]), reverse=True)
    for start, end, new_lines in replacements:
        lines[start:end] = new_lines

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.md> [output.md]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    content = input_path.read_text()
    result = transform(content)

    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(result)
    else:
        print(result)


if __name__ == "__main__":
    main()
