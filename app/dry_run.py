from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.csv_parser import ProjectCsvRow
from app.gitlab_client import GitLabGroupSummary, GitLabProjectSummary, GitLabUserLookup
from app.validators import validate_gitlab_path_component, validate_project_rows


class GitLabReadModel(Protocol):
    def get_group_summary(self, full_path: str) -> GitLabGroupSummary | None:
        ...

    def list_group_projects(self, full_path: str) -> list[GitLabProjectSummary]:
        ...

    def get_project_summary(self, full_path: str) -> GitLabProjectSummary | None:
        ...

    def lookup_users(self, usernames: tuple[str, ...]) -> dict[str, GitLabUserLookup]:
        ...


@dataclass(frozen=True)
class DryRunSelection:
    parent_group_path: str
    offering_path: str
    offering_name: str
    assessment_path: str
    assessment_name: str
    base_repository_mode: str
    base_repository_full_path: str

    @property
    def offering_full_path(self) -> str:
        return f"{self.parent_group_path}/{self.offering_path}"

    @property
    def assessment_full_path(self) -> str:
        return f"{self.offering_full_path}/{self.assessment_path}"


def build_dry_run_report(
    rows: list[ProjectCsvRow],
    selection: DryRunSelection,
    gitlab: GitLabReadModel,
) -> dict[str, object]:
    validation = validate_project_rows(rows)
    errors = list(validation.errors)
    warnings = list(validation.warnings)

    errors.extend(_selection_errors(selection))
    base_repository, base_repository_errors = _base_repository(selection, gitlab)
    errors.extend(base_repository_errors)
    for row in rows:
        errors.extend(validate_gitlab_path_component(row.project_path, "Project path"))

    parent_group = None
    offering_group = None
    assessment_group = None
    existing_projects: dict[str, GitLabProjectSummary] = {}

    parent_group = gitlab.get_group_summary(selection.parent_group_path)
    if parent_group is not None:
        offering_group = gitlab.get_group_summary(selection.offering_full_path)
        if offering_group is not None:
            assessment_group = gitlab.get_group_summary(selection.assessment_full_path)
            if assessment_group is not None:
                existing_projects = {
                    project.path: project
                    for project in gitlab.list_group_projects(selection.assessment_full_path)
                }

    student_usernames = tuple(sorted({student_id for row in rows for student_id in row.student_ids}))
    student_lookups = gitlab.lookup_users(student_usernames) if student_usernames else {}
    for username in student_usernames:
        lookup = student_lookups.get(
            username,
            GitLabUserLookup(
                username=username,
                exists=False,
                ambiguous=False,
                id=None,
                name=None,
            ),
        )
        if lookup.ambiguous:
            errors.append(f"GitLab user lookup is ambiguous for student ID {username}.")
        elif not lookup.exists:
            errors.append(f"GitLab user not found for student ID {username}.")

    requested_project_paths = {row.project_path for row in rows}
    extra_project_paths = sorted(set(existing_projects) - requested_project_paths)
    for project_path in extra_project_paths:
        warnings.append(
            f"Existing GitLab project not present in CSV will be left unchanged: {project_path}"
        )

    return {
        "run_id": _new_run_id(),
        "mode": "dry-run",
        "valid": not errors,
        "project_count": validation.project_count,
        "student_count": validation.student_count,
        "errors": errors,
        "warnings": warnings,
        "target": {
            "parent": _target_group(
                full_path=selection.parent_group_path,
                name=selection.parent_group_path,
                summary=parent_group,
                missing_action="create_later",
            ),
            "offering": _target_group(
                full_path=selection.offering_full_path,
                name=selection.offering_name or selection.offering_path,
                summary=offering_group,
                missing_action="create_later",
            ),
            "assessment": _target_group(
                full_path=selection.assessment_full_path,
                name=selection.assessment_name or selection.assessment_path,
                summary=assessment_group,
                missing_action="create_later",
            ),
        },
        "base_repository": base_repository,
        "projects": [
            _project_plan(selection.assessment_full_path, row, existing_projects.get(row.project_path))
            for row in rows
        ],
        "students": {
            username: asdict(
                student_lookups.get(
                    username,
                    GitLabUserLookup(
                        username=username,
                        exists=False,
                        ambiguous=False,
                        id=None,
                        name=None,
                    ),
                )
            )
            for username in student_usernames
        },
    }


def persist_dry_run_snapshot(data_dir: str, report: dict[str, object]) -> Path:
    reports_dir = Path(data_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report['run_id']}-dry-run.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _selection_errors(
    selection: DryRunSelection,
) -> list[str]:
    errors: list[str] = []
    for label, path in (
        ("Parent group path", selection.parent_group_path),
        ("Offering path", selection.offering_path),
        ("Assessment path", selection.assessment_path),
    ):
        errors.extend(validate_gitlab_path_component(path, label))

    if selection.base_repository_mode not in {"blank", "fork"}:
        errors.append("Base repository selection is required.")
    elif (
        selection.base_repository_mode == "fork"
        and not selection.base_repository_full_path
    ):
        errors.append("Fork source repository is required.")

    return errors


def _base_repository(
    selection: DryRunSelection,
    gitlab: GitLabReadModel,
) -> tuple[dict[str, object], list[str]]:
    if selection.base_repository_mode == "blank":
        return (
            {
                "mode": "blank",
                "name": "Blank repository",
                "full_path": None,
                "exists": True,
                "gitlab": None,
            },
            [],
        )

    if selection.base_repository_mode != "fork":
        return (
            {
                "mode": selection.base_repository_mode,
                "name": "",
                "full_path": None,
                "exists": False,
                "gitlab": None,
            },
            [],
        )

    full_path = selection.base_repository_full_path
    if not full_path:
        return (
            {
                "mode": "fork",
                "name": "",
                "full_path": None,
                "exists": False,
                "gitlab": None,
            },
            [],
        )

    project = gitlab.get_project_summary(full_path)
    errors = [] if project else [f"Fork source repository not found: {full_path}"]
    return (
        {
            "mode": "fork",
            "name": project.name if project else full_path,
            "full_path": full_path,
            "exists": project is not None,
            "gitlab": asdict(project) if project else None,
        },
        errors,
    )


def _target_group(
    full_path: str,
    name: str,
    summary: GitLabGroupSummary | None,
    missing_action: str,
) -> dict[str, object]:
    return {
        "full_path": full_path,
        "name": summary.name if summary else name,
        "exists": summary is not None,
        "action": "reuse" if summary else missing_action,
        "gitlab": asdict(summary) if summary else None,
    }


def _project_plan(
    assessment_full_path: str,
    row: ProjectCsvRow,
    existing_project: GitLabProjectSummary | None,
) -> dict[str, object]:
    return {
        "project_path": row.project_path,
        "project_name": row.project_name,
        "student_ids": row.student_ids,
        "full_path": f"{assessment_full_path}/{row.project_path}",
        "exists": existing_project is not None,
        "action": "reuse" if existing_project else "create_later",
        "gitlab": asdict(existing_project) if existing_project else None,
    }


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{secrets.token_hex(4)}"
