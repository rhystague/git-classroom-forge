from app.config import AppConfig


def test_config_loads_defaults_and_gitlab_settings():
    config = AppConfig.from_env(
        {
            "GITLAB_URL": "https://gitlab.example.edu.au",
            "GITLAB_TOKEN": "secret-token",
        }
    )

    assert config.gitlab_url == "https://gitlab.example.edu.au"
    assert config.gitlab_token == "secret-token"
    assert config.app_env == "development"
    assert config.app_host == "0.0.0.0"
    assert config.app_port == 8080
    assert config.data_dir == "/workspace/data"
    assert config.student_email_domain == "student.university.edu.au"


def test_config_allows_student_email_domain_override():
    config = AppConfig.from_env(
        {
            "STUDENT_EMAIL_DOMAIN": "students.example.edu",
        }
    )

    assert config.student_email_domain == "students.example.edu"


def test_config_redacts_token():
    config = AppConfig.from_env(
        {
            "GITLAB_URL": "https://gitlab.example.edu.au",
            "GITLAB_TOKEN": "secret-token",
        }
    )

    public = config.to_public_dict()

    assert public["gitlab_token"] == "[redacted]"
    assert "secret-token" not in repr(public)
