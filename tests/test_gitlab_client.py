from app.config import AppConfig
from app.gitlab_client import GitLabClient


class FakeManager:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return self.items


class FakeObject:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeGroupsManager:
    def __init__(self, objects):
        self.objects = objects
        self.calls = []

    def get(self, key):
        self.calls.append(key)
        return self.objects[key]

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return [
            group
            for group in self.objects.values()
            if getattr(group, "parent_id", None) is None
        ]


class FakeUsersManager:
    def __init__(self):
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        username = kwargs["username"]
        if username == "22048668":
            return [FakeObject(id=100, username="22048668", name="Student One")]
        return []


class FakeGitLab:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        assessment = FakeObject(
            id=3,
            name="PA2621",
            path="pa2621",
            full_path="professional-experience/autumn-2026/pa2621",
            parent_id=2,
            web_url="https://gitlab.example.edu.au/groups/professional-experience/autumn-2026/pa2621",
            created_at="2026-01-05T00:00:00Z",
            updated_at="2026-01-06T00:00:00Z",
            projects_count=4,
            subgroups=FakeManager([]),
            projects=FakeManager([]),
        )
        fork_source_project = FakeObject(
            id=20,
            name="Python Starter",
            path="python-starter",
            path_with_namespace="professional-experience/examples/python-starter",
            web_url="https://gitlab.example.edu.au/professional-experience/examples/python-starter",
            members=FakeManager(
                [
                    FakeObject(
                        id=100,
                        username="22048668",
                        name="Student One",
                        access_level=30,
                        state="active",
                    )
                ]
            ),
            members_all=FakeManager(
                [
                    FakeObject(
                        id=100,
                        username="22048668",
                        name="Student One",
                        access_level=30,
                        state="active",
                    ),
                    FakeObject(
                        id=101,
                        username="22049321",
                        name="Student Two",
                        access_level=30,
                        state="active",
                    ),
                ]
            ),
            invitations=FakeManager(
                [
                    FakeObject(
                        email="22051234@student.university.edu.au",
                        access_level=30,
                    )
                ]
            ),
        )
        offering = FakeObject(
            id=2,
            name="Autumn 2026",
            path="autumn-2026",
            full_path="professional-experience/autumn-2026",
            parent_id=1,
            web_url="https://gitlab.example.edu.au/groups/professional-experience/autumn-2026",
            created_at="2026-01-03T00:00:00Z",
            updated_at="2026-01-04T00:00:00Z",
            projects_count=0,
            subgroups=FakeManager([assessment]),
            projects=FakeManager([]),
        )
        parent = FakeObject(
            id=1,
            name="Professional Experience",
            path="professional-experience",
            full_path="professional-experience",
            parent_id=None,
            web_url="https://gitlab.example.edu.au/groups/professional-experience",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            projects_count=0,
            subgroups=FakeManager([offering]),
            projects=FakeManager([fork_source_project]),
        )
        self.fork_source_project = fork_source_project
        self.groups = FakeGroupsManager(
            {
                "professional-experience": parent,
                "professional-experience/autumn-2026": offering,
                "professional-experience/autumn-2026/pa2621": assessment,
                2: offering,
                3: assessment,
            }
        )
        self.users = FakeUsersManager()
        self.projects = FakeGroupsManager(
            {
                "professional-experience/examples/python-starter": fork_source_project,
            }
        )


def test_gitlab_client_browses_head_course_groups(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    tree = client.browse_head_course_groups()

    assert tree[0].parent.full_path == "professional-experience"
    assert tree[0].offerings == []
    assert fake_gitlab.groups.calls[0] == {"top_level_only": True, "get_all": True}
    assert 2 not in fake_gitlab.groups.calls


def test_gitlab_client_lists_offerings_for_one_course(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    offerings = client.list_offerings("professional-experience")

    assert offerings[0].full_path == "professional-experience/autumn-2026"
    assert fake_gitlab.groups.calls == ["professional-experience"]


def test_gitlab_client_lists_assessments_for_one_offering(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    assessments = client.list_assessments("professional-experience/autumn-2026")

    assert assessments[0].full_path == "professional-experience/autumn-2026/pa2621"
    assert fake_gitlab.groups.calls == ["professional-experience/autumn-2026"]


def test_gitlab_client_lists_course_projects_including_subgroups(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    projects = client.list_course_projects("professional-experience")

    assert projects[0].path_with_namespace == "professional-experience/examples/python-starter"
    assert fake_gitlab.groups.calls == ["professional-experience"]
    assert fake_gitlab.groups.objects["professional-experience"].projects.calls == [
        {"get_all": True, "include_subgroups": True}
    ]


def test_gitlab_client_get_project_summary_returns_project(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    project = client.get_project_summary("professional-experience/examples/python-starter")

    assert project is not None
    assert project.name == "Python Starter"
    assert fake_gitlab.projects.calls == ["professional-experience/examples/python-starter"]


def test_gitlab_client_looks_up_users_by_exact_username(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    users = client.lookup_users(("22048668", "22049321"))

    assert users["22048668"].exists is True
    assert users["22048668"].name == "Student One"
    assert users["22049321"].exists is False


def test_gitlab_client_lists_project_direct_members(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    members = client.list_project_direct_members("professional-experience/examples/python-starter")

    assert members[0].username == "22048668"
    assert members[0].access_level == 30
    assert fake_gitlab.fork_source_project.members.calls == [{"get_all": True}]


def test_gitlab_client_lists_project_all_members(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    members = client.list_project_all_members("professional-experience/examples/python-starter")

    assert [member.username for member in members] == ["22048668", "22049321"]
    assert fake_gitlab.fork_source_project.members_all.calls == [{"get_all": True}]


def test_gitlab_client_lists_project_invitations(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    invitations = client.list_project_invitations("professional-experience/examples/python-starter")

    assert invitations[0].email == "22051234@student.university.edu.au"
    assert invitations[0].access_level == 30
    assert fake_gitlab.fork_source_project.invitations.calls == [{"get_all": True}]


def test_gitlab_client_sets_short_api_timeout(monkeypatch):
    created = {}

    def fake_gitlab_factory(**kwargs):
        created.update(kwargs)
        return FakeGitLab(**kwargs)

    import sys
    import types

    monkeypatch.setitem(sys.modules, "gitlab", types.SimpleNamespace(Gitlab=fake_gitlab_factory))

    GitLabClient(AppConfig.from_env({}))._make_client()

    assert created["timeout"] == 5
