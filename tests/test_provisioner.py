import json

from app.gitlab_client import GitLabGroupSummary, GitLabProjectSummary
from app.provisioner import (
    DryRunSnapshotError,
    load_valid_dry_run_snapshot,
    persist_provisioning_report,
    provision_from_dry_run,
)


def group(group_id, name, path, full_path, parent_id=None):
    return GitLabGroupSummary(
        id=group_id,
        name=name,
        path=path,
        full_path=full_path,
        parent_id=parent_id,
        web_url=f"https://gitlab.example.edu.au/groups/{full_path}",
        subgroup_count=0,
        project_count=0,
        created_at=None,
        updated_at=None,
    )


def project(project_id, name, path, full_path):
    return GitLabProjectSummary(
        id=project_id,
        name=name,
        path=path,
        path_with_namespace=full_path,
        web_url=f"https://gitlab.example.edu.au/{full_path}",
    )


def dry_run_report(*, valid=True, mode="dry-run", base_repository_mode="blank"):
    return {
        "run_id": "20260601T010203000000Z-abcd1234",
        "mode": mode,
        "valid": valid,
        "project_count": 2,
        "student_count": 4,
        "errors": [] if valid else ["dry-run error"],
        "warnings": ["dry-run warning"],
        "target": {
            "parent": {
                "full_path": "new-course",
                "name": "New Course",
                "exists": False,
                "action": "create_later",
            },
            "offering": {
                "full_path": "new-course/autumn-2026",
                "name": "Autumn 2026",
                "exists": False,
                "action": "create_later",
            },
            "assessment": {
                "full_path": "new-course/autumn-2026/pa2621",
                "name": "PA2621",
                "exists": False,
                "action": "create_later",
            },
        },
        "base_repository": {
            "mode": base_repository_mode,
            "name": "Python Starter" if base_repository_mode == "fork" else "Blank repository",
            "full_path": (
                "templates/python-starter" if base_repository_mode == "fork" else None
            ),
            "exists": True,
            "gitlab": None,
        },
        "students": {
            "22048668": {"id": 100, "exists": True},
            "22049321": {"id": None, "exists": False},
            "22051234": {"id": 101, "exists": True},
            "22054567": {"id": None, "exists": False},
        },
        "projects": [
            {
                "project_path": "team-01",
                "project_name": "Team 01",
                "full_path": "new-course/autumn-2026/pa2621/team-01",
                "exists": False,
                "action": "create_later",
                "membership_actions": [
                    {
                        "student_id": "22048668",
                        "email": "22048668@student.university.edu.au",
                        "target_access_level": 30,
                        "action": "add_member_after_project_create",
                        "action_label": "Add member after project create",
                    },
                    {
                        "student_id": "22049321",
                        "email": "22049321@student.university.edu.au",
                        "target_access_level": 30,
                        "action": "create_invite_after_project_create",
                        "action_label": "Invite after project create",
                    },
                ],
            },
            {
                "project_path": "team-02",
                "project_name": "Team 02",
                "full_path": "new-course/autumn-2026/pa2621/team-02",
                "exists": True,
                "action": "reuse",
                "membership_actions": [
                    {
                        "student_id": "22051234",
                        "email": "22051234@student.university.edu.au",
                        "target_access_level": 30,
                        "action": "upgrade_to_developer",
                        "action_label": "Upgrade to Developer",
                    },
                    {
                        "student_id": "22054567",
                        "email": "22054567@student.university.edu.au",
                        "target_access_level": 30,
                        "action": "refresh_invite",
                        "action_label": "Refresh invite",
                    },
                    {
                        "student_id": "22048668",
                        "email": "22048668@student.university.edu.au",
                        "target_access_level": 30,
                        "action": "reuse",
                        "action_label": "Reuse existing access",
                    },
                ],
            },
            {
                "project_path": "empty",
                "project_name": "Empty",
                "full_path": "new-course/autumn-2026/pa2621/empty",
                "exists": False,
                "action": "skip_empty_project",
                "membership_actions": [
                    {
                        "student_id": None,
                        "email": None,
                        "target_access_level": 30,
                        "action": "skip_empty_project",
                        "action_label": "Skip empty project",
                    }
                ],
            },
        ],
    }


class FakeProvisionGitLab:
    def __init__(self):
        self.groups = {}
        self.projects = {
            "new-course/autumn-2026/pa2621/team-02": project(
                20,
                "Team 02",
                "team-02",
                "new-course/autumn-2026/pa2621/team-02",
            ),
        }
        self.calls = []

    def ensure_group(self, *, full_path, name, parent_full_path=None):
        self.calls.append(("ensure_group", full_path, name, parent_full_path))
        if full_path not in self.groups:
            parent_id = self.groups[parent_full_path].id if parent_full_path else None
            self.groups[full_path] = group(
                len(self.groups) + 1,
                name,
                full_path.rsplit("/", 1)[-1],
                full_path,
                parent_id,
            )
        return self.groups[full_path]

    def get_project_summary(self, full_path):
        self.calls.append(("get_project_summary", full_path))
        return self.projects.get(full_path)

    def create_blank_project(self, *, namespace_full_path, name, path):
        self.calls.append(("create_blank_project", namespace_full_path, name, path))
        full_path = f"{namespace_full_path}/{path}"
        self.projects[full_path] = project(len(self.projects) + 30, name, path, full_path)
        return self.projects[full_path]

    def fork_project(self, *, source_full_path, namespace_full_path, name, path):
        self.calls.append(("fork_project", source_full_path, namespace_full_path, name, path))
        full_path = f"{namespace_full_path}/{path}"
        self.projects[full_path] = project(len(self.projects) + 30, name, path, full_path)
        return self.projects[full_path]

    def add_project_member(self, *, project_full_path, user_id, access_level):
        self.calls.append(("add_project_member", project_full_path, user_id, access_level))

    def update_project_member(self, *, project_full_path, user_id, access_level):
        self.calls.append(("update_project_member", project_full_path, user_id, access_level))

    def create_project_invitation(self, *, project_full_path, email, access_level):
        self.calls.append(("create_project_invitation", project_full_path, email, access_level))

    def update_project_invitation(self, *, project_full_path, email, access_level):
        self.calls.append(("update_project_invitation", project_full_path, email, access_level))


