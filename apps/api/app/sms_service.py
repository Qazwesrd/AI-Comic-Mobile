from __future__ import annotations

import json

from .config import settings


def _body_map(response) -> dict:
    body = getattr(response, "body", None)
    if body is None:
        body = getattr(response, "Body", None)
    if isinstance(body, dict):
        return body
    converter = getattr(body, "to_map", None)
    if callable(converter):
        return converter()
    return {}


def _value(data: dict, key: str):
    pascal = "".join(part.capitalize() for part in key.split("_"))
    camel = key.split("_")[0] + "".join(part.capitalize() for part in key.split("_")[1:])
    return data.get(key, data.get(camel, data.get(pascal)))


def _client():
    required = (
        settings.aliyun_access_key_id,
        settings.aliyun_access_key_secret,
        settings.aliyun_sms_sign_name,
        settings.aliyun_sms_template_code,
    )
    if not all(required):
        raise RuntimeError("阿里云短信认证服务尚未完成配置。")
    from alibabacloud_dypnsapi20170525.client import Client
    from alibabacloud_tea_openapi import models as open_api_models

    config = open_api_models.Config(
        access_key_id=settings.aliyun_access_key_id,
        access_key_secret=settings.aliyun_access_key_secret,
    )
    config.endpoint = "dypnsapi.aliyuncs.com"
    return Client(config)


def send_phone_verification_code(phone: str) -> None:
    from alibabacloud_dypnsapi20170525 import models as sms_models
    from alibabacloud_tea_util import models as util_models

    client = _client()
    request_args = {
        "phone_number": phone,
        "country_code": "86",
        "sign_name": settings.aliyun_sms_sign_name,
        "template_code": settings.aliyun_sms_template_code,
        "template_param": json.dumps({"code": "##code##", "min": "5"}),
        "code_length": 6,
        "code_type": 1,
        "valid_time": 300,
        "interval": 60,
        "duplicate_policy": 1,
        "return_verify_code": False,
    }
    if settings.aliyun_sms_scheme_name:
        request_args["scheme_name"] = settings.aliyun_sms_scheme_name
    try:
        response = client.send_sms_verify_code_with_options(
            sms_models.SendSmsVerifyCodeRequest(**request_args),
            util_models.RuntimeOptions(),
        )
        data = _body_map(response)
        if _value(data, "success") is not True or _value(data, "code") != "OK":
            raise RuntimeError("阿里云未能受理短信发送请求。")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("阿里云短信发送失败，请检查短信服务配置和号码状态。") from exc


def check_phone_verification_code(phone: str, code: str) -> bool:
    from alibabacloud_dypnsapi20170525 import models as sms_models
    from alibabacloud_tea_util import models as util_models

    client = _client()
    try:
        response = client.check_sms_verify_code_with_options(
            sms_models.CheckSmsVerifyCodeRequest(
                country_code="86",
                phone_number=phone,
                verify_code=code,
                case_auth_policy=0,
                scheme_name=settings.aliyun_sms_scheme_name or None,
            ),
            util_models.RuntimeOptions(),
        )
        data = _body_map(response)
        if _value(data, "success") is not True or _value(data, "code") != "OK":
            return False
        result = _value(data, "model") or {}
        if not isinstance(result, dict):
            converter = getattr(result, "to_map", None)
            result = converter() if callable(converter) else {}
        return _value(result, "verify_result") == "PASS"
    except Exception as exc:
        raise RuntimeError("阿里云短信验证码核验服务暂不可用。") from exc
