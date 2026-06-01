from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig


@dataclass(frozen=True)
class GitLabConnectionStatus:
    configured: bool
    authenticated: bool
    message: str


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

    def _make_client(self):
        import gitlab

        return gitlab.Gitlab(
            url=self._config.gitlab_url,
            private_token=self._config.gitlab_token,
            user_agent="class-git-forge/0.1",
        )
