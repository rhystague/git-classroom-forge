from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig


@dataclass(frozen=True)
class GitLabConnectionStatus:
    configured: bool
    authenticated: bool
    message: str


@dataclass(frozen=True)
class GitLabGroupSummary:
    id: int
    name: str
    path: str
    full_path: str
    parent_id: int | None
    web_url: str
    subgroup_count: int | None
    project_count: int | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class GitLabProjectSummary:
    id: int
    name: str
    path: str
    path_with_namespace: str
    web_url: str


@dataclass(frozen=True)
class GitLabUserLookup:
    username: str
    exists: bool
    ambiguous: bool
    id: int | None
    name: str | None


@dataclass(frozen=True)
class OfferingGroupTree:
    group: GitLabGroupSummary
    assessments: list[GitLabGroupSummary]


@dataclass(frozen=True)
class CourseGroupTree:
    parent: GitLabGroupSummary
    offerings: list[OfferingGroupTree]


class GitLabClient:
    def __init__(self, config: AppConfig):
        self._config = config

    def connection_status(self) -> GitLabConnectionStatus:
        if not self._config.gitlab_configured:
            return GitLabConnectionStatus(
                configured=False,
                authenticated=False,
                message="GITLAB_URL and GITLAB_TOKEN must be set before GitLab validation.",
            )

        try:
            client = self._make_client()
            client.auth()
        except Exception as exc:  # pragma: no cover - exercised with integration credentials.
            return GitLabConnectionStatus(
                configured=True,
                authenticated=False,
                message=f"GitLab authentication failed: {type(exc).__name__}",
            )

        return GitLabConnectionStatus(
            configured=True,
            authenticated=True,
            message="GitLab authentication succeeded.",
        )

    def browse_head_course_groups(self) -> list[CourseGroupTree]:
        client = self._make_client()
        parent_groups = client.groups.list(top_level_only=True, get_all=True)
        return [
            CourseGroupTree(
                parent=self._group_summary(parent),
                offerings=[],
            )
            for parent in parent_groups
        ]

    def list_offerings(self, course_path: str) -> list[GitLabGroupSummary]:
        client = self._make_client()
        course = client.groups.get(course_path)
        return [
            self._group_summary(offering)
            for offering in course.subgroups.list(get_all=True)
        ]

    def list_assessments(self, offering_path: str) -> list[GitLabGroupSummary]:
        client = self._make_client()
        offering = client.groups.get(offering_path)
        return [
            self._group_summary(assessment)
            for assessment in offering.subgroups.list(get_all=True)
        ]

    def list_course_projects(self, course_path: str) -> list[GitLabProjectSummary]:
        client = self._make_client()
        course = client.groups.get(course_path)
        return [
            self._project_summary(project)
            for project in course.projects.list(get_all=True, include_subgroups=True)
        ]

    def get_group_summary(self, full_path: str) -> GitLabGroupSummary | None:
        client = self._make_client()
        try:
            group = client.groups.get(full_path)
        except Exception:
            return None

        return self._group_summary(group)

    def get_project_summary(self, full_path: str) -> GitLabProjectSummary | None:
        client = self._make_client()
        try:
            project = client.projects.get(full_path)
        except Exception:
            return None

        return self._project_summary(project)

    def list_group_projects(self, full_path: str) -> list[GitLabProjectSummary]:
        client = self._make_client()
        group = client.groups.get(full_path)
        return [
            self._project_summary(project)
            for project in group.projects.list(get_all=True)
        ]

    def lookup_users(self, usernames: tuple[str, ...]) -> dict[str, GitLabUserLookup]:
        client = self._make_client()
        results: dict[str, GitLabUserLookup] = {}

        for username in usernames:
            users = client.users.list(username=username, get_all=True)
            exact_matches = [
                user for user in users if getattr(user, "username", None) == username
            ]
            if len(exact_matches) == 1:
                user = exact_matches[0]
                results[username] = GitLabUserLookup(
                    username=username,
                    exists=True,
                    ambiguous=False,
                    id=getattr(user, "id", None),
                    name=getattr(user, "name", None),
                )
            elif len(exact_matches) > 1:
                results[username] = GitLabUserLookup(
                    username=username,
                    exists=False,
                    ambiguous=True,
                    id=None,
                    name=None,
                )
            else:
                results[username] = GitLabUserLookup(
                    username=username,
                    exists=False,
                    ambiguous=False,
                    id=None,
                    name=None,
                )

        return results

    def _make_client(self):
        import gitlab

        return gitlab.Gitlab(
            url=self._config.gitlab_url,
            private_token=self._config.gitlab_token,
            user_agent="class-git-forge/0.1",
            timeout=5,
        )

    def _full_group(self, client, group_ref):
        return client.groups.get(getattr(group_ref, "id"))

    def _group_summary(self, group, subgroup_count: int | None = None) -> GitLabGroupSummary:
        return GitLabGroupSummary(
            id=getattr(group, "id"),
            name=getattr(group, "name", ""),
            path=getattr(group, "path", ""),
            full_path=getattr(group, "full_path", getattr(group, "path", "")),
            parent_id=getattr(group, "parent_id", None),
            web_url=getattr(group, "web_url", ""),
            subgroup_count=subgroup_count
            if subgroup_count is not None
            else _optional_int_attr(group, "subgroup_count", "subgroups_count"),
            project_count=_optional_int_attr(group, "projects_count", "project_count"),
            created_at=getattr(group, "created_at", None),
            updated_at=getattr(group, "updated_at", None),
        )

    def _project_summary(self, project) -> GitLabProjectSummary:
        return GitLabProjectSummary(
            id=getattr(project, "id"),
            name=getattr(project, "name", ""),
            path=getattr(project, "path", ""),
            path_with_namespace=getattr(
                project,
                "path_with_namespace",
                getattr(project, "full_path", getattr(project, "path", "")),
            ),
            web_url=getattr(project, "web_url", ""),
        )


def _optional_int_attr(obj, *names: str) -> int | None:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return int(value)
    return None
