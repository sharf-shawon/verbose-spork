#!/usr/bin/env python3
"""
generate_project_post.py
========================
Gather repository context, fill the prompt template, and produce project.md.

AI generation strategy (pluggable)
-----------------------------------
This script implements a *placeholder* generation step that produces a
well-structured project.md from the repository context without requiring an
external AI API.  It is intentionally designed so that the placeholder can be
swapped for any LLM call (OpenAI, Anthropic, GitHub Models, etc.) by replacing
the `generate_content()` function.

Expected interface for a custom generator
------------------------------------------
Input  : a filled prompt string (UTF-8 text)
Output : a Markdown string starting with YAML frontmatter

Environment variables (optional, used by the placeholder & any replacement):
  AI_API_KEY        – API key for the chosen LLM provider
  AI_MODEL          – model name / endpoint (default: placeholder)
  OUTPUT_PATH       – where to write project.md (default: project.md)
  REPO_FULL_NAME    – override auto-detected owner/repo
  DEFAULT_BRANCH    – override auto-detected default branch
"""

import os
import sys
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE", Path(__file__).resolve().parents[2]))
OUTPUT_PATH = Path(os.environ.get("OUTPUT_PATH", REPO_ROOT / "project.md"))
PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "prompts" / "project-post.prompt.md"
AI_MODEL = os.environ.get("AI_MODEL", "placeholder")
REPO_FULL_NAME = os.environ.get("GITHUB_REPOSITORY", "")
DEFAULT_BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

# Files to scan for package / dependency context
PACKAGE_FILE_PATTERNS = [
    "package.json", "package-lock.json", "yarn.lock",
    "requirements.txt", "Pipfile", "pyproject.toml", "setup.py", "setup.cfg",
    "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "Gemfile.lock",
    "composer.json",
    "Cargo.toml",
    "*.csproj", "*.sln",
]

MAX_FILE_CHARS = 4000  # cap individual file content sent to prompt


# ---------------------------------------------------------------------------
# Context gathering helpers
# ---------------------------------------------------------------------------

