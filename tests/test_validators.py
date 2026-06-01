from app.csv_parser import ProjectCsvRow
from app.validators import validate_project_rows


def test_validator_detects_duplicate_project_paths():
    rows = [
        ProjectCsvRow(project_path="team-01", project_name="Team 01", student_ids=["22048668"]),
        ProjectCsvRow(project_path="team-01", project_name="Team 01 Again", student_ids=["22049321"]),
    ]

    report = validate_project_rows(rows)

    assert report.valid is False
    assert any("Duplicate project path: team-01" == error for error in report.errors)


def test_validator_detects_duplicate_student_ids_within_project():
    rows = [
        ProjectCsvRow(
            project_path="team-01",
            project_name="Team 01",
            student_ids=["22048668", "22048668"],
        )
    ]

    report = validate_project_rows(rows)

    assert report.valid is False
    assert any(
        "Duplicate student ID 22048668 in project team-01" == error
        for error in report.errors
    )
