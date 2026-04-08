#!/usr/bin/env python3
"""
validate_project_post.py
========================
Validates that project.md meets the structural requirements before
preview or publish steps proceed.

Exits with code 0 on success, 1 on failure.

Usage:
    python validate_project_post.py [path/to/project.md]

Defaults to project.md in the repository root (GITHUB_WORKSPACE or cwd).
"""

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REQUIRED_FRONTMATTER_FIELDS = ["title", "date", "repo", "tags", "summary"]
REQUIRED_HEADINGS = [
    "## Overview",
    "## Features",
    "## Technical Stack",
    "## Challenges & Solutions",
    "## Status & Future Improvements",
    "## Links",
]
MIN_WORD_COUNT = 100  # Minimum body words (excluding frontmatter)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def load_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def check_not_empty(content: str) -> list[str]:
    if not content.strip():
        return ["File is empty."]
    return []


def check_frontmatter(content: str) -> tuple[list[str], str]:
    """
    Returns (errors, body_without_frontmatter).
    Frontmatter must start on line 1 as '---'.
    """
    errors: list[str] = []
    if not content.startswith("---"):
        errors.append("Frontmatter missing: file must start with '---'.")
        return errors, content

    end = content.find("\n---", 3)
    if end == -1:
        errors.append("Frontmatter closing '---' not found.")
        return errors, content

    frontmatter = content[3:end]
    body = content[end + 4:]

    for field in REQUIRED_FRONTMATTER_FIELDS:
        pattern = re.compile(rf"^\s*{re.escape(field)}\s*:", re.MULTILINE)
        if not pattern.search(frontmatter):
            errors.append(f"Frontmatter missing required field: '{field}'.")

    return errors, body


def check_headings(body: str) -> list[str]:
    errors: list[str] = []
    for heading in REQUIRED_HEADINGS:
        # Match heading at start of a line (allow trailing whitespace)
        pattern = re.compile(r"^" + re.escape(heading) + r"\s*$", re.MULTILINE)
        if not pattern.search(body):
            errors.append(f"Required heading not found: '{heading}'.")
    return errors


def check_word_count(body: str) -> list[str]:
    words = len(body.split())
    if words < MIN_WORD_COUNT:
        return [f"Body too short: {words} words (minimum {MIN_WORD_COUNT})."]
    return []


def check_links_section(body: str) -> list[str]:
    errors: list[str] = []
    links_match = re.search(r"## Links\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
    if links_match:
        links_block = links_match.group(1)
        if "http" not in links_block:
            errors.append("## Links section contains no URLs.")
    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        import os
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))
        path = workspace / "project.md"

    print(f"Validating: {path}")

    content = load_file(path)
    all_errors: list[str] = []

    all_errors.extend(check_not_empty(content))
    if all_errors:
        _report(all_errors)
        sys.exit(1)

    fm_errors, body = check_frontmatter(content)
    all_errors.extend(fm_errors)
    all_errors.extend(check_headings(body))
    all_errors.extend(check_word_count(body))
    all_errors.extend(check_links_section(body))

    _report(all_errors)

    if all_errors:
        sys.exit(1)
    else:
        print("Validation passed.")
        sys.exit(0)


def _report(errors: list[str]) -> None:
    if errors:
        print(f"\n{len(errors)} validation error(s) found:")
        for err in errors:
            print(f"  ✗ {err}")
    else:
        print("  ✓ All checks passed.")


if __name__ == "__main__":
    main()
