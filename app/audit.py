from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = {"gitlab_token", "token", "private_token", "authorization"}


def write_audit_event(data_dir: str, event_type: str, payload: dict[str, Any]) -> Path:
    logs_dir = Path(data_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = logs_dir / f"{timestamp}-{event_type}.json"
    path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "event_type": event_type,
                "payload": _redact(payload),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
