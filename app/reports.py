from __future__ import annotations

from dataclasses import asdict

from app.provisioner import ProvisioningPreview
from app.validators import ValidationReport


def validation_response(report: ValidationReport, preview: ProvisioningPreview) -> dict[str, object]:
    return {
        "valid": report.valid,
        "project_count": report.project_count,
        "student_count": report.student_count,
        "errors": report.errors,
        "warnings": report.warnings,
        "mode": preview.mode,
        "projects": [asdict(project) for project in preview.projects],
    }
