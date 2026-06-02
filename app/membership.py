from __future__ import annotations

from app.gitlab_client import (
    GitLabProjectInvitation,
    GitLabProjectMember,
    GitLabProjectSummary,
    GitLabUserLookup,
)


DEVELOPER_ACCESS_LEVEL = 30
ACTIVE_USER_STATES = {None, "", "active"}


def plan_project_memberships(
    *,
    student_ids: list[str],
    project: GitLabProjectSummary | None,
    student_lookups: dict[str, GitLabUserLookup],
    direct_members: list[GitLabProjectMember],
    all_members: list[GitLabProjectMember],
    invitations: list[GitLabProjectInvitation],
    student_email_domain: str,
) -> dict[str, object]:
    if not student_ids:
        reason = (
            "Existing project has no student IDs; no membership actions planned."
            if project
            else "Project row has no student IDs; missing project will not be created."
        )
        action = _action(
            student_id=None,
            email=None,
            user_exists=False,
            user_state=None,
            access_source=None,
            current_access_level=None,
            action="skip_empty_project",
            reason=reason,
            stale_invite=False,
        )
        return {"valid": True, "actions": [action], "errors": [], "warnings": []}

    actions: list[dict[str, object]] = []
    errors: list[str] = []
    warnings: list[str] = []
    direct_by_user_id = _members_by_user_id(direct_members)
    all_by_user_id = _members_by_user_id(all_members)
    invitations_by_email = {
        invitation.email.lower(): invitation
        for invitation in invitations
        if invitation.email
    }

    for student_id in student_ids:
        email = f"{student_id}@{student_email_domain}"
        if not student_id.isdigit():
            message = f"Student ID {student_id} must contain digits only before membership planning."
            errors.append(message)
            actions.append(
                _action(
                    student_id=student_id,
                    email=None,
                    user_exists=False,
                    user_state=None,
                    access_source=None,
                    current_access_level=None,
                    action="error",
                    reason=message,
                    stale_invite=False,
                )
            )
            continue

        lookup = student_lookups.get(
            student_id,
            GitLabUserLookup(
                username=student_id,
                exists=False,
                ambiguous=False,
                id=None,
                name=None,
            ),
        )
        invitation = invitations_by_email.get(email.lower())

        if lookup.ambiguous:
            message = f"GitLab user lookup is ambiguous for student ID {student_id}."
            errors.append(message)
            actions.append(
                _action(
                    student_id=student_id,
                    email=email,
                    user_exists=False,
                    user_state=None,
                    access_source=None,
                    current_access_level=None,
                    action="error",
                    reason=message,
                    stale_invite=False,
                )
            )
            continue

        if lookup.exists:
            action, warning, error = _existing_user_action(
                student_id=student_id,
                email=email,
                lookup=lookup,
                direct_by_user_id=direct_by_user_id,
                all_by_user_id=all_by_user_id,
                invitation=invitation,
                project_exists=project is not None,
            )
        else:
            action = _missing_user_action(
                student_id=student_id,
                email=email,
                invitation=invitation,
                project_exists=project is not None,
            )
            warning = None
            error = None

        actions.append(action)
        if warning:
            warnings.append(warning)
        if error:
            errors.append(error)

    return {
        "valid": not errors,
        "actions": actions,
        "errors": errors,
        "warnings": warnings,
    }


