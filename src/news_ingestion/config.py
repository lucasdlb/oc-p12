import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


def get_project_root() -> Path:
    env_root = os.getenv("PROJECT_ROOT")
    if env_root:
        return Path(env_root).resolve()

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent

    raise RuntimeError(
        "Could not determine PROJECT_ROOT.\n"
        "Set the PROJECT_ROOT environment variable explicitly."
    )


PROJECT_ROOT = get_project_root()


def resolve_project_path(value: Path) -> Path:
    path = value.expanduser()
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


NewsCategory = Literal[
    "business",
    "crime",
    "domestic",
    "education",
    "entertainment",
    "environment",
    "food",
    "health",
    "lifestyle",
    "politics",
    "science",
    "sports",
    "technology",
    "top",
    "tourism",
    "world",
]


class NewsDataSettings(BaseModel):
    base_url: str = "https://newsdata.io/api/1/news"
    query: str = "climate change"
    language: str = "en"
    category: NewsCategory = "environment"
    country: str | None = None
    max_pages: int = Field(default=1, ge=1, le=10)
    only_with_images: bool = True
    validate_image_urls: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        base_url = value.strip()
        if not base_url.startswith("https://"):
            msg = "newsdata.base_url must use HTTPS."
            raise ValueError(msg)
        return base_url

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        language = value.strip().lower()
        if len(language) != 2 or not language.isalpha():
            msg = "newsdata.language must be a two-letter language code, for example 'en' or 'fr'."
            raise ValueError(msg)
        return language

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            msg = "newsdata.query must not be empty."
            raise ValueError(msg)
        return query

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        country = value.strip().lower()
        return country or None


class GdeltSettings(BaseModel):
    enabled: bool = True
    base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    query: str = "climate change"
    mode: str = "artlist"
    response_format: str = "json"
    max_records: int = Field(default=250, ge=1, le=250)
    sort: str = "datedesc"
    language: str | None = "English"
    only_with_images: bool = True
    validate_image_urls: bool = False
    max_retries: int = Field(default=5, ge=0)
    retry_backoff_seconds: list[int] = Field(
        default_factory=lambda: [5, 10, 15, 20, 25]
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        base_url = value.strip()
        if not base_url.startswith("https://"):
            msg = "gdelt.base_url must use HTTPS."
            raise ValueError(msg)
        return base_url

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            msg = "gdelt.query must not be empty."
            raise ValueError(msg)
        return query

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        language = value.strip()
        return language or None

    @field_validator("retry_backoff_seconds")
    @classmethod
    def validate_retry_backoff_seconds(cls, value: list[int]) -> list[int]:
        if any(delay < 0 for delay in value):
            msg = "gdelt.retry_backoff_seconds must contain positive or zero delays."
            raise ValueError(msg)
        return value


class ClimateFeverSettings(BaseModel):
    dataset_name: str = "tdiggelm/climate_fever"
    split: str = "test"
    max_records: int = Field(default=500, ge=1)

    @field_validator("dataset_name", "split")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            msg = "climate_fever dataset_name and split must not be empty."
            raise ValueError(msg)
        return cleaned_value


class DataForGoodSettings(BaseModel):
    dataset_name: str = "DataForGood/climate-misinformation-RCoT"
    splits: list[str] = Field(default_factory=lambda: ["train", "test"])
    max_records: int = Field(default=500, ge=1)

    @field_validator("dataset_name")
    @classmethod
    def validate_dataset_name(cls, value: str) -> str:
        dataset_name = value.strip()
        if not dataset_name:
            msg = "dataforgood.dataset_name must not be empty."
            raise ValueError(msg)
        return dataset_name

    @field_validator("splits")
    @classmethod
    def validate_splits(cls, value: list[str]) -> list[str]:
        splits = [split.strip() for split in value if split.strip()]
        if not splits:
            msg = "dataforgood.splits must contain at least one split."
            raise ValueError(msg)
        return splits


class FakedditSettings(BaseModel):
    dataset_dir: Path = resolve_project_path(Path("external/Fakeddit"))
    files: list[str] = Field(
        default_factory=lambda: [
            "multimodal_train.tsv",
            "multimodal_validate.tsv",
            "multimodal_test.tsv",
        ]
    )
    max_records: int = Field(default=500, ge=1)
    only_multimodal: bool = True
    validate_image_urls: bool = False

    @field_validator("dataset_dir")
    @classmethod
    def resolve_dataset_dir(cls, value: Path) -> Path:
        return resolve_project_path(value)

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: list[str]) -> list[str]:
        files = [file_name.strip() for file_name in value if file_name.strip()]
        if not files:
            msg = "fakeddit.files must contain at least one TSV file."
            raise ValueError(msg)
        return files


