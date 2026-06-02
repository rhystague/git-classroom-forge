from __future__ import annotations

import copy
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.csv_parser import ProjectCsvRow
from app.gitlab_client import GitLabGroupSummary, GitLabProjectSummary


SENSITIVE_DETAIL_PATTERNS = (
    re.compile(r"secret[-_ ]?token", re.IGNORECASE),
    re.compile(r"private[-_ ]?token", re.IGNORECASE),
    re.compile(r"bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
)


@dataclass(frozen=True)
class ProvisioningPreview:
    mode: str
    projects: list[ProjectCsvRow]


def build_validation_preview(rows: list[ProjectCsvRow]) -> ProvisioningPreview:
    return ProvisioningPreview(mode="validation-only", projects=rows)


class DryRunSnapshotError(ValueError):
    pass


class GitLabProvisioningClient(Protocol):
    def ensure_group(
        self,
        *,
        full_path: str,
        name: str,
        parent_full_path: str | None = None,
    ) -> GitLabGroupSummary:
        ...

    def get_project_summary(self, full_path: str) -> GitLabProjectSummary | None:
        ...

    def create_blank_project(
        self,
        *,
        namespace_full_path: str,
        name: str,
        path: str,
    ) -> GitLabProjectSummary:
        ...

    def fork_project(
        self,
        *,
        source_full_path: str,
        namespace_full_path: str,
        name: str,
        path: str,
    ) -> GitLabProjectSummary:
        ...

    def add_project_member(
        self,
        *,
        project_full_path: str,
        user_id: int,
        access_level: int,
    ) -> None:
        ...

    def update_project_member(
        self,
        *,
        project_full_path: str,
        user_id: int,
        access_level: int,
    ) -> None:
        ...

    def create_project_invitation(
        self,
        *,
        project_full_path: str,
        email: str,
        access_level: int,
    ) -> None:
        ...

    def update_project_invitation(
        self,
        *,
        project_full_path: str,
        email: str,
        access_level: int,
    ) -> None:
        ...


def load_valid_dry_run_snapshot(data_dir: str, run_id: str) -> dict[str, Any]:
    if not run_id:
        raise DryRunSnapshotError("Dry-run run ID is required.")

    snapshot_path = Path(data_dir) / "reports" / f"{run_id}-dry-run.json"
    if not snapshot_path.exists():
        raise DryRunSnapshotError("Dry-run snapshot was not found.")

    try:
        report = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DryRunSnapshotError("Dry-run snapshot is not valid JSON.") from exc

    if report.get("mode") != "dry-run":
        raise DryRunSnapshotError("Provisioning requires a dry-run snapshot.")
    if not report.get("valid"):
        raise DryRunSnapshotError("Dry-run snapshot is invalid and cannot be provisioned.")

    return report


def persist_provisioning_report(data_dir: str, report: dict[str, Any]) -> Path:
    reports_dir = Path(data_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report['run_id']}-provision.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def provision_from_dry_run(
    report: dict[str, Any],
    gitlab: GitLabProvisioningClient,
) -> dict[str, Any]:
    if report.get("mode") != "dry-run":
        raise DryRunSnapshotError("Provisioning requires a dry-run snapshot.")
    if not report.get("valid"):
        raise DryRunSnapshotError("Dry-run snapshot is invalid and cannot be provisioned.")

    result = _base_provisioning_result(report)
    target = result["target"]
    assessment_full_path = target["assessment"]["full_path"]

    _ensure_target_groups(target, gitlab, result["errors"])

    for project in result["projects"]:
        _provision_project(
            project,
            assessment_full_path,
            result["base_repository"],
            result.get("students", {}),
            gitlab,
            result["errors"],
        )

    result["valid"] = not result["errors"]
    return result


def _base_provisioning_result(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": _new_run_id(),
        "source_run_id": report["run_id"],
        "mode": "provision",
        "valid": False,
        "project_count": report.get("project_count", 0),
        "student_count": report.get("student_count", 0),
        "errors": [],
        "warnings": list(report.get("warnings", [])),
        "target": copy.deepcopy(report.get("target", {})),
        "base_repository": copy.deepcopy(report.get("base_repository", {})),
        "membership": copy.deepcopy(report.get("membership", {})),
        "students": copy.deepcopy(report.get("students", {})),
        "projects": copy.deepcopy(report.get("projects", [])),
    }


def _ensure_target_groups(
    target: dict[str, Any],
    gitlab: GitLabProvisioningClient,
    errors: list[str],
) -> None:
    parent = target["parent"]
    offering = target["offering"]
    assessment = target["assessment"]

    _ensure_group(parent, gitlab, errors, parent_full_path=None)
    _ensure_group(offering, gitlab, errors, parent_full_path=parent["full_path"])
    _ensure_group(assessment, gitlab, errors, parent_full_path=offering["full_path"])


def _ensure_group(
    group: dict[str, Any],
    gitlab: GitLabProvisioningClient,
    errors: list[str],
    *,
    parent_full_path: str | None,
) -> None:
    try:
        summary = gitlab.ensure_group(
            full_path=group["full_path"],
            name=group["name"],
            parent_full_path=parent_full_path,
        )
    except Exception as exc:
        detail = _safe_exception_detail(exc)
        group["result"] = "failed"
        group["provision_error"] = detail
        errors.append(
            f"Provisioning failed for group {group.get('full_path')}: {detail}"
        )
        return

    group["result"] = "reused" if group.get("exists") else "created"
    group["exists"] = True
    group["gitlab"] = _summary_dict(summary)


def _provision_project(
    project: dict[str, Any],
    assessment_full_path: str,
    base_repository: dict[str, Any],
    students: dict[str, Any],
    gitlab: GitLabProvisioningClient,
    errors: list[str],
) -> None:
    action = project.get("action")
    full_path = project["full_path"]
    project_available = False

    if action == "skip_empty_project":
        project["result"] = "skipped"
    elif project.get("exists") or action == "reuse":
        project["result"] = "reused"
        project_available = True
        current = gitlab.get_project_summary(full_path)
        if current is not None:
            project["gitlab"] = _summary_dict(current)
    else:
        try:
            created = _create_project(project, assessment_full_path, base_repository, gitlab)
        except Exception as exc:
            detail = _safe_exception_detail(exc)
            project["result"] = "failed"
            project["provision_error"] = detail
            errors.append(f"Provisioning failed for project {full_path}: {detail}")
        else:
            project["result"] = "created"
            project["exists"] = True
            project["gitlab"] = _summary_dict(created)
            project_available = True

    for membership_action in project.get("membership_actions", []):
        _provision_membership_action(
            membership_action,
            full_path,
            students,
            gitlab,
            errors,
            project_available=project_available,
        )


def _create_project(
    project: dict[str, Any],
    assessment_full_path: str,
    base_repository: dict[str, Any],
    gitlab: GitLabProvisioningClient,
) -> GitLabProjectSummary:
    if base_repository.get("mode") == "fork":
        return gitlab.fork_project(
            source_full_path=base_repository["full_path"],
            namespace_full_path=assessment_full_path,
            name=project["project_name"],
            path=project["project_path"],
        )

    return gitlab.create_blank_project(
        namespace_full_path=assessment_full_path,
        name=project["project_name"],
        path=project["project_path"],
    )


def _provision_membership_action(
    action: dict[str, Any],
    project_full_path: str,
    students: dict[str, Any],
    gitlab: GitLabProvisioningClient,
    errors: list[str],
    *,
    project_available: bool,
) -> None:
    action_name = action.get("action")

    if action_name in {"reuse"}:
        action["result"] = "reused"
        return
    if action_name in {"skip_empty_project"}:
        action["result"] = "skipped"
        return
    if action_name == "error":
        action["result"] = "failed"
        return
    if not project_available:
        action["result"] = "skipped"
        action["provision_reason"] = (
            "Skipped because project provisioning did not complete."
        )
        return

    try:
        _write_membership_action(action, action_name, project_full_path, students, gitlab)
    except Exception as exc:
        detail = _safe_exception_detail(exc)
        action["result"] = "failed"
        action["provision_error"] = detail
        subject = action.get("student_id") or action.get("email") or "unknown student"
        errors.append(
            f"Provisioning failed for membership {subject} on {project_full_path}: "
            f"{detail}"
        )


def _write_membership_action(
    action: dict[str, Any],
    action_name: str,
    project_full_path: str,
    students: dict[str, Any],
    gitlab: GitLabProvisioningClient,
) -> None:
    access_level = int(action.get("target_access_level") or 30)

    if action_name in {"add_member", "add_member_after_project_create"}:
        gitlab.add_project_member(
            project_full_path=project_full_path,
            user_id=_student_user_id(action, students),
            access_level=access_level,
        )
        action["result"] = "updated"
        return

    if action_name == "upgrade_to_developer":
        gitlab.update_project_member(
            project_full_path=project_full_path,
            user_id=_student_user_id(action, students),
            access_level=access_level,
        )
        action["result"] = "updated"
        return

    if action_name in {"create_invite", "create_invite_after_project_create"}:
        gitlab.create_project_invitation(
            project_full_path=project_full_path,
            email=_action_email(action),
            access_level=access_level,
        )
        action["result"] = "invited"
        return

    if action_name in {"refresh_invite", "refresh_invite_after_project_create"}:
        gitlab.update_project_invitation(
            project_full_path=project_full_path,
            email=_action_email(action),
            access_level=access_level,
        )
        action["result"] = "invited"
        return

    action["result"] = "skipped"


def _student_user_id(action: dict[str, Any], students: dict[str, Any]) -> int:
    student_id = action.get("student_id")
    user_id = students.get(student_id, {}).get("id") if student_id else None
    if user_id is None:
        raise ValueError("GitLab user ID is missing from dry-run snapshot.")
    return int(user_id)


def _action_email(action: dict[str, Any]) -> str:
    email = action.get("email")
    if not email:
        raise ValueError("Student email is missing from dry-run snapshot.")
    return str(email)


def _summary_dict(summary: GitLabGroupSummary | GitLabProjectSummary) -> dict[str, Any]:
    return {
        key: value
        for key, value in summary.__dict__.items()
        if not key.startswith("_")
    }


def _safe_exception_detail(exc: Exception) -> str:
    detail_parts = [type(exc).__name__]
    response_code = getattr(exc, "response_code", None)
    error_message = getattr(exc, "error_message", None)

    if error_message:
        message = _normalise_exception_message(str(error_message))
        if response_code and not message.startswith(str(response_code)):
            detail_parts.append(f"{response_code} {message}")
        else:
            detail_parts.append(message)
    elif response_code:
        detail_parts.append(str(response_code))
    else:
        message = str(exc)
        if message:
            detail_parts.append(_normalise_exception_message(message))

    return _redact_detail(": ".join(part for part in detail_parts if part))


def _normalise_exception_message(message: str) -> str:
    cleaned = message.strip()
    if not cleaned:
        return cleaned

    for separator in (":", "-"):
        if separator in cleaned:
            status, remainder = cleaned.split(separator, maxsplit=1)
            if status.strip().isdigit():
                return remainder.strip()

    return cleaned


def _redact_detail(detail: str) -> str:
    redacted = detail
    for pattern in SENSITIVE_DETAIL_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{secrets.token_hex(4)}"
