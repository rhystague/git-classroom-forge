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
            projects=FakeManager([]),
        )
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


def test_gitlab_client_looks_up_users_by_exact_username(monkeypatch):
    client = GitLabClient(AppConfig.from_env({}))
    fake_gitlab = FakeGitLab()
    monkeypatch.setattr(client, "_make_client", lambda: fake_gitlab)

    users = client.lookup_users(("22048668", "22049321"))

    assert users["22048668"].exists is True
    assert users["22048668"].name == "Student One"
    assert users["22049321"].exists is False


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
