from app.gitlab_client import (
    GitLabProjectInvitation,
    GitLabProjectMember,
    GitLabProjectSummary,
    GitLabUserLookup,
)
from app.membership import plan_project_memberships


PROJECT = GitLabProjectSummary(
    id=10,
    name="Team 01",
    path="team-01",
    path_with_namespace="professional-experience/autumn-2026/pa2621/team-01",
    web_url="https://gitlab.example.edu.au/professional-experience/autumn-2026/pa2621/team-01",
)


def lookup(username, *, exists=True, user_id=None, state="active"):
    return GitLabUserLookup(
        username=username,
        exists=exists,
        ambiguous=False,
        id=user_id,
        name=f"Student {username}" if exists else None,
        state=state if exists else None,
    )


def member(username, access_level, *, user_id=None):
    return GitLabProjectMember(
        user_id=user_id or int(username),
        username=username,
        name=f"Student {username}",
        access_level=access_level,
        state="active",
    )


def invitation(email, access_level=30):
    return GitLabProjectInvitation(email=email, access_level=access_level)


def first_action(result):
    return result["actions"][0]


def test_existing_direct_developer_member_is_reused():
    result = plan_project_memberships(
        student_ids=["22048668"],
        project=PROJECT,
        student_lookups={"22048668": lookup("22048668", user_id=100)},
        direct_members=[member("22048668", 30, user_id=100)],
        all_members=[member("22048668", 30, user_id=100)],
        invitations=[],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is True
    assert action["action"] == "reuse"
    assert action["access_source"] == "direct"
    assert action["email"] == "22048668@student.university.edu.au"


def test_existing_inherited_developer_member_is_reused():
    result = plan_project_memberships(
        student_ids=["22048668"],
        project=PROJECT,
        student_lookups={"22048668": lookup("22048668", user_id=100)},
        direct_members=[],
        all_members=[member("22048668", 30, user_id=100)],
        invitations=[],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is True
    assert action["action"] == "reuse"
    assert action["access_source"] == "inherited"


def test_existing_lower_direct_access_is_upgraded_to_developer():
    result = plan_project_memberships(
        student_ids=["22048668"],
        project=PROJECT,
        student_lookups={"22048668": lookup("22048668", user_id=100)},
        direct_members=[member("22048668", 20, user_id=100)],
        all_members=[member("22048668", 20, user_id=100)],
        invitations=[],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is True
    assert action["action"] == "upgrade_to_developer"
    assert action["current_access_level"] == 20


def test_missing_user_without_pending_invite_plans_invitation():
    result = plan_project_memberships(
        student_ids=["22049321"],
        project=PROJECT,
        student_lookups={"22049321": lookup("22049321", exists=False)},
        direct_members=[],
        all_members=[],
        invitations=[],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is True
    assert action["action"] == "create_invite"
    assert action["email"] == "22049321@student.university.edu.au"


def test_missing_user_with_pending_invite_plans_refresh():
    result = plan_project_memberships(
        student_ids=["22049321"],
        project=PROJECT,
        student_lookups={"22049321": lookup("22049321", exists=False)},
        direct_members=[],
        all_members=[],
        invitations=[invitation("22049321@student.university.edu.au", access_level=20)],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is True
    assert action["action"] == "refresh_invite"
    assert action["current_access_level"] == 20


def test_inactive_existing_user_is_an_error():
    result = plan_project_memberships(
        student_ids=["22048668"],
        project=PROJECT,
        student_lookups={"22048668": lookup("22048668", user_id=100, state="blocked")},
        direct_members=[],
        all_members=[],
        invitations=[],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is False
    assert action["action"] == "error"
    assert "blocked" in action["reason"]
    assert result["errors"] == [
        "GitLab user 22048668 is blocked and cannot be provisioned automatically."
    ]


def test_existing_user_with_pending_invite_reports_stale_invite():
    result = plan_project_memberships(
        student_ids=["22048668"],
        project=PROJECT,
        student_lookups={"22048668": lookup("22048668", user_id=100)},
        direct_members=[],
        all_members=[],
        invitations=[invitation("22048668@student.university.edu.au")],
        student_email_domain="student.university.edu.au",
    )

    action = first_action(result)
    assert result["valid"] is True
    assert action["action"] == "add_member"
    assert action["stale_invite"] is True
    assert result["warnings"] == [
        "Pending invite for 22048668@student.university.edu.au is stale because user 22048668 now exists."
    ]


def test_empty_missing_project_is_skipped():
    result = plan_project_memberships(
        student_ids=[],
        project=None,
        student_lookups={},
        direct_members=[],
        all_members=[],
        invitations=[],
        student_email_domain="student.university.edu.au",
    )

    assert result["valid"] is True
    assert result["actions"] == [
        {
            "student_id": None,
            "email": None,
            "user_exists": False,
            "user_state": None,
            "access_source": None,
            "current_access_level": None,
            "target_access_level": 30,
            "action": "skip_empty_project",
            "action_label": "Skip empty project",
            "reason": "Project row has no student IDs; missing project will not be created.",
            "stale_invite": False,
        }
    ]
