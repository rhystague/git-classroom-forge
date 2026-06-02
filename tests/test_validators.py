from app.csv_parser import ProjectCsvRow
from app.validators import validate_gitlab_path_component, validate_project_rows


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


def test_validator_detects_duplicate_student_ids_across_projects():
    rows = [
        ProjectCsvRow(project_path="team-01", project_name="Team 01", student_ids=["22048668"]),
        ProjectCsvRow(project_path="team-02", project_name="Team 02", student_ids=["22048668"]),
    ]

    report = validate_project_rows(rows)

    assert report.valid is False
    assert any(
        "Student ID 22048668 appears in multiple projects: team-01, team-02" == error
        for error in report.errors
    )


def test_validator_requires_numeric_student_ids():
    rows = [
        ProjectCsvRow(project_path="team-01", project_name="Team 01", student_ids=["s22048668"]),
    ]

    report = validate_project_rows(rows)

    assert report.valid is False
    assert "Student ID s22048668 in project team-01 must contain digits only." in report.errors


def test_validate_gitlab_path_component_rejects_unsafe_paths():
    errors = validate_gitlab_path_component("bad/path", "Offering path")

    assert errors == ["Offering path must be a single GitLab path component without slashes."]


def test_validate_gitlab_path_component_accepts_gitlab_safe_paths():
    assert validate_gitlab_path_component("placement-journal.1", "Assessment path") == []
