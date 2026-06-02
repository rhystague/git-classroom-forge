import json
from io import BytesIO

from app.main import create_app
from app.config import AppConfig
from app.gitlab_client import (
    CourseGroupTree,
    GitLabGroupSummary,
    GitLabProjectSummary,
    GitLabUserLookup,
)


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
        self.fork_source_project = GitLabProjectSummary(
            id=20,
            name="Python Starter",
            path="python-starter",
            path_with_namespace="professional-experience/examples/python-starter",
            web_url="https://gitlab.example.edu.au/professional-experience/examples/python-starter",
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

    def list_course_projects(self, course_path):
        if course_path == "professional-experience":
            return [self.fork_source_project]
        return []

    def get_group_summary(self, full_path):
        if full_path == "professional-experience":
            return self.parent
        return None

    def list_group_projects(self, full_path):
        return []

    def list_project_direct_members(self, full_path):
        return []

    def list_project_all_members(self, full_path):
        return []

    def list_project_invitations(self, full_path):
        return []

    def lookup_users(self, usernames):
        return {
            username: GitLabUserLookup(
                username=username,
                exists=True,
                ambiguous=False,
                id=100,
                name=f"Student {username}",
                state="active",
            )
            for username in usernames
        }


class FailingRouteGitLabClient:
    def browse_head_course_groups(self):
        raise RuntimeError("GitLab API unavailable")

    def list_course_projects(self, course_path):
        raise RuntimeError("GitLab API unavailable secret-token")


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


def test_projects_route_returns_course_fork_source_repositories(tmp_path):
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

    response = app.test_client().get("/groups/professional-experience/projects")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["projects"][0]["name"] == "Python Starter"
    assert (
        payload["projects"][0]["path_with_namespace"]
        == "professional-experience/examples/python-starter"
    )


def test_projects_route_requires_gitlab_configuration(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
            "GITLAB_CLIENT": FakeRouteGitLabClient(),
        }
    )

    response = app.test_client().get("/groups/professional-experience/projects")

    assert response.status_code == 503
    assert response.get_json()["projects"] == []


def test_projects_route_returns_safe_gitlab_error_diagnostics(tmp_path):
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

    response = app.test_client().get("/groups/professional-experience/projects")

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["error"] == "GitLab project browse failed."
    assert payload["error_type"] == "RuntimeError"
    assert "secret-token" not in response.get_data(as_text=True)


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


def test_validate_form_renders_progressive_workflow_sections(tmp_path):
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

    response = app.test_client().get("/validate")

    assert response.status_code == 200
    assert b"Git Classroom Forge" in response.data
    assert b"Class Git Forge" not in response.data
    assert b'data-step="course"' in response.data
    assert b'data-step="assessment"' in response.data
    assert b'data-step="provision"' in response.data
    assert b'id="assessment_step" disabled' in response.data
    assert b'id="provision_step" disabled' in response.data
    assert b"Assessment Provisioning" in response.data
    assert b"Provision Details" in response.data
    assert (
        b"Confirm the target, upload the roster CSV, then run a non-destructive "
        b"dry run before provisioning."
    ) in response.data
    assert b"Choose an existing course or create a new course path." not in response.data
    assert b"#A71D2A" in response.data
    assert b"#14532d" not in response.data
    assert b'class="assessment-flow"' in response.data
    assert b'class="assessment-field-group"' in response.data
    assert b'<div class="grid">' not in response.data
    assert b"Create new offering" in response.data
    assert b'id="create_new_offering"' in response.data
    assert b'id="new_offering_name"' in response.data
    assert b'id="offering_derived_path"' in response.data
    assert b"Offering ID" in response.data
    assert b'for="offering_path">Offering path' not in response.data
    assert b'for="offering_name">Offering name' not in response.data
    assert b"Select assessment" in response.data
    assert b"Create new assessment" in response.data
    assert b'id="create_new_assessment"' in response.data
    assert b'id="new_assessment_name"' in response.data
    assert b'id="assessment_derived_path"' in response.data
    assert b"Assessment ID" in response.data
    assert b"Assessment display name" not in response.data
    assert b"This will be the name of the assessment group." in response.data
    assert b"Base repository" in response.data
    assert b'id="blank_base_repository"' in response.data
    assert b'id="fork_base_repository"' in response.data
    assert b'id="base_repository_full_path"' in response.data
    assert b'name="base_repository_mode"' in response.data
    assert b"Blank repository" in response.data
    assert b"Fork repository" in response.data
    assert b"Select repository to fork" in response.data
    assert b"Template repository" not in response.data
    assert b"loadCourseProjects" in response.data
    assert b"Select assessment type" in response.data
    assert b'class="choice-stack assessment-mode-choices"' in response.data
    assert b"The group name from the CSV will be the project/repository name." in response.data
    assert (
        b"Each student ID from the CSV will get its own project/repository inside "
        b"this assessment."
    ) in response.data
    assert b'id="provision_summary" class="summary-selection-list"' in response.data
    assert b"className = \"summary-value\"" in response.data
    assert b'class="summary-callout"' in response.data
    assert b'class="info-icon"' in response.data
    assert b"Select Student Roster" in response.data
    assert b'id="csv_sample_download"' in response.data
    assert b'href="/sample-csv/group"' in response.data
    assert b'href="/sample-csv/individual"' in response.data
    assert b'id="review_provision"' not in response.data
    assert b"Review Provision" not in response.data
    assert b"Perform Dry Run" in response.data
    assert b'id="provision_button"' not in response.data
    assert b"Provisioning is intentionally unavailable" not in response.data
    assert b'replace(/([a-z])([0-9])/g, "$1-$2")' in response.data
    assert b"offeringDerivedPath.textContent" in response.data
    assert b"assessmentDerivedPath.textContent" in response.data
    assert b"updateProgressiveWorkflow" in response.data


