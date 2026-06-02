from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable


GROUP_COLUMNS = {"project_path", "project_name", "student_id"}
INDIVIDUAL_COLUMNS = {"student_id", "project_path", "project_name"}


class CsvParseError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectCsvRow:
    project_path: str
    project_name: str
    student_ids: list[str]


def parse_projects_csv(content: str, assessment_mode: str) -> list[ProjectCsvRow]:
    mode = assessment_mode.strip().lower()
    if mode not in {"group", "individual"}:
        raise CsvParseError("Assessment mode is required.")

    reader = csv.DictReader(StringIO(content.strip()))
    columns = set(reader.fieldnames or [])

    if mode == "group" and GROUP_COLUMNS.issubset(columns):
        return _parse_group_rows(row for row in reader if _has_values(row))

    if mode == "individual" and INDIVIDUAL_COLUMNS.issubset(columns):
        return _parse_individual_rows(row for row in reader if _has_values(row))

    if mode == "group":
        raise CsvParseError(
            "Group CSV must include required columns: project_path, project_name, student_id."
        )

    raise CsvParseError(
        "Individual CSV must include required columns: student_id, project_path, project_name."
    )


def _parse_group_rows(rows: Iterable[dict[str, str | None]]) -> list[ProjectCsvRow]:
    grouped_rows: dict[str, ProjectCsvRow] = {}

    for row in rows:
        project_path = _clean(row.get("project_path"))
        project_name = _clean(row.get("project_name"))
        student_id = _clean(row.get("student_id"))
        if ";" in student_id:
            raise CsvParseError(
                "Group CSV student_id must contain one student ID per row, "
                "not semicolon-delimited values."
            )
        existing_row = grouped_rows.get(project_path)
        if existing_row is None:
            existing_row = ProjectCsvRow(
                project_path=project_path,
                project_name=project_name,
                student_ids=[],
            )
            grouped_rows[project_path] = existing_row
        elif existing_row.project_name != project_name:
            raise CsvParseError(f"Conflicting project names for path {project_path}.")

        if student_id:
            existing_row.student_ids.append(student_id)

    return list(grouped_rows.values())


def _parse_individual_row(row: dict[str, str | None]) -> ProjectCsvRow:
    student_id = _clean(row.get("student_id"))
    return ProjectCsvRow(
        project_path=_clean(row.get("project_path")),
        project_name=_clean(row.get("project_name")),
        student_ids=[student_id] if student_id else [],
    )


def _parse_individual_rows(rows: Iterable[dict[str, str | None]]) -> list[ProjectCsvRow]:
    parsed_rows: list[ProjectCsvRow] = []
    seen_project_paths: set[str] = set()
    for row in rows:
        parsed_row = _parse_individual_row(row)
        if parsed_row.project_path in seen_project_paths:
            raise CsvParseError(
                f"Duplicate project path in individual CSV: {parsed_row.project_path}"
            )
        seen_project_paths.add(parsed_row.project_path)
        parsed_rows.append(parsed_row)
    return parsed_rows


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _has_values(row: dict[str, str | None]) -> bool:
    return any((value or "").strip() for value in row.values())
