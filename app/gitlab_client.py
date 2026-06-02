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
class GitLabProjectMember:
    user_id: int
    username: str
    name: str | None
    access_level: int
    state: str | None = None


@dataclass(frozen=True)
class GitLabProjectInvitation:
    email: str
    access_level: int | None


@dataclass(frozen=True)
class GitLabUserLookup:
    username: str
    exists: bool
    ambiguous: bool
    id: int | None
    name: str | None
    state: str | None = None


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

    def list_project_direct_members(self, full_path: str) -> list[GitLabProjectMember]:
        client = self._make_client()
        project = client.projects.get(full_path)
        return [
            self._project_member(member)
            for member in project.members.list(get_all=True)
        ]

    def list_project_all_members(self, full_path: str) -> list[GitLabProjectMember]:
        client = self._make_client()
        project = client.projects.get(full_path)
        return [
            self._project_member(member)
            for member in project.members_all.list(get_all=True)
        ]

    def list_project_invitations(self, full_path: str) -> list[GitLabProjectInvitation]:
        client = self._make_client()
        project = client.projects.get(full_path)
        return [
            self._project_invitation(invitation)
            for invitation in project.invitations.list(get_all=True)
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
                    state=getattr(user, "state", None),
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

    def ensure_group(
        self,
        *,
        full_path: str,
        name: str,
        parent_full_path: str | None = None,
    ) -> GitLabGroupSummary:
        client = self._make_client()
        try:
            return self._group_summary(client.groups.get(full_path))
        except Exception:
            pass

        path = full_path.rsplit("/", maxsplit=1)[-1]
        payload = {"name": name, "path": path}
        if parent_full_path:
            parent = client.groups.get(parent_full_path)
            payload["parent_id"] = getattr(parent, "id")

        group = client.groups.create(payload)
        return self._group_summary(group)

    def create_blank_project(
        self,
        *,
        namespace_full_path: str,
        name: str,
        path: str,
    ) -> GitLabProjectSummary:
        client = self._make_client()
        namespace = client.groups.get(namespace_full_path)
        project = client.projects.create(
            {
                "name": name,
                "path": path,
                "namespace_id": getattr(namespace, "id"),
            }
        )
        return self._project_summary(project)

    def fork_project(
        self,
        *,
        source_full_path: str,
        namespace_full_path: str,
        name: str,
        path: str,
    ) -> GitLabProjectSummary:
        client = self._make_client()
        source_project = client.projects.get(source_full_path)
        namespace = client.groups.get(namespace_full_path)
        fork = source_project.forks.create(
            {
                "namespace_id": getattr(namespace, "id"),
                "name": name,
                "path": path,
            }
        )
        return self._project_summary(fork)

    def add_project_member(
        self,
        *,
        project_full_path: str,
        user_id: int,
        access_level: int,
    ) -> None:
        client = self._make_client()
        project = client.projects.get(project_full_path)
        project.members.create({"user_id": user_id, "access_level": access_level})

    def update_project_member(
        self,
        *,
        project_full_path: str,
        user_id: int,
        access_level: int,
    ) -> None:
        client = self._make_client()
        project = client.projects.get(project_full_path)
        member = project.members.get(user_id)
        member.access_level = access_level
        member.save()

    def create_project_invitation(
        self,
        *,
        project_full_path: str,
        email: str,
        access_level: int,
    ) -> None:
        client = self._make_client()
        project = client.projects.get(project_full_path)
        project.invitations.create({"email": email, "access_level": access_level})

    def update_project_invitation(
        self,
        *,
        project_full_path: str,
        email: str,
        access_level: int,
    ) -> None:
        client = self._make_client()
        project = client.projects.get(project_full_path)
        project.invitations.update(email, {"access_level": access_level})

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

    def _project_member(self, member) -> GitLabProjectMember:
        return GitLabProjectMember(
            user_id=getattr(member, "id", getattr(member, "user_id", None)),
            username=getattr(member, "username", ""),
            name=getattr(member, "name", None),
            access_level=int(getattr(member, "access_level", 0)),
            state=getattr(member, "state", None),
        )

    def _project_invitation(self, invitation) -> GitLabProjectInvitation:
        return GitLabProjectInvitation(
            email=getattr(invitation, "email", ""),
            access_level=_optional_int_attr(invitation, "access_level"),
        )


def _optional_int_attr(obj, *names: str) -> int | None:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return int(value)
    return None
