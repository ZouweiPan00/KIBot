from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_base_url: str = "https://example.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    session_storage_dir: str = "data/sessions"
    app_host: str = "0.0.0.0"
    app_port: int = 7860

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
