# Project Charter

This document is the single source of truth for project goals, scope, and technical context.
It should be updated as the project evolves, especially the DECISION LOG.

> 📚 For a high-level entry point and links to all documentation, see [README.md](../README.md).

## Project Overview

**Project Name:** {{ project_name }}

**Project Vision:** {{ project_vision }}

**Technical Goal:** {{ project_technical_goal }}

**Repository:** {{ git_repository_link }}

## Users & User Stories

### Primary Persona

**Target User:** {{ user_persona_description }}

- **Name:** {{ user_persona_name }}
- **Role:** {{ user_persona_role }}
- **Pain Points:** {{ user_persona_pain_points }}
- **Goals:** {{ user_persona_goals }}

### Core User Stories

As a {{ user_type }}, I want {{ functionality }} so that {{ benefit_value }}.

**Story 1:** As a {{ primary_persona }}, I want to {{ main_action }} so that {{ primary_benefit }}.

- Priority: Must-have

**Story 2:** As a {{ user_type }}, I want to {{ supporting_action }} so that {{ supporting_benefit }}.

- Priority: Should-have

## Features & Scope

**Core Features:** {{ core_features }}

### Must-Have (MVP)

**Feature A:** {{ feature_description }}

- User Story: Story 1
- Implementation: {{ impl_task_id }}
- User Impact: High

**Feature B:** {{ feature_description }}

- User Story: Story 2
- Implementation: {{ impl_task_id }}
- User Impact: Medium

### Should-Have (Post-MVP)

**Feature C:** {{ feature_description }}

- Implementation: {{ impl_task_id }}

### Out of Scope

- {{ out_of_scope_feature }}
- {{ out_of_scope_integration }}

## Architecture

### High-Level Summary

{{ architecture_summary }}

### System Diagram

```mermaid
+------------------+           +------------------+           +------------------+
| React Frontend   |   <--->   | FastAPI Backend  |   <--->   | PostgreSQL DB    |
| (Vercel)         |           | (Render)         |           | (Supabase)       |
+------------------+           +------------------+           +------------------+
```

### Folder Structure

- `/src`: Contains the main source code for the project
- `/docs`: Contains all project documentation, including planning, guides, and logs
- `/notebooks`: Contains Jupyter notebooks for experimentation and analysis
- `/data`: Contains raw, interim, and processed data (not versioned by Git)
- `/tests`: Contains all unit, integration, and functional tests

## Technology Stack

| Category | Technology | Version | Notes |
|----------|------------|---------|-------|
| Package Management | uv | latest | High-performance Python package manager and resolver |
| Core Language | Python | 3.11+ | Primary programming language |
| Linting & Formatting | Ruff | latest | Combines linting, formatting, and import sorting |
| Experiment Tracking | MLflow | latest | For managing the ML lifecycle, including tracking experiments |
| Data Lineage | OpenLineage | latest | For collecting data lineage metadata |
| Testing | Pytest | latest | Framework for writing and running tests |
| Documentation | MkDocs | latest | Static site generator for project documentation |
| Orchestration | Prefect | latest | Workflow orchestration and scheduling |

## Risks & Assumptions

### Key Assumptions

**User Behavior:** We assume users will {{ assumed_user_behavior }}.

- Validation: Test via user interviews in {{ impl_task_id }}

**Technical:** We assume {{ assumed_technology }}.

- Validation: Proof of concept in {{ impl_task_id }}

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Third-party API failure | {{ risk_probability }} | {{ risk_impact }} | {{ risk_mitigation }} |

## Decision Log

*Key architectural and product decisions will be recorded here as the project evolves.*

---

*This document consolidates the project definition, technical context, and scope appendix into a
single source of truth.*
