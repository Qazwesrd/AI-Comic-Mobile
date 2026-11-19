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


class EmailCodeIn(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

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


class PhoneCredentialsIn(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    password: str = Field(min_length=10, max_length=128)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return value.strip()


class PhoneCodeIn(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return value.strip()


class PhoneRegisterVerifyIn(PhoneCodeIn):
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d{4,8}$")
    password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str | None = None
    phone: str | None = None
    model_config = ConfigDict(from_attributes=True)


class AuthOut(BaseModel):
    user: UserOut
    csrf_token: str


class CsrfOut(BaseModel):
    csrf_token: str


class LicenseOut(BaseModel):
    status: str
    permanent: bool
    trial_started_at: str | None
    trial_expires_at: str | None
    remaining_seconds: int
    message: str
