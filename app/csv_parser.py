from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO


GROUP_COLUMNS = {"project_path", "project_name", "student_ids"}
INDIVIDUAL_COLUMNS = {"student_id", "project_path", "project_name"}


class CsvParseError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectCsvRow:
    project_path: str
    project_name: str
    student_ids: list[str]


def parse_projects_csv(content: str) -> list[ProjectCsvRow]:
    reader = csv.DictReader(StringIO(content.strip()))
    columns = set(reader.fieldnames or [])

    if GROUP_COLUMNS.issubset(columns):
        return [_parse_group_row(row) for row in reader if _has_values(row)]

    if INDIVIDUAL_COLUMNS.issubset(columns):
        return [_parse_individual_row(row) for row in reader if _has_values(row)]

    raise CsvParseError(
        "CSV must include required columns for either group rows "
        "(project_path, project_name, student_ids) or individual rows "
        "(student_id, project_path, project_name)."
    )


def _parse_group_row(row: dict[str, str | None]) -> ProjectCsvRow:
    return ProjectCsvRow(
        project_path=_clean(row.get("project_path")),
        project_name=_clean(row.get("project_name")),
        student_ids=_split_student_ids(row.get("student_ids")),
    )


def _parse_individual_row(row: dict[str, str | None]) -> ProjectCsvRow:
    student_id = _clean(row.get("student_id"))
    return ProjectCsvRow(
        project_path=_clean(row.get("project_path")),
        project_name=_clean(row.get("project_name")),
        student_ids=[student_id] if student_id else [],
    )


def _split_student_ids(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _has_values(row: dict[str, str | None]) -> bool:
    return any((value or "").strip() for value in row.values())
