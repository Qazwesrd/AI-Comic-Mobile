from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-only-change-me-please-use-32-bytes"
    database_url: str = "sqlite:///./ai_comic_mobile.db"
    access_token_minutes: int = 60 * 24
    trial_hours: int = 48
    web_origin: str = "http://localhost:3000"
    cors_origins: str = ""
    session_cookie_name: str = "ai_comic_session"
    csrf_cookie_name: str = "ai_comic_csrf"
    session_cookie_samesite: str = "lax"
    app_base_url: str = "http://localhost:3000"
    token_pepper: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender_email: str = ""
    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    aliyun_sms_sign_name: str = ""
    aliyun_sms_template_code: str = ""
    aliyun_sms_scheme_name: str = ""
    payment_webhook_secret: str = ""
    payment_checkout_url: str = ""
    admin_bootstrap_emails: str = ""
    rate_limit_auth_per_minute: int = 8
    rate_limit_email_per_hour: int = 5
    max_active_devices: int = 3
    require_email_verification: bool = True
    ai_api_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 120
    ai_config_encryption_key: str = ""
    media_root: str = "./storage/media"
    max_upload_bytes: int = 2147483648
    image_api_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""
    image_timeout_seconds: int = 180
    audio_api_base_url: str = ""
    audio_api_key: str = ""
    audio_model: str = ""
    audio_timeout_seconds: int = 180

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

if settings.app_env.lower() == "production" and settings.app_secret_key == "development-only-change-me":
    raise RuntimeError("APP_SECRET_KEY must be configured in production.")

if settings.session_cookie_samesite.lower() not in {"lax", "strict", "none"}:
    raise RuntimeError("SESSION_COOKIE_SAMESITE must be lax, strict, or none.")

if settings.app_env.lower() == "production" and settings.session_cookie_samesite.lower() == "none":
    # SameSite=None is valid only with Secure cookies.
    pass

if settings.app_env.lower() == "production" and not settings.token_pepper:
    raise RuntimeError("TOKEN_PEPPER must be configured in production.")

if settings.app_env.lower() == "production" and not settings.require_email_verification:
    raise RuntimeError("REQUIRE_EMAIL_VERIFICATION must be enabled in production.")

if settings.app_env.lower() == "production":
    if not settings.app_base_url.startswith("https://") or not settings.web_origin.startswith("https://"):
        raise RuntimeError("APP_BASE_URL and WEB_ORIGIN must use HTTPS in production.")
    if not settings.cors_origins:
        raise RuntimeError("CORS_ORIGINS must be explicitly configured in production.")

if settings.app_env.lower() == "production" and not settings.ai_config_encryption_key:
    raise RuntimeError("AI_CONFIG_ENCRYPTION_KEY must be configured in production when account-level AI credentials are enabled.")
