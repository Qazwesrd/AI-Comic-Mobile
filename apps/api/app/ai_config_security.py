from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from .config import settings


def _fernet() -> Fernet:
    key = settings.ai_config_encryption_key.strip()
    if not key:
        raise HTTPException(status_code=503, detail="服务器尚未设置 AI_CONFIG_ENCRYPTION_KEY，暂时不能保存账号级 API Key")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise HTTPException(status_code=503, detail="AI_CONFIG_ENCRYPTION_KEY 格式无效，请使用 Fernet 生成的密钥")


def encrypt_api_key(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_api_key(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=503, detail="已保存的 AI 密钥无法解密，请检查服务器加密密钥是否与保存时一致")
