# Getting Started

> **Purpose:** This document is the *first stop* after cloning the template. It guides you (or an AI
> co-pilot) to turn this generic template into a focused, real project.
>
> **How to use:** Work through the "Project Initialization" checklist below.  When a prompt says
> *AI-ACTION*, feed the indented question to your AI assistant and paste the answer back here (or
> link to the relevant doc).  Repeat until all placeholders are filled.

---

## 🔰 Project Initialization (AI-Assisted)

| Section             | Prompt (AI-ACTION)                                                                                   |
|---------------------|------------------------------------------------------------------------------------------------------|
| Project Overview    | "Summarize in 2–3 sentences: What problem does this project solve and why does it matter?"             |
| Success Criteria    | "List measurable KPIs or qualitative goals that indicate project success."                               |
| Stakeholders        | "Name primary stakeholders & their roles (e.g., Product Manager, Data Scientist, Domain Expert)."      |
| Data Sources        | "Describe each data source: origin, owner, refresh cadence, and access method."                        |
| Technical Stack     | "Recommend languages, frameworks, cloud services and justify each choice briefly."                   |
| High-Level Timeline | "Propose major milestones with rough dates or sprint numbers."                                       |
| Risks & Mitigations | "List top 3 project risks and suggested mitigations."                                                |
| Governance          | "Outline how decisions will be recorded (e.g., DECISION LOG), and who has merge approval rights."      |

*After each answer is captured, consider linking to deeper docs such as `project_charter.md`,
 `implementation_schedule.md`, or creating new files under `docs/`.*

---

## 🧹 Template Cleanup Checklist

Once the above blanks are filled and the project scope is clear, delete or keep the following assets
as appropriate:

- **`docs/*`**
  - `checklists.md` – Keep if your team will follow the default checklists, otherwise remove or
    merge into another doc.
  - `development_standards.md` – Keep unless your org has a conflicting standard.
  - `knowledge_base.md` – Delete if you don’t plan to maintain an internal KB.
- **`notebooks/`** – Remove if the project will *not* use exploratory notebooks (e.g.,
  production-only pipeline).
- **`flows/` & `prefect.yaml`** – Delete if you won’t orchestrate with Prefect.
- **`models/` & `reports/`** – Delete until the project produces artifacts.
- **CI/CD Workflows in `.github/`** – Cull any workflows you won’t need (e.g., Docker publish) to
  reduce pipeline noise.
- **Docs Sections** – Update `mkdocs.yml` nav to remove deleted pages.

> **Tip:** Perform cleanup in a dedicated pull request so the diff clearly shows removed items.

---
This guide provides instructions for setting up your local development environment to work with the
Vibe Coding Data Science Template.

## Prerequisites

- **Python 3.11+**: Ensure you have a compatible Python version installed.
- **Git**: For version control.
- **`uv`**: The project's package manager. If you don't have it, install it with `pip install uv`.

## 1. Clone the Repository

Clone this repository to your local machine:

```bash
git clone <repository-url>
cd <repository-name>
```

## 2. Set Up the Virtual Environment

This project uses `uv` for package and environment management. Create and activate a virtual environment:

```bash
# Create a virtual environment named .venv
uv venv

# Activate the environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

## 3. Install Dependencies

Install all required project dependencies using `uv`:

```bash
uv pip install -r requirements.txt
```

## 4. Set Up Pre-Commit Hooks

Install the pre-commit hooks to ensure your contributions adhere to the project's quality standards:

```bash
pre-commit install
```

## 5. Run the Tests

Verify that the setup is correct by running the test suite:

```bash
uv run pytest
```

## 6. View the Documentation

To serve the documentation site locally, run the following command:

```bash
mkdocs serve
```

Then, open your browser to `http://127.0.0.1:8000` to view the documentation.

You are now ready to start developing!
