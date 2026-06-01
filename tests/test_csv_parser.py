import pytest

from app.csv_parser import CsvParseError, parse_projects_csv


def test_parser_accepts_group_based_csv():
    content = """project_path,project_name,student_ids
team-01,PA2621 Team 01,22048668
team-01,PA2621 Team 01,22049321
team-02,PA2621 Team 02,22051234
"""

    rows = parse_projects_csv(content)

    assert len(rows) == 2
    assert rows[0].project_path == "team-01"
    assert rows[0].project_name == "PA2621 Team 01"
    assert rows[0].student_ids == ["22048668", "22049321"]
    assert rows[1].student_ids == ["22051234"]


def test_parser_accepts_individual_based_csv():
    content = """student_id,project_path,project_name
22048668,22048668,PA2621 - 22048668
22049321,22049321,PA2621 - 22049321
"""

    rows = parse_projects_csv(content)

    assert [row.project_path for row in rows] == ["22048668", "22049321"]
    assert [row.student_ids for row in rows] == [["22048668"], ["22049321"]]


def test_parser_rejects_group_csv_with_semicolon_delimited_students():
    content = """project_path,project_name,student_ids
team-01,PA2621 Team 01,22048668;22049321
"""

    with pytest.raises(CsvParseError, match="one student ID per row"):
        parse_projects_csv(content)


def test_parser_rejects_missing_required_columns():
    content = """project_path,student_ids
team-01,22048668
"""

    with pytest.raises(CsvParseError, match="required columns"):
        parse_projects_csv(content)
