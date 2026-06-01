import json

from app.csv_parser import ProjectCsvRow
from app.dry_run import DryRunSelection, build_dry_run_report, persist_dry_run_snapshot
from app.gitlab_client import GitLabGroupSummary, GitLabProjectSummary, GitLabUserLookup


class FakeGitLabReadModel:
    def __init__(self):
        self.groups = {
            "professional-experience": GitLabGroupSummary(
                id=1,
                name="Professional Experience",
                path="professional-experience",
                full_path="professional-experience",
                parent_id=None,
                web_url="https://gitlab.example.edu.au/groups/professional-experience",
                subgroup_count=1,
                project_count=0,
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-02T00:00:00Z",
            ),
            "professional-experience/autumn-2026": GitLabGroupSummary(
                id=2,
                name="Autumn 2026",
                path="autumn-2026",
                full_path="professional-experience/autumn-2026",
                parent_id=1,
                web_url="https://gitlab.example.edu.au/groups/professional-experience/autumn-2026",
                subgroup_count=1,
                project_count=0,
                created_at="2026-01-03T00:00:00Z",
                updated_at="2026-01-04T00:00:00Z",
            ),
            "professional-experience/autumn-2026/pa2621": GitLabGroupSummary(
                id=3,
                name="PA2621",
                path="pa2621",
                full_path="professional-experience/autumn-2026/pa2621",
                parent_id=2,
                web_url="https://gitlab.example.edu.au/groups/professional-experience/autumn-2026/pa2621",
                subgroup_count=0,
                project_count=1,
                created_at="2026-01-05T00:00:00Z",
                updated_at="2026-01-06T00:00:00Z",
            ),
        }
        self.projects = {
            "professional-experience/autumn-2026/pa2621": [
                GitLabProjectSummary(
                    id=10,
                    name="Team 01",
                    path="team-01",
                    path_with_namespace="professional-experience/autumn-2026/pa2621/team-01",
                    web_url="https://gitlab.example.edu.au/professional-experience/autumn-2026/pa2621/team-01",
                )
            ]
        }
        self.users = {
            "22048668": GitLabUserLookup(
                username="22048668",
                exists=True,
                ambiguous=False,
                id=100,
                name="Student One",
            ),
            "22049321": GitLabUserLookup(
                username="22049321",
                exists=False,
                ambiguous=False,
                id=None,
                name=None,
            ),
        }

    def get_group_summary(self, full_path):
        return self.groups.get(full_path)

    def list_group_projects(self, full_path):
        return self.projects.get(full_path, [])

    def lookup_users(self, usernames):
        return {username: self.users[username] for username in usernames}


def test_build_dry_run_report_marks_reused_projects_and_missing_users():
    rows = [
        ProjectCsvRow(
            project_path="team-01",
            project_name="Team 01",
            student_ids=["22048668", "22049321"],
        )
    ]
    selection = DryRunSelection(
        parent_group_path="professional-experience",
        offering_path="autumn-2026",
        offering_name="Autumn 2026",
        assessment_path="pa2621",
        assessment_name="PA2621",
    )

    report = build_dry_run_report(
        rows=rows,
        selection=selection,
        gitlab=FakeGitLabReadModel(),
    )

    assert report["mode"] == "dry-run"
    assert report["valid"] is False
    assert report["target"]["offering"]["action"] == "reuse"
    assert report["target"]["assessment"]["action"] == "reuse"
    assert report["projects"][0]["action"] == "reuse"
    assert report["projects"][0]["exists"] is True
    assert report["students"]["22048668"]["exists"] is True
    assert report["students"]["22049321"]["exists"] is False
    assert "GitLab user not found for student ID 22049321." in report["errors"]


def test_build_dry_run_report_allows_new_parent_group_path():
    rows = [
        ProjectCsvRow(
            project_path="team-01",
            project_name="Team 01",
            student_ids=["22048668"],
        )
    ]
    selection = DryRunSelection(
        parent_group_path="new-course",
        offering_path="autumn-2026",
        offering_name="Autumn 2026",
        assessment_path="pa2621",
        assessment_name="PA2621",
    )

    report = build_dry_run_report(
        rows=rows,
        selection=selection,
        gitlab=FakeGitLabReadModel(),
    )

    assert report["valid"] is True
    assert report["target"]["parent"]["action"] == "create_later"
    assert report["target"]["assessment"]["full_path"] == "new-course/autumn-2026/pa2621"


def test_persist_dry_run_snapshot_writes_report_with_run_id(tmp_path):
    report = {
        "run_id": "20260601T010203000000Z-abcd1234",
        "mode": "dry-run",
        "valid": True,
        "errors": [],
        "warnings": [],
    }

    path = persist_dry_run_snapshot(str(tmp_path), report)

    assert path.name == "20260601T010203000000Z-abcd1234-dry-run.json"
    assert path.parent.name == "reports"
    assert json.loads(path.read_text(encoding="utf-8")) == report
