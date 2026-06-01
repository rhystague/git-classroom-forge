from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


@dataclass(frozen=True)
class AppConfig:
    gitlab_url: str
    gitlab_token: str
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    data_dir: str = "/workspace/data"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        source = environ if env is None else env
        return cls(
            gitlab_url=source.get("GITLAB_URL", "").strip(),
            gitlab_token=source.get("GITLAB_TOKEN", "").strip(),
            app_env=source.get("APP_ENV", "development").strip() or "development",
            app_host=source.get("APP_HOST", "0.0.0.0").strip() or "0.0.0.0",
            app_port=int(source.get("APP_PORT", "8080")),
            data_dir=source.get("DATA_DIR", "/workspace/data").strip() or "/workspace/data",
        )

    def to_public_dict(self) -> dict[str, str | int]:
        return {
            "gitlab_url": self.gitlab_url,
            "gitlab_token": "[redacted]" if self.gitlab_token else "",
            "app_env": self.app_env,
            "app_host": self.app_host,
            "app_port": self.app_port,
            "data_dir": self.data_dir,
        }

    @property
    def gitlab_configured(self) -> bool:
        return bool(self.gitlab_url and self.gitlab_token)
