from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.csv_parser import ProjectCsvRow

GITLAB_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
GITLAB_RESERVED_SUFFIXES = (".git", ".atom")


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    project_count: int
    student_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_project_rows(rows: list[ProjectCsvRow]) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    seen_project_paths: set[str] = set()
    student_projects: dict[str, list[str]] = {}
    student_count = 0

    if not rows:
        errors.append("CSV did not contain any project rows.")

    for row in rows:
        if not row.project_path:
            errors.append("Project path is required.")
        elif row.project_path in seen_project_paths:
            errors.append(f"Duplicate project path: {row.project_path}")
        else:
            seen_project_paths.add(row.project_path)

        if not row.project_name:
            errors.append(f"Project name is required for project {row.project_path or '[missing]'}.")

        if not row.student_ids:
            warnings.append(f"Project {row.project_path or '[missing]'} has no student IDs.")

        seen_students: set[str] = set()
        for student_id in row.student_ids:
            student_count += 1
            if student_id in seen_students:
                errors.append(f"Duplicate student ID {student_id} in project {row.project_path}")
            else:
                seen_students.add(student_id)
            if student_id and not student_id.isdigit():
                errors.append(
                    f"Student ID {student_id} in project {row.project_path} must contain digits only."
                )

        for student_id in seen_students:
            student_projects.setdefault(student_id, []).append(row.project_path or "[missing]")

    for student_id, project_paths in student_projects.items():
        if len(project_paths) > 1:
            errors.append(
                f"Student ID {student_id} appears in multiple projects: "
                f"{', '.join(project_paths)}"
            )

    return ValidationReport(
        valid=not errors,
        project_count=len(rows),
        student_count=student_count,
        errors=errors,
        warnings=warnings,
    )


def validate_gitlab_path_component(path: str, label: str) -> list[str]:
    clean_path = path.strip()
    if not clean_path:
        return [f"{label} is required."]

    if "/" in clean_path:
        return [f"{label} must be a single GitLab path component without slashes."]

    if clean_path in {".", ".."}:
        return [f"{label} cannot be a reserved path component."]

    if clean_path.endswith(GITLAB_RESERVED_SUFFIXES):
        return [f"{label} cannot end with .git or .atom."]

    if not GITLAB_PATH_PATTERN.fullmatch(clean_path):
        return [
            f"{label} must contain only letters, digits, periods, underscores, "
            "or dashes and must start with a letter or digit."
        ]

    return []