def test_load_valid_dry_run_snapshot_requires_valid_dry_run(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    snapshot = reports / "20260601T010203000000Z-abcd1234-dry-run.json"
    snapshot.write_text(json.dumps(dry_run_report(valid=False)), encoding="utf-8")

    try:
        load_valid_dry_run_snapshot(str(tmp_path), "20260601T010203000000Z-abcd1234")
    except DryRunSnapshotError as exc:
        assert str(exc) == "Dry-run snapshot is invalid and cannot be provisioned."
    else:
        raise AssertionError("invalid dry-run snapshot was accepted")

    snapshot.write_text(json.dumps(dry_run_report(mode="provision")), encoding="utf-8")

    try:
        load_valid_dry_run_snapshot(str(tmp_path), "20260601T010203000000Z-abcd1234")
    except DryRunSnapshotError as exc:
        assert str(exc) == "Provisioning requires a dry-run snapshot."
    else:
        raise AssertionError("non-dry-run snapshot was accepted")


def test_provision_from_dry_run_creates_blank_resources_and_memberships():
    gitlab = FakeProvisionGitLab()

    result = provision_from_dry_run(dry_run_report(), gitlab)

    assert result["mode"] == "provision"
    assert result["source_run_id"] == "20260601T010203000000Z-abcd1234"
    assert result["valid"] is True
    assert ("ensure_group", "new-course", "New Course", None) in gitlab.calls
    assert (
        "ensure_group",
        "new-course/autumn-2026",
        "Autumn 2026",
        "new-course",
    ) in gitlab.calls
    assert (
        "create_blank_project",
        "new-course/autumn-2026/pa2621",
        "Team 01",
        "team-01",
    ) in gitlab.calls
    assert (
        "add_project_member",
        "new-course/autumn-2026/pa2621/team-01",
        100,
        30,
    ) in gitlab.calls
    assert (
        "update_project_member",
        "new-course/autumn-2026/pa2621/team-02",
        101,
        30,
    ) in gitlab.calls
    assert (
        "create_project_invitation",
        "new-course/autumn-2026/pa2621/team-01",
        "22049321@student.university.edu.au",
        30,
    ) in gitlab.calls
    assert (
        "update_project_invitation",
        "new-course/autumn-2026/pa2621/team-02",
        "22054567@student.university.edu.au",
        30,
    ) in gitlab.calls
    assert result["projects"][0]["result"] == "created"
    assert result["projects"][1]["result"] == "reused"
    assert result["projects"][2]["result"] == "skipped"
    assert result["projects"][0]["membership_actions"][0]["result"] == "updated"
    assert result["projects"][0]["membership_actions"][1]["result"] == "invited"
    assert result["projects"][1]["membership_actions"][2]["result"] == "reused"


def test_provision_from_dry_run_forks_projects_with_target_name_and_path():
    gitlab = FakeProvisionGitLab()
    report = dry_run_report(base_repository_mode="fork")

    result = provision_from_dry_run(report, gitlab)

    assert result["valid"] is True
    assert (
        "fork_project",
        "templates/python-starter",
        "new-course/autumn-2026/pa2621",
        "Team 01",
        "team-01",
    ) in gitlab.calls


def test_provision_from_dry_run_records_write_failures_without_secret():
    class FailingGitLab(FakeProvisionGitLab):
        def create_blank_project(self, *, namespace_full_path, name, path):
            raise RuntimeError("secret-token leaked by API")

    result = provision_from_dry_run(dry_run_report(), FailingGitLab())

    assert result["valid"] is False
    assert result["projects"][0]["result"] == "failed"
    assert "RuntimeError" in result["errors"][0]
    assert "secret-token" not in json.dumps(result)


def test_provision_from_dry_run_includes_gitlab_error_detail_and_skip_reason():
    class GitLabLikeError(Exception):
        response_code = 403
        error_message = "403 Forbidden: missing permission for secret-token"

    class FailingGitLab(FakeProvisionGitLab):
        def create_blank_project(self, *, namespace_full_path, name, path):
            raise GitLabLikeError("secret-token")

    result = provision_from_dry_run(dry_run_report(), FailingGitLab())

    assert result["valid"] is False
    assert result["projects"][0]["result"] == "failed"
    assert result["projects"][0]["provision_error"] == (
        "GitLabLikeError: 403 Forbidden: missing permission for [redacted]"
    )
    assert result["errors"][0] == (
        "Provisioning failed for project new-course/autumn-2026/pa2621/team-01: "
        "GitLabLikeError: 403 Forbidden: missing permission for [redacted]"
    )
    assert result["projects"][0]["membership_actions"][0]["result"] == "skipped"
    assert result["projects"][0]["membership_actions"][0]["provision_reason"] == (
        "Skipped because project provisioning did not complete."
    )
    assert "secret-token" not in json.dumps(result)


def test_persist_provisioning_report_writes_report_with_run_id(tmp_path):
    report = {"run_id": "20260601T010203000000Z-efgh5678", "mode": "provision"}

    path = persist_provisioning_report(str(tmp_path), report)

    assert path.name == "20260601T010203000000Z-efgh5678-provision.json"
    assert json.loads(path.read_text(encoding="utf-8")) == report
