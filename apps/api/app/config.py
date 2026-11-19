from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./ai_comic_mobile.db"
    access_token_minutes: int = 60 * 24
    trial_hours: int = 72
    web_origin: str = "http://localhost:3000"
    cors_origins: str = ""
    session_cookie_name: str = "ai_comic_session"
    csrf_cookie_name: str = "ai_comic_csrf"
    session_cookie_samesite: str = "lax"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

if settings.app_env == "production" and settings.app_secret_key == "development-only-change-me":
    raise RuntimeError("APP_SECRET_KEY must be configured in production.")

if settings.session_cookie_samesite.lower() not in {"lax", "strict", "none"}:
    raise RuntimeError("SESSION_COOKIE_SAMESITE must be lax, strict, or none.")

if settings.app_env == "production" and settings.session_cookie_samesite.lower() == "none":
    # SameSite=None is valid only with Secure cookies.
    pass
