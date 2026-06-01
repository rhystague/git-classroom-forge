from __future__ import annotations

from dataclasses import dataclass

from app.csv_parser import ProjectCsvRow


@dataclass(frozen=True)
class ProvisioningPreview:
    mode: str
    projects: list[ProjectCsvRow]


def build_validation_preview(rows: list[ProjectCsvRow]) -> ProvisioningPreview:
    return ProvisioningPreview(mode="validation-only", projects=rows)