class RssSettings(BaseModel):
    feeds: list[str] = Field(
        default_factory=lambda: [
            "https://www.theguardian.com/environment/climate-crisis/rss",
            "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
            "https://www.france24.com/en/tag/climate-change/rss",
            "https://www.politifact.com/rss/factchecks/",
        ]
    )
    max_records_per_feed: int = Field(default=50, ge=1)
    only_with_images: bool = False
    validate_image_urls: bool = False

    @field_validator("feeds")
    @classmethod
    def validate_feeds(cls, value: list[str]) -> list[str]:
        feeds = [feed.strip() for feed in value if feed.strip()]
        if not feeds:
            msg = "rss.feeds must contain at least one feed URL."
            raise ValueError(msg)
        invalid_feeds = [feed for feed in feeds if not feed.startswith("https://")]
        if invalid_feeds:
            msg = "rss.feeds must contain HTTPS URLs only."
            raise ValueError(msg)
        return feeds


class Settings(BaseSettings):
    """Application settings loaded from environment, `.env`, and `config.toml`."""

    project_root: Path = PROJECT_ROOT
    news_data_api_key: SecretStr | None = Field(default=None, alias="NEWS_DATA_API_KEY")
    hf_token: SecretStr | None = Field(default=None, alias="HF_TOKEN")
    raw_data_dir: Path = Field(
        default=resolve_project_path(Path("data/raw")),
        alias="RAW_DATA_DIR",
    )
    processed_data_dir: Path = Field(
        default=resolve_project_path(Path("data/processed")),
        alias="PROCESSED_DATA_DIR",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    newsdata: NewsDataSettings = Field(default_factory=NewsDataSettings)
    gdelt: GdeltSettings = Field(default_factory=GdeltSettings)
    climate_fever: ClimateFeverSettings = Field(default_factory=ClimateFeverSettings)
    dataforgood: DataForGoodSettings = Field(default_factory=DataForGoodSettings)
    fakeddit: FakedditSettings = Field(default_factory=FakedditSettings)
    rss: RssSettings = Field(default_factory=RssSettings)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        toml_file=PROJECT_ROOT / "config.toml",
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            init_settings,
            file_secret_settings,
        )

    @field_validator("news_data_api_key")
    @classmethod
    def validate_news_data_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        api_key = value.get_secret_value().strip()
        if not api_key:
            msg = "NEWS_DATA_API_KEY must not be empty."
            raise ValueError(msg)
        if not api_key.startswith("pub_"):
            msg = "NEWS_DATA_API_KEY should look like a NewsData.io public key and start with 'pub_'."
            raise ValueError(msg)
        return value

    @field_validator("hf_token")
    @classmethod
    def validate_hf_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        token = value.get_secret_value().strip()
        if not token:
            msg = "HF_TOKEN must not be empty when set."
            raise ValueError(msg)
        return value

    @field_validator("raw_data_dir")
    @classmethod
    def resolve_raw_data_dir(cls, value: Path) -> Path:
        return resolve_project_path(value)

    @field_validator("processed_data_dir")
    @classmethod
    def resolve_processed_data_dir(cls, value: Path) -> Path:
        return resolve_project_path(value)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        log_level = value.strip().upper()
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if log_level not in valid_levels:
            msg = "LOG_LEVEL must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG, or NOTSET."
            raise ValueError(msg)
        return log_level


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings instance for the current process."""
    return Settings()
