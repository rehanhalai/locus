from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import get_data_dir


class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{get_data_dir() / 'locus.db'}"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
