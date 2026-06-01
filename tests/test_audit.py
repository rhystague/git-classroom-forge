import json

from app.audit import write_audit_event


def test_audit_event_redacts_tokens_and_authorization_headers(tmp_path):
    path = write_audit_event(
        str(tmp_path),
        "dry-run",
        {
            "gitlab_token": "secret-token",
            "nested": {
                "Authorization": "Bearer secret-token",
                "student_id": "22048668",
            },
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))["payload"]

    assert payload["gitlab_token"] == "[redacted]"
    assert payload["nested"]["Authorization"] == "[redacted]"
    assert payload["nested"]["student_id"] == "22048668"
    assert "secret-token" not in path.read_text(encoding="utf-8")
