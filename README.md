# verbose-spork

> **Automated project documentation generator powered by GitHub Actions.**  
> Analyzes any repository and produces a structured, portfolio-ready `project.md` — with optional LLM enhancement.

---

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Features](#features)
- [How to Use](#how-to-use)
  - [Prerequisites](#prerequisites)
  - [Running the Workflow](#running-the-workflow)
  - [Preview vs. Publish Mode](#preview-vs-publish-mode)
- [Configuration](#configuration)
  - [Using a Real LLM](#using-a-real-llm)
- [Output Format](#output-format)
- [How to Contribute](#how-to-contribute)
- [Project Structure](#project-structure)

---

## Overview

**verbose-spork** is a reusable GitHub Actions workflow that automatically generates a `project.md` write-up for your repository. It scans your codebase — README, package files, Dockerfiles, CI workflows, and source tree — builds a rich context prompt, and produces a consistently structured Markdown document.

Out of the box it runs in **placeholder mode** (no external API required). Swap in your own LLM API key to get AI-authored, human-quality project write-ups.

---

## How It Works

```
Checkout repo
     │
     ▼
Gather context (Python)
 ├─ README.md / README.rst
 ├─ package.json, requirements.txt, go.mod, …
 ├─ Dockerfile / docker-compose.*
 ├─ .github/workflows/*.yml
 ├─ git ls-files  →  source tree (depth ≤ 2)
 └─ file-extension stats  →  language breakdown
     │
     ▼
Fill prompt template  (.github/prompts/project-post.prompt.md)
     │
     ▼
Generate content
 ├─ Placeholder mode  – built-in Python generator (no API key needed)
 └─ LLM mode          – plug in any OpenAI-compatible API
     │
     ▼
Validate project.md  (frontmatter, headings, word count, links)
     │
     ├─ Preview mode  → artifact + job summary
     └─ Publish mode  → branch + pull request
```

---

## Features

- **Zero-dependency preview** — runs entirely with Python 3.11 and the standard library; no API key required.
- **Pluggable LLM backend** — replace one Python function to integrate OpenAI, Anthropic, GitHub Models, or any other provider.
- **Structured output validation** — a dedicated validator checks frontmatter fields, required headings, minimum word count, and link presence before anything is published.
- **Safe publish flow** — changes are only pushed when content has actually changed; the workflow creates or updates a dedicated branch and opens a pull request for human review.
- **Reusable** — all tuneable constants (`OUTPUT_PATH`, `PR_BRANCH`, `PR_TITLE`, `AI_MODEL`, …) are defined as workflow-level `env` variables, making it easy to drop the workflow into any repository.

---

## How to Use

### Prerequisites

- A GitHub repository with Actions enabled.
- **"Allow GitHub Actions to create and approve pull requests"** must be turned on:  
  `Settings → Actions → General → Workflow permissions`

No local tooling is required — everything runs in the GitHub-hosted runner.

### Running the Workflow

1. Navigate to **Actions → Generate Project Post** in your repository.
2. Click **Run workflow**.
3. Choose a mode (see below) and click **Run workflow** to confirm.

### Preview vs. Publish Mode

| Mode | `publish` input | What happens |
|------|-----------------|--------------|
| **Preview** | `false` (default) | `project.md` is written, validated, uploaded as an artifact, and shown in the job summary. Nothing is committed. |
| **Publish** | `true` | If content changed, a branch (`automation/project-post`) is created/updated and a pull request is opened automatically. |

Always run in preview mode first to review the output before publishing.

---

## Configuration

All tuneable values live in the `env` block at the top of `.github/workflows/generate-project-post.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_PATH` | `project.md` | Path (relative to repo root) where the file is written. |
| `PR_BRANCH` | `automation/project-post` | Branch name used when publishing. |
| `PR_TITLE` | `docs: add / update project.md` | Title of the auto-generated pull request. |
| `PR_LABEL` | `documentation` | Label applied to the pull request. |
| `PYTHON_VERSION` | `3.11` | Python version used by the runner. |
| `AI_MODEL` | `placeholder` | Model name passed to the generator. Set to a real model when using an LLM. |

### Using a Real LLM

1. Add your API key as a repository secret (e.g. `AI_API_KEY`).
2. Set `AI_MODEL` in the workflow `env` block to your chosen model (e.g. `gpt-4o`).
3. Uncomment the `AI_API_KEY` line in the **Generate project.md** step.
4. Replace the body of `generate_content()` in `.github/scripts/generate_project_post.py` with your LLM API call.

A commented example using the `openai` Python package is already included in the function's docstring.

---

## Output Format

The generated `project.md` always contains:

```
YAML frontmatter   title · date · repo · tags · summary
─────────────────────────────────────────────────────────
## Overview
## Features
## Technical Stack
## Challenges & Solutions
## Status & Future Improvements
## Links
```

Sections that cannot be inferred from the repository context are populated with clearly marked placeholder comments (`<!-- assumption: … -->`), making human review straightforward.

---

## How to Contribute

Contributions are welcome! Please follow these steps:

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-improvement
   ```

2. **Make your changes.**  
   - The Python scripts live in `.github/scripts/`.  
   - The prompt template is `.github/prompts/project-post.prompt.md`.  
   - The workflow definition is `.github/workflows/generate-project-post.yml`.

3. **Test locally** (optional but encouraged):
   ```bash
   # From the repository root
   python .github/scripts/generate_project_post.py
   python .github/scripts/validate_project_post.py project.md
   ```

4. **Open a pull request** against the `main` branch with a clear description of what you changed and why.

### Contribution ideas

- Add support for additional LLM providers (Anthropic, Mistral, Google Gemini, …).
- Extend the context gatherer to capture more file types or project metadata.
- Improve the placeholder generator's heuristics.
- Add unit tests for the Python helper functions.
- Enhance the validation rules (e.g. check for placeholder assumptions left unreviewed).

---

## Project Structure

```
.
├── .github/
│   ├── prompts/
│   │   └── project-post.prompt.md   # Prompt template filled with repo context
│   ├── scripts/
│   │   ├── generate_project_post.py # Context gathering + content generation
│   │   └── validate_project_post.py # Structural validation of the output file
│   └── workflows/
│       └── generate-project-post.yml # GitHub Actions workflow definition
└── README.md
```