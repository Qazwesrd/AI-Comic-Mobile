from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./ai_comic_mobile.db"
    access_token_minutes: int = 60 * 24
    trial_hours: int = 72
    web_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

if settings.app_env == "production" and settings.app_secret_key == "development-only-change-me":
    raise RuntimeError("APP_SECRET_KEY must be configured in production.")
