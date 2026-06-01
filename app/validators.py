from __future__ import annotations

from dataclasses import dataclass, field

from app.csv_parser import ProjectCsvRow


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

    return ValidationReport(
        valid=not errors,
        project_count=len(rows),
        student_count=student_count,
        errors=errors,
        warnings=warnings,
    )