def test_sample_group_csv_download_uses_group_project_format(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
        }
    )

    response = app.test_client().get("/sample-csv/group")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"] == (
        "attachment; filename=group-assessment-sample.csv"
    )
    assert response.data == (
        b"project_path,project_name,student_id\r\n"
        b"team-01,Team 01,22048668\r\n"
        b"team-01,Team 01,22049321\r\n"
        b"team-02,Team 02,22051234\r\n"
    )


def test_sample_individual_csv_download_uses_student_project_format(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
        }
    )

    response = app.test_client().get("/sample-csv/individual")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"] == (
        "attachment; filename=individual-assessment-sample.csv"
    )
    assert response.data == (
        b"student_id,project_path,project_name\r\n"
        b"22048668,22048668,John Smith - 22048668\r\n"
        b"22049321,22049321,Jane Doe - 22049321\r\n"
    )


def test_unknown_sample_csv_type_returns_not_found(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
        }
    )

    response = app.test_client().get("/sample-csv/unsupported")

    assert response.status_code == 404


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
    csv_content = b"""project_path,project_name,student_id
team-01,Team 01,22048668
team-01,Team 01,22049321
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "professional-experience",
            "offering_path": "autumn-2026",
            "offering_name": "Autumn 2026",
            "assessment_path": "pa2621",
            "assessment_name": "PA2621",
            "base_repository_mode": "blank",
            "assessment_mode": "group",
            "csv_file": (BytesIO(csv_content), "projects.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Dry-run result" in response.data
    assert b"Membership actions" in response.data
    assert b'data-step="course"' not in response.data
    assert b"Select your course" not in response.data
    assert b"Assessment Provisioning" not in response.data
    assert b"Perform Dry Run" not in response.data
    assert b"<pre>" not in response.data
    assert b'"mode": "dry-run"' not in response.data
    assert b'id="provision_button"' not in response.data
    assert response.data.count(b"Team 01 (new-course") == 0
    assert response.data.count(b"Team 01 (professional-experience/autumn-2026/pa2621/team-01)") == 1
    assert b"22048668@student.university.edu.au" in response.data
    assert b"22049321@student.university.edu.au" in response.data
    assert b"Add member after project create" in response.data
    report_files = list((tmp_path / "reports").glob("*-dry-run.json"))
    assert len(report_files) == 1
    report = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert report["project_count"] == 1
    assert report["student_count"] == 2
    assert len(report["projects"]) == 1
    assert len(report["projects"][0]["membership_actions"]) == 2
    assert report["projects"][0]["membership_actions"][0]["action"] == "add_member_after_project_create"


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
    csv_content = b"""project_path,project_name,student_id
team-01,Team 01,22048668
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "new-course",
            "offering_path": "autumn-2026",
            "assessment_path": "pa2621",
            "base_repository_mode": "blank",
            "assessment_mode": "group",
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
    csv_content = b"""project_path,project_name,student_id
team-01,Team 01,22048668
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "professional-experience",
            "offering_path": "autumn-2026",
            "assessment_path": "pa2621",
            "base_repository_mode": "blank",
            "assessment_mode": "group",
            "csv_file": (BytesIO(csv_content), "projects.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert b"GITLAB_URL and GITLAB_TOKEN must be set before dry-run validation." in response.data


def test_dry_run_route_requires_assessment_mode(tmp_path):
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
    csv_content = b"""project_path,project_name,student_id
team-01,Team 01,22048668
"""

    response = app.test_client().post(
        "/dry-run",
        data={
            "parent_group_path": "professional-experience",
            "offering_path": "autumn-2026",
            "assessment_path": "pa2621",
            "base_repository_mode": "blank",
            "csv_file": (BytesIO(csv_content), "projects.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Assessment mode is required." in response.data


def test_validate_route_requires_assessment_mode(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
        }
    )
    csv_content = b"""project_path,project_name,student_id
team-01,Team 01,22048668
"""

    response = app.test_client().post(
        "/validate",
        data={"csv_file": (BytesIO(csv_content), "projects.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Assessment mode is required." in response.data
