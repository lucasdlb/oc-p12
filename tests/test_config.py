from news_ingestion.config import Settings


def test_settings_load_env_and_toml_with_env_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    toml_file = tmp_path / "config.toml"
    raw_data_dir = tmp_path / "raw"

    env_file.write_text(
        "\n".join(
            [
                "NEWS_DATA_API_KEY=pub_test_key",
                "HF_TOKEN=hf_test_token",
                f"RAW_DATA_DIR={raw_data_dir}",
                "NEWSDATA__QUERY=env query",
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
validate_image_urls = true

[gdelt]
enabled = false
query = "gdelt query"
language = "French"
max_records = 10
only_with_images = false
validate_image_urls = true
max_retries = 3
retry_backoff_seconds = [5, 10, 15]

[climate_fever]
dataset_name = "custom/climate_fever"
split = "train"
max_records = 25

[dataforgood]
dataset_name = "custom/dataforgood"
splits = ["test"]
max_records = 30

[fakeddit]
dataset_dir = "external/Fakeddit"
files = ["sample.tsv"]
max_records = 40
only_multimodal = false
validate_image_urls = true

[rss]
feeds = ["https://example.com/feed.xml"]
max_records_per_feed = 12
only_with_images = true
validate_image_urls = true
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

    assert settings.news_data_api_key is not None
    assert settings.news_data_api_key.get_secret_value() == "pub_test_key"
    assert settings.hf_token is not None
    assert settings.hf_token.get_secret_value() == "hf_test_token"
    assert settings.raw_data_dir == raw_data_dir
    assert settings.newsdata.query == "env query"
    assert settings.newsdata.language == "fr"
    assert settings.newsdata.category == "environment"
    assert settings.newsdata.country == "ca"
    assert settings.newsdata.max_pages == 2
    assert settings.newsdata.only_with_images is False
    assert settings.newsdata.validate_image_urls is True
    assert settings.gdelt.query == "gdelt query"
    assert settings.gdelt.enabled is False
    assert settings.gdelt.language == "French"
    assert settings.gdelt.max_records == 10
    assert settings.gdelt.only_with_images is False
    assert settings.gdelt.validate_image_urls is True
    assert settings.gdelt.max_retries == 3
    assert settings.gdelt.retry_backoff_seconds == [5, 10, 15]
    assert settings.climate_fever.dataset_name == "custom/climate_fever"
    assert settings.climate_fever.split == "train"
    assert settings.climate_fever.max_records == 25
    assert settings.dataforgood.dataset_name == "custom/dataforgood"
    assert settings.dataforgood.splits == ["test"]
    assert settings.dataforgood.max_records == 30
    assert settings.fakeddit.dataset_dir.name == "Fakeddit"
    assert settings.fakeddit.files == ["sample.tsv"]
    assert settings.fakeddit.max_records == 40
    assert settings.fakeddit.only_multimodal is False
    assert settings.fakeddit.validate_image_urls is True
    assert settings.rss.feeds == ["https://example.com/feed.xml"]
    assert settings.rss.max_records_per_feed == 12
    assert settings.rss.only_with_images is True
    assert settings.rss.validate_image_urls is True
