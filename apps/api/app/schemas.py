from pydantic import BaseModel, ConfigDict, Field, field_validator


class CredentialsIn(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("请输入有效的邮箱地址")
        return normalized


class DeviceActivationIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)
    platform: str = Field(default="unknown", max_length=24)


class UserOut(BaseModel):
    id: int
    email: str
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LicenseOut(BaseModel):
    status: str
    permanent: bool
    trial_started_at: str | None
    trial_expires_at: str | None
    remaining_seconds: int
    message: str
