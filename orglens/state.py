"""State aggregation from markdown files."""

from __future__ import annotations

import re


def extract_status(content: str) -> str | None:
    """Extract the status badge from a markdown file.

    Looks for patterns like:
      > **Status:** Active
      > **Status:** Packaged and shipped (Plan 01 complete)
    """
    match = re.search(r'\*\*Status:\*\*\s*(.+)', content)
    if not match:
        return None
    raw = match.group(1).strip()
    # Strip parenthetical suffixes
    raw = re.sub(r'\s*\(.*\)\s*$', '', raw)
    # Strip trailing comma and everything after
    raw = re.sub(r',.*$', '', raw)
    return raw.strip().lower()


def extract_table_statuses(content: str) -> list[dict]:
    """Extract status entries from markdown tables.

    Looks for tables with a Status column and a Name/Plan/Item column.
    Returns list of {"name": ..., "status": ...} dicts.
    """
    results = []
    lines = content.split("\n")

    # Find table header rows
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]  # Remove empty from leading/trailing |

        # Find status column and name column
        status_col = None
        name_col = None
        for j, cell in enumerate(cells):
            if cell.lower() == "status":
                status_col = j
            if cell.lower() in ("name", "plan", "item", "task"):
                name_col = j

        if status_col is None:
            continue

        # If no explicit name column, use the column after # or the first non-trivial one
        if name_col is None:
            for j, cell in enumerate(cells):
                if cell == "#":
                    name_col = j + 1 if j + 1 < len(cells) else None
                    break
            if name_col is None:
                name_col = 0

        # Skip separator row
        if i + 1 < len(lines) and re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i + 1]):
            data_start = i + 2
        else:
            continue

        # Read data rows
        for row_line in lines[data_start:]:
            if "|" not in row_line or row_line.strip() == "":
                break
            row_cells = [c.strip() for c in row_line.split("|")]
            row_cells = [c for c in row_cells if c]

            if len(row_cells) <= max(status_col, name_col):
                continue

            name_raw = row_cells[name_col]
            status_raw = row_cells[status_col]

            # Strip bold markers
            name_raw = re.sub(r'\*\*(.+?)\*\*', r'\1', name_raw)
            status_raw = re.sub(r'\*\*(.+?)\*\*', r'\1', status_raw)

            # Strip markdown links
            name_raw = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', name_raw)

            # Strip leading numbering like "01 —"
            name_raw = re.sub(r'^\d+\s*[—–-]\s*', '', name_raw)

            results.append({
                "name": name_raw.strip(),
                "status": status_raw.strip().lower(),
            })

        break  # Only process the first table with a Status column

    return results
