# AGENTS.md

## Purpose
This repository is an internal GitLab course provisioning tool for authorised staff.
It creates a controlled base for validating CSV inputs and, in later work, provisioning
GitLab groups, projects, forks, memberships, audit logs, and reports at scale.

The system direction is:
1. Accept staff-provided offering and assignment details.
2. Accept a CSV describing team or individual repositories.
3. Validate project paths, student IDs, GitLab access, and provisioning intent.
4. Provision through the GitLab API only after an explicit non-destructive validation step.
5. Produce audit and report artefacts that do not expose credentials.

## Repo Shape
- `app/`: Flask application and provisioning domain modules.
- `app/main.py`: Flask application factory and local entrypoint.
- `app/routes.py`: HTTP route boundary for the staff-facing interface.
- `app/csv_parser.py`: Supported CSV formats and parsing.
- `app/validators.py`: Local validation rules before GitLab API checks.
- `app/gitlab_client.py`: Thin wrapper around `python-gitlab`.
- `app/provisioner.py`: Dry-run-safe provisioning model until destructive actions are implemented.
- `app/reports.py`: Report shaping for UI and future export.
- `app/audit.py`: Redacted audit event writing.
- `data/`: Local generated uploads, reports, and logs; contents are ignored by git.
- `docker/dev/`, `compose.yaml`, `scripts/dev`: Docker-first development workflow.

## Change Rules
- Keep provisioning idempotent. Existing groups, projects, and members must be reused or reported clearly.
- Do not add destructive GitLab operations without a validation-only path and tests.
- Do not log GitLab tokens, request authorization headers, or raw credential-bearing exceptions.
- Keep `app/gitlab_client.py` as the only direct `python-gitlab` integration point unless a task explicitly changes the boundary.
- Keep CSV parsing, validation, provisioning, reporting, and audit responsibilities separated.
- Prefer small Flask routes that delegate to domain modules.
- Treat `GET /health`, `GET /validate`, and `POST /validate` as public app interfaces.

## Security Rules
- `GITLAB_TOKEN` must be supplied through environment variables and must never be committed.
- Do not write tokens to reports, audit logs, terminal output, templates, or exceptions.
- Do not enable `python-gitlab` debug mode because it can expose credentials.
- Assume app access is deployment-gated by an internal network or reverse proxy until a task explicitly adds app-level authentication.
- Generated files under `data/` may contain student IDs and must stay out of git.

## Verification Rules
- Every behavior change needs an automated or command-line verification step.
- Changes to CSV shape, validation, GitLab client behavior, reporting, or audit output need tests.
- Minimum checks:
  - `python -m compileall app`
  - `pytest`
- Docker workflow checks:
  - `scripts/dev init`
  - `scripts/dev check`
- If a verification command cannot run in the current environment, state exactly why in the handoff.

## Context7 Requirement
Use Context7 MCP to fetch current documentation whenever a task asks about a library,
framework, SDK, API, CLI tool, or cloud service. Start with `resolve-library-id` unless
the user provides an exact `/org/project` library ID, then use `query-docs` with the
full user question.