def _read_file(path: Path, max_chars: int = MAX_FILE_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"
        return text.strip()
    except OSError:
        return ""


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except Exception:
        return ""


def gather_readme() -> str:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        p = REPO_ROOT / name
        if p.exists():
            return _read_file(p)
    return "(no README found)"


def gather_package_files() -> str:
    import glob as _glob

    collected: list[str] = []
    seen: set[str] = set()
    for pattern in PACKAGE_FILE_PATTERNS:
        for match in _glob.glob(str(REPO_ROOT / "**" / pattern), recursive=True):
            p = Path(match)
            # skip node_modules, vendor, .git, venv, dist
            parts = p.relative_to(REPO_ROOT).parts
            if any(part in {"node_modules", "vendor", ".git", "venv", ".venv", "dist", "__pycache__"} for part in parts):
                continue
            key = str(p.relative_to(REPO_ROOT))
            if key in seen:
                continue
            seen.add(key)
            content = _read_file(p, max_chars=1500)
            collected.append(f"### {key}\n{content}")
    return "\n\n".join(collected) if collected else "(none detected)"


def gather_docker_files() -> str:
    import glob as _glob

    collected: list[str] = []
    for pattern in ("Dockerfile*", "docker-compose*.yml", "docker-compose*.yaml"):
        for match in _glob.glob(str(REPO_ROOT / "**" / pattern), recursive=True):
            p = Path(match)
            parts = p.relative_to(REPO_ROOT).parts
            if any(part in {"node_modules", "vendor", ".git"} for part in parts):
                continue
            key = str(p.relative_to(REPO_ROOT))
            content = _read_file(p, max_chars=1500)
            collected.append(f"### {key}\n{content}")
    return "\n\n".join(collected) if collected else "(none detected)"


def gather_ci_files() -> str:
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        return "(none detected)"
    collected: list[str] = []
    for p in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        content = _read_file(p, max_chars=1500)
        collected.append(f"### .github/workflows/{p.name}\n{content}")
    return "\n\n".join(collected) if collected else "(none detected)"


def gather_source_tree() -> str:
    lines = _run(["git", "ls-files"]).splitlines()
    # Build a compact tree limited to 2 levels of depth
    tree: dict = {}
    for line in lines:
        parts = Path(line).parts
        if not parts:
            continue
        top = parts[0]
        if top == ".git":
            continue
        if top not in tree:
            tree[top] = set()
        if len(parts) >= 2:
            tree[top].add(parts[1])

    output_lines: list[str] = []
    for top in sorted(tree):
        children = sorted(tree[top])
        if children:
            output_lines.append(f"{top}/")
            for child in children[:20]:
                output_lines.append(f"  {child}")
            if len(children) > 20:
                output_lines.append(f"  ... ({len(children) - 20} more)")
        else:
            output_lines.append(top)
    return "\n".join(output_lines) if output_lines else "(empty repository)"


def gather_language_stats() -> str:
    lines = _run(["git", "ls-files"]).splitlines()
    from collections import Counter
    ext_counts: Counter = Counter()
    for line in lines:
        ext = Path(line).suffix.lower()
        if ext:
            ext_counts[ext] += 1
    if not ext_counts:
        return "(no files tracked)"
    total = sum(ext_counts.values())
    rows = []
    for ext, count in ext_counts.most_common(10):
        pct = count / total * 100
        rows.append(f"{ext:12s}  {count:4d} files  ({pct:.1f}%)")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Prompt filling
# ---------------------------------------------------------------------------

def fill_prompt(template: str, ctx: dict) -> str:
    for key, value in ctx.items():
        template = template.replace("{" + key + "}", value)
    return template


# ---------------------------------------------------------------------------
# Placeholder content generation
# (Replace the body of this function with an LLM API call if desired.)
# ---------------------------------------------------------------------------

def generate_content(prompt: str) -> str:
    """
    Placeholder generator: produces a minimal but valid project.md from the
    context embedded in the prompt.  Replace this function body with an LLM
    API call to get AI-written content.

    Replacement interface
    ---------------------
    Input : prompt  – the filled prompt string
    Output: a string starting with '---\\n' (YAML frontmatter) followed by
            Markdown sections.

    Example replacement using openai-python >= 1.0:
    -----------------------------------------------
        import openai
        client = openai.OpenAI(api_key=os.environ["AI_API_KEY"])
        response = client.chat.completions.create(
            model=os.environ.get("AI_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": "You are a technical writer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content
    """
    # Extract key values from the context block inside the prompt
    repo = _extract_between(prompt, "**Repository:** ", "\n").strip() or REPO_FULL_NAME or "unknown/repo"
    branch = _extract_between(prompt, "**Default branch:** ", "\n").strip() or "main"
    generated_at = _extract_between(prompt, "**Generated at:** ", "\n").strip() or datetime.now(timezone.utc).isoformat()
    date_str = generated_at[:10]

    # Derive a human-readable title from the repo name
    repo_name = repo.split("/")[-1] if "/" in repo else repo
    title = repo_name.replace("-", " ").replace("_", " ").title()
    repo_url = f"https://github.com/{repo}"

    # Pull a short summary from the README block (first non-empty line after heading)
    readme_block = _extract_between(prompt, "### README\n\n```\n", "\n```").strip()
    summary = _first_meaningful_line(readme_block, fallback=f"Source code for {title}.")

    # Collect package file names for tech stack hints
    package_block = _extract_between(prompt, "### Package / dependency files detected\n\n```\n", "\n```").strip()
    tech_hints = _derive_tech_hints(package_block)

    content = textwrap.dedent(f"""\
        ---
        title: "{title}"
        date: "{date_str}"
        repo: "{repo}"
        tags: [{_tags_from_hints(tech_hints)}]
        summary: "{summary}"
        ---

        ## Overview

        {title} is a software project hosted at [{repo}]({repo_url}).
        {summary}

        <!-- assumption: overview derived from README and repository name; update with project-specific details -->

        ## Features

        <!-- assumption: features list is a placeholder; replace with actual feature list from project documentation -->

        - Core functionality as described in the repository README
        - Version-controlled source with a structured commit history
        - Automated CI/CD pipeline via GitHub Actions

        ## Technical Stack

        {_format_tech_stack(tech_hints)}

        ## Challenges & Solutions

        <!-- assumption: no specific challenges documented; section populated with generic placeholder -->

        - **Challenge:** Setting up a reproducible development environment.
          **Solution:** Dependency management files and CI workflows ensure consistent builds.

        - **Challenge:** Maintaining code quality over time.
          **Solution:** Automated workflows lint and test code on every push.

        ## Status & Future Improvements

        <!-- assumption: project status unknown; update with current state -->

        - Current status: active development (see repository for latest commits)
        - Planned improvements: see open issues and project board in the repository

        ## Links

        - [Repository]({repo_url})
        - [Issues]({repo_url}/issues)
        - [Actions]({repo_url}/actions)
    """)
    return content


def _extract_between(text: str, start: str, end: str) -> str:
    s = text.find(start)
    if s == -1:
        return ""
    s += len(start)
    e = text.find(end, s)
    if e == -1:
        return text[s:]
    return text[s:e]


def _first_meaningful_line(text: str, fallback: str = "") -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if len(line) > 15:
            return line[:200]
    return fallback


def _derive_tech_hints(package_block: str) -> list[str]:
    hints = []
    lower = package_block.lower()
    if "package.json" in lower:
        hints.append("Node.js / JavaScript")
    if "requirements.txt" in lower or "pyproject.toml" in lower or "setup.py" in lower:
        hints.append("Python")
    if "go.mod" in lower:
        hints.append("Go")
    if "pom.xml" in lower or "build.gradle" in lower:
        hints.append("Java / JVM")
    if "cargo.toml" in lower:
        hints.append("Rust")
    if "gemfile" in lower:
        hints.append("Ruby")
    if "composer.json" in lower:
        hints.append("PHP")
    if ".csproj" in lower or ".sln" in lower:
        hints.append(".NET / C#")
    if "dockerfile" in lower or "docker-compose" in lower:
        hints.append("Docker")
    if not hints:
        hints.append("<!-- assumption: language/stack unknown; update with actual stack -->")
    return hints


def _format_tech_stack(hints: list[str]) -> str:
    if not hints:
        return "- <!-- assumption: stack unknown -->"
    return "\n".join(f"- {h}" for h in hints)


def _tags_from_hints(hints: list[str]) -> str:
    tag_map = {
        "Node.js": "nodejs",
        "JavaScript": "javascript",
        "Python": "python",
        "Go": "go",
        "Java": "java",
        "Rust": "rust",
        "Ruby": "ruby",
        "PHP": "php",
        ".NET": "dotnet",
        "Docker": "docker",
    }
    tags = set()
    for hint in hints:
        for key, tag in tag_map.items():
            if key.lower() in hint.lower():
                tags.add(f'"{tag}"')
    tags.add('"open-source"')
    return ", ".join(sorted(tags))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not PROMPT_TEMPLATE_PATH.exists():
        print(f"ERROR: prompt template not found at {PROMPT_TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ctx = {
        "REPO_FULL_NAME": REPO_FULL_NAME or "unknown/repo",
        "DEFAULT_BRANCH": DEFAULT_BRANCH,
        "GENERATED_AT": generated_at,
        "README_CONTENT": gather_readme(),
        "PACKAGE_FILES": gather_package_files(),
        "DOCKER_FILES": gather_docker_files(),
        "CI_FILES": gather_ci_files(),
        "SOURCE_TREE": gather_source_tree(),
        "LANGUAGE_STATS": gather_language_stats(),
    }

    filled_prompt = fill_prompt(template, ctx)

    print(f"Using model: {AI_MODEL}")
    if AI_MODEL == "placeholder":
        print("NOTE: Running in placeholder mode. Set AI_MODEL and AI_API_KEY to use an LLM.")

    content = generate_content(filled_prompt)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