def _existing_user_action(
    *,
    student_id: str,
    email: str,
    lookup: GitLabUserLookup,
    direct_by_user_id: dict[int, GitLabProjectMember],
    all_by_user_id: dict[int, GitLabProjectMember],
    invitation: GitLabProjectInvitation | None,
    project_exists: bool,
) -> tuple[dict[str, object], str | None, str | None]:
    if lookup.state not in ACTIVE_USER_STATES:
        message = (
            f"GitLab user {student_id} is {lookup.state} and cannot be provisioned automatically."
        )
        return (
            _action(
                student_id=student_id,
                email=email,
                user_exists=True,
                user_state=lookup.state,
                access_source=None,
                current_access_level=None,
                action="error",
                reason=message,
                stale_invite=False,
            ),
            None,
            message,
        )

    direct_member = direct_by_user_id.get(lookup.id) if lookup.id is not None else None
    all_member = all_by_user_id.get(lookup.id) if lookup.id is not None else None
    member = direct_member or all_member
    access_source = "direct" if direct_member else "inherited" if all_member else None
    current_access_level = member.access_level if member else None
    stale_invite = invitation is not None
    warning = (
        f"Pending invite for {email} is stale because user {student_id} now exists."
        if stale_invite
        else None
    )

    if current_access_level is not None and current_access_level >= DEVELOPER_ACCESS_LEVEL:
        return (
            _action(
                student_id=student_id,
                email=email,
                user_exists=True,
                user_state=lookup.state,
                access_source=access_source,
                current_access_level=current_access_level,
                action="reuse",
                reason=f"Student already has {access_source} Developer-or-higher access.",
                stale_invite=stale_invite,
            ),
            warning,
            None,
        )

    if current_access_level is not None and access_source == "direct":
        return (
            _action(
                student_id=student_id,
                email=email,
                user_exists=True,
                user_state=lookup.state,
                access_source="direct",
                current_access_level=current_access_level,
                action="upgrade_to_developer",
                reason="Student has direct access below Developer and will be upgraded.",
                stale_invite=stale_invite,
            ),
            warning,
            None,
        )

    action_name = "add_member" if project_exists else "add_member_after_project_create"
    reason = (
        "Student exists and will be added as a direct project member."
        if project_exists
        else "Student exists and will be added after the project is created."
    )
    return (
        _action(
            student_id=student_id,
            email=email,
            user_exists=True,
            user_state=lookup.state,
            access_source=access_source,
            current_access_level=current_access_level,
            action=action_name,
            reason=reason,
            stale_invite=stale_invite,
        ),
        warning,
        None,
    )


def _missing_user_action(
    *,
    student_id: str,
    email: str,
    invitation: GitLabProjectInvitation | None,
    project_exists: bool,
) -> dict[str, object]:
    current_access_level = invitation.access_level if invitation else None
    if invitation:
        action_name = "refresh_invite" if project_exists else "refresh_invite_after_project_create"
        reason = (
            "Pending invitation exists and will be refreshed to Developer access."
            if project_exists
            else "Pending invitation will be refreshed after the project is created."
        )
    else:
        action_name = "create_invite" if project_exists else "create_invite_after_project_create"
        reason = (
            "GitLab user does not exist; derived email will be invited."
            if project_exists
            else "GitLab user does not exist; derived email will be invited after the project is created."
        )

    return _action(
        student_id=student_id,
        email=email,
        user_exists=False,
        user_state=None,
        access_source=None,
        current_access_level=current_access_level,
        action=action_name,
        reason=reason,
        stale_invite=False,
    )


def _members_by_user_id(members: list[GitLabProjectMember]) -> dict[int, GitLabProjectMember]:
    return {member.user_id: member for member in members}


def _action(
    *,
    student_id: str | None,
    email: str | None,
    user_exists: bool,
    user_state: str | None,
    access_source: str | None,
    current_access_level: int | None,
    action: str,
    reason: str,
    stale_invite: bool,
) -> dict[str, object]:
    return {
        "student_id": student_id,
        "email": email,
        "user_exists": user_exists,
        "user_state": user_state,
        "access_source": access_source,
        "current_access_level": current_access_level,
        "target_access_level": DEVELOPER_ACCESS_LEVEL,
        "action": action,
        "action_label": _action_label(action),
        "reason": reason,
        "stale_invite": stale_invite,
    }


def _action_label(action: str) -> str:
    labels = {
        "reuse": "Reuse existing access",
        "upgrade_to_developer": "Upgrade to Developer",
        "add_member": "Add member",
        "add_member_after_project_create": "Add member after project create",
        "create_invite": "Create invite",
        "create_invite_after_project_create": "Invite after project create",
        "refresh_invite": "Refresh invite",
        "refresh_invite_after_project_create": "Refresh invite after project create",
        "skip_empty_project": "Skip empty project",
        "error": "Error",
    }
    return labels.get(action, action.replace("_", " ").capitalize())
