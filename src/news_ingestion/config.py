from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    msg = "Could not find project root (no pyproject.toml found)."
    raise RuntimeError(msg)


PROJECT_ROOT = _find_project_root()

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


class Settings(BaseSettings):
    """Application settings loaded from environment, `.env`, and `config.toml`."""

    news_data_api_key: SecretStr = Field(alias="NEWS_DATA_API_KEY")
    news_data_base_url: str = Field(
        default="https://newsdata.io/api/1/news",
        validation_alias=AliasChoices("NEWS_DATA_BASE_URL", "base_url"),
    )
    news_data_query: str = Field(
        default="climate change",
        validation_alias=AliasChoices("NEWS_DATA_QUERY", "query"),
    )
    news_data_language: str = Field(
        default="en",
        validation_alias=AliasChoices("NEWS_DATA_LANGUAGE", "language"),
    )
    news_data_category: NewsCategory = Field(
        default="environment",
        validation_alias=AliasChoices("NEWS_DATA_CATEGORY", "category"),
    )
    news_data_country: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NEWS_DATA_COUNTRY", "country"),
    )
    news_data_max_pages: int = Field(
        default=1,
        ge=1,
        le=10,
        validation_alias=AliasChoices("NEWS_DATA_MAX_PAGES", "max_pages"),
    )
    news_data_only_with_images: bool = Field(
        default=True,
        validation_alias=AliasChoices("NEWS_DATA_ONLY_WITH_IMAGES", "only_with_images"),
    )
    raw_data_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "raw",
        alias="RAW_DATA_DIR",
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
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
            TomlConfigSettingsSource(settings_cls, toml_table_header=("newsdata",)),
            init_settings,
            file_secret_settings,
        )

    @field_validator("news_data_api_key")
    @classmethod
    def validate_news_data_api_key(cls, value: SecretStr) -> SecretStr:
        api_key = value.get_secret_value().strip()
        if not api_key:
            msg = "NEWS_DATA_API_KEY must not be empty."
            raise ValueError(msg)
        if not api_key.startswith("pub_"):
            msg = "NEWS_DATA_API_KEY should look like a NewsData.io public key and start with 'pub_'."
            raise ValueError(msg)
        return value

    @field_validator("news_data_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        language = value.strip().lower()
        if len(language) != 2 or not language.isalpha():
            msg = "NEWS_DATA_LANGUAGE must be a two-letter language code, for example 'en' or 'fr'."
            raise ValueError(msg)
        return language

    @field_validator("news_data_query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            msg = "NEWS_DATA_QUERY must not be empty."
            raise ValueError(msg)
        return query

    @field_validator("news_data_base_url")
    @classmethod
    def validate_news_data_base_url(cls, value: str) -> str:
        base_url = value.strip()
        if not base_url.startswith("https://"):
            msg = "NEWS_DATA_BASE_URL must use HTTPS."
            raise ValueError(msg)
        return base_url

    @field_validator("raw_data_dir")
    @classmethod
    def resolve_raw_data_dir(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return PROJECT_ROOT / value
