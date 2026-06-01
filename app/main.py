from __future__ import annotations

from pathlib import Path

from flask import Flask

from app.config import AppConfig
from app.routes import bp


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    app = Flask(__name__)
    config = AppConfig.from_env()
    app.config.from_mapping(
        APP_CONFIG=config,
        DATA_DIR=config.data_dir,
    )

    if test_config:
        app.config.from_mapping(test_config)

    _ensure_data_dirs(app.config["APP_CONFIG"].data_dir)
    app.register_blueprint(bp)
    return app


def _ensure_data_dirs(data_dir: str) -> None:
    root = Path(data_dir)
    for name in ("uploads", "reports", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    runtime_config = AppConfig.from_env()
    create_app().run(host=runtime_config.app_host, port=runtime_config.app_port)
