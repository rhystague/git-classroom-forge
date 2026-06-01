from app.main import create_app
from app.config import AppConfig


def test_health_route_returns_json_status(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_CONFIG": AppConfig.from_env({"DATA_DIR": str(tmp_path)}),
        }
    )

    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "class-git-forge"}
