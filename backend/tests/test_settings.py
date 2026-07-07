from app.core.config import Settings


def test_settings_accept_typed_environment_overrides() -> None:
    settings = Settings(
        env="dev",
        log_level="DEBUG",
        cors_origins=["http://localhost:8081"],
        database_port=6543,
        readiness_database_required=True,
    )

    assert settings.env == "dev"
    assert settings.log_level == "DEBUG"
    assert settings.cors_origins == ["http://localhost:8081"]
    assert settings.database_port == 6543
    assert settings.database_configured is True
    assert settings.readiness_database_required is True


def test_hinterland_env_prefix_wins_over_dragonfly_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DRAGONFLY_APP_NAME", "Dragonfly API")
    monkeypatch.setenv("HINTERLAND_APP_NAME", "The Hinterland Guide API")

    settings = Settings()

    assert settings.app_name == "The Hinterland Guide API"


def test_dragonfly_env_prefix_remains_fallback(monkeypatch) -> None:
    monkeypatch.delenv("HINTERLAND_APP_NAME", raising=False)
    monkeypatch.setenv("DRAGONFLY_APP_NAME", "Legacy Dragonfly API")

    settings = Settings()

    assert settings.app_name == "Legacy Dragonfly API"
