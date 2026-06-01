from io import BytesIO

from app.main import create_app
from app.config import AppConfig
from app.gitlab_client import CourseGroupTree, GitLabGroupSummary, GitLabUserLookup


def test_health_route_returns_json_status(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
        }
    )

    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "class-git-forge"}


class FakeRouteGitLabClient:
    def __init__(self):
        self.browse_calls = 0
        self.parent = GitLabGroupSummary(
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
        )
        self.offering = GitLabGroupSummary(
            id=2,
            name="Autumn 2026",
            path="autumn-2026",
            full_path="professional-experience/autumn-2026",
            parent_id=1,
            web_url="https://gitlab.example.edu.au/groups/professional-experience/autumn-2026",
            subgroup_count=0,
            project_count=0,
            created_at="2026-01-03T00:00:00Z",
            updated_at="2026-01-04T00:00:00Z",
        )
        self.assessment = GitLabGroupSummary(
            id=3,
            name="PA2621",
            path="pa2621",
            full_path="professional-experience/autumn-2026/pa2621",
            parent_id=2,
            web_url="https://gitlab.example.edu.au/groups/professional-experience/autumn-2026/pa2621",
            subgroup_count=0,
            project_count=0,
            created_at="2026-01-05T00:00:00Z",
            updated_at="2026-01-06T00:00:00Z",
        )

    def browse_head_course_groups(self):
        self.browse_calls += 1
        return [CourseGroupTree(parent=self.parent, offerings=[])]

    def list_offerings(self, course_path):
        return [self.offering] if course_path == "professional-experience" else []

    def list_assessments(self, offering_path):
        if offering_path == "professional-experience/autumn-2026":
            return [self.assessment]
        return []

    def get_group_summary(self, full_path):
        if full_path == "professional-experience":
            return self.parent
        return None

    def list_group_projects(self, full_path):
        return []

    def lookup_users(self, usernames):
        return {
            username: GitLabUserLookup(
                username=username,
                exists=True,
                ambiguous=False,
                id=100,
                name=f"Student {username}",
            )
            for username in usernames
        }


class FailingRouteGitLabClient:
    def browse_head_course_groups(self):
        raise RuntimeError("GitLab API unavailable")


def test_groups_route_returns_head_course_group_tree(tmp_path):
    gitlab = FakeRouteGitLabClient()
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": gitlab,
        }
    )

    response = app.test_client().get("/groups")

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"groups"}
    assert payload["groups"][0]["parent"]["full_path"] == "professional-experience"
    assert payload["groups"][0]["offerings"] == []
    assert gitlab.browse_calls == 1


def test_offerings_route_returns_course_offerings(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": FakeRouteGitLabClient(),
        }
    )

    response = app.test_client().get("/groups/professional-experience/offerings")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["offerings"][0]["full_path"] == "professional-experience/autumn-2026"


def test_assessments_route_returns_offering_assessments(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": FakeRouteGitLabClient(),
        }
    )

    response = app.test_client().get("/groups/professional-experience/autumn-2026/assessments")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["assessments"][0]["full_path"] == "professional-experience/autumn-2026/pa2621"


def test_groups_route_returns_gitlab_error_diagnostics(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": FailingRouteGitLabClient(),
        }
    )

    response = app.test_client().get("/groups")

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["error"] == "GitLab group browse failed."
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_detail"] == "GitLab API unavailable"
    assert "secret-token" not in response.get_data(as_text=True)


def test_validate_form_does_not_block_on_group_browse(tmp_path):
    gitlab = FakeRouteGitLabClient()
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": gitlab,
        }
    )

    response = app.test_client().get("/validate")

    assert response.status_code == 200
    assert b"Select your course" in response.data
    assert b"Create new course" in response.data
    assert b"selected_course_display" in response.data
    assert b"GitLab activity" not in response.data
    assert b"View live GitLab group data as JSON" not in response.data
    assert b"course-select" in response.data
    assert b"selectExistingCourse(course.parent.full_path" in response.data
    assert b"function fetchJson" in response.data
    assert b"AbortController" in response.data
    assert b"loadOfferings" in response.data
    assert b"loadAssessments" in response.data
    assert b"replace(/^\\\\/+|\\\\/+$/g" not in response.data
    assert b"replace(/^\\/+|\\/+$/g" in response.data
    assert gitlab.browse_calls == 0


def test_dry_run_route_persists_snapshot_and_renders_result(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": FakeRouteGitLabClient(),
        }
    )
    csv_content = b"""project_path,project_name,student_ids
team-01,Team 01,22048668;22049321
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "professional-experience",
            "offering_path": "autumn-2026",
            "offering_name": "Autumn 2026",
            "assessment_path": "pa2621",
            "assessment_name": "PA2621",
            "csv_file": (BytesIO(csv_content), "projects.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Dry-run result" in response.data
    report_files = list((tmp_path / "reports").glob("*-dry-run.json"))
    assert len(report_files) == 1


def test_dry_run_route_allows_new_course_path(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                    "GITLAB_URL": "https://gitlab.example.edu.au",
                    "GITLAB_TOKEN": "secret-token",
                }
            ),
            "GITLAB_CLIENT": FakeRouteGitLabClient(),
        }
    )
    csv_content = b"""project_path,project_name,student_ids
team-01,Team 01,22048668
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "new-course",
            "offering_path": "autumn-2026",
            "assessment_path": "pa2621",
            "csv_file": (BytesIO(csv_content), "projects.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"new-course/autumn-2026/pa2621" in response.data


def test_dry_run_route_requires_gitlab_configuration(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env(
                {
                    "DATA_DIR": str(tmp_path),
                }
            ),
        }
    )
    csv_content = b"""project_path,project_name,student_ids
team-01,Team 01,22048668
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "professional-experience",
            "offering_path": "autumn-2026",
            "assessment_path": "pa2621",
            "csv_file": (BytesIO(csv_content), "projects.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert b"GITLAB_URL and GITLAB_TOKEN must be set before dry-run validation." in response.data
