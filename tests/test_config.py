from news_ingestion.config import Settings


def test_settings_load_env_and_toml_with_env_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    toml_file = tmp_path / "config.toml"
    raw_data_dir = tmp_path / "raw"

    env_file.write_text(
        "\n".join(
            [
                "NEWS_DATA_API_KEY=pub_test_key",
                f"RAW_DATA_DIR={raw_data_dir}",
                "NEWS_DATA_QUERY=env query",
            ]
        ),
        encoding="utf-8",
    )
    toml_file.write_text(
        """
[newsdata]
query = "toml query"
language = "fr"
category = "environment"
country = "ca"
max_pages = 2
only_with_images = false
""".strip(),
        encoding="utf-8",
    )

    old_model_config = Settings.model_config.copy()
    monkeypatch.setattr(
        Settings,
        "model_config",
        {**Settings.model_config, "env_file": env_file, "toml_file": toml_file},
    )

    try:
        settings = Settings()
    finally:
        monkeypatch.setattr(Settings, "model_config", old_model_config)

    assert settings.news_data_api_key.get_secret_value() == "pub_test_key"
    assert settings.raw_data_dir == raw_data_dir
    assert settings.news_data_query == "env query"
    assert settings.news_data_language == "fr"
    assert settings.news_data_category == "environment"
    assert settings.news_data_country == "ca"
    assert settings.news_data_max_pages == 2
    assert settings.news_data_only_with_images is False
