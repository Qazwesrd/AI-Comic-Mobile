from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import (
    Chapter, CreativeArtifact, DeviceActivation, License, MediaAsset, Notice, OneTimeToken, Order, PaymentEvent,
    Product, Project, PublishJob, Release, User, UserSession, Novel, StoryEntity, utc_now,
)
from ..security import hash_password
from ..ai_service import chat_json
from ..security_services import (
    audit, consume_one_time_token, create_one_time_token, enforce_rate_limit,
    request_fingerprint, send_account_email,
)

router = APIRouter(prefix="/api/v1", tags=["platform"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_active_license(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if settings.require_email_verification and not (user.email_verified or user.phone_verified):
        raise HTTPException(status_code=403, detail="请先完成手机号或邮箱验证")
    record = db.scalar(select(License).where(License.user_id == user.id))
    if record is None:
        raise HTTPException(status_code=402, detail="请先激活设备开始48小时试用")
    if record.permanent:
        return user
    if not record.trial_started_at:
        raise HTTPException(status_code=402, detail="请先激活设备开始48小时试用")
    started = record.trial_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= started + timedelta(hours=48):
        raise HTTPException(status_code=402, detail="免费试用已结束，请购买永久授权")
    return user


def _safe_dt(value):
    return value.isoformat() if value else None


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class EmailIn(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class PasswordResetIn(TokenIn):
    new_password: str = Field(min_length=10, max_length=128)


class OrderCreateIn(BaseModel):
    product_code: str = Field(min_length=2, max_length=48)


class ManualPaymentConfirmIn(BaseModel):
    transaction_id: str = Field(min_length=4, max_length=128)
    note: str = Field(default="", max_length=500)


class ProductIn(BaseModel):
    code: str = Field(min_length=2, max_length=48)
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    amount_minor: int = Field(gt=0, le=100000000)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    grants_permanent_license: bool = True


class NoticeIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=1, max_length=20000)
    published: bool = False


class ReleaseIn(BaseModel):
    platform: str = Field(pattern="^(android|ios|pwa)$")
    version: str = Field(min_length=1, max_length=32)
    download_url: str = Field(min_length=8, max_length=2048)
    notes: str = Field(default="", max_length=10000)
    minimum_supported_version: str = "0.0.0"
    published: bool = False


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=4000)


class NovelIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    text: str = Field(min_length=1, max_length=5_000_000)


class ArtifactRequest(BaseModel):
    chapter_no: int = Field(ge=1)
    instructions: str = Field(default="", max_length=4000)


class EntityReviewIn(BaseModel):
    approved: bool | None = None
    canonical_name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)


class PublishIn(BaseModel):
    platform: str = Field(pattern="^(douyin|hongguo|kuaishou)$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    media_url: str = Field(min_length=8, max_length=2048)


@router.post("/auth/email/verify/request")
def request_email_verification(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    enforce_rate_limit(db, f"verify-email:{request_fingerprint(request)}", settings.rate_limit_email_per_hour, 3600)
    if user.email_verified:
        return {"message": "邮箱已经验证"}
    raw = create_one_time_token(db, user, "verify_email", 30)
    sent = send_account_email(
        user.email, "AI 漫剧手机版邮箱验证",
        f"请在30分钟内打开以下链接完成邮箱验证：{settings.app_base_url}/verify-email?token={raw}",
    )
    if not sent and settings.app_env == "production":
        raise HTTPException(status_code=503, detail="邮件服务尚未配置，请联系管理员")
    return {"message": "验证邮件已发送" if sent else "邮件服务未配置；开发环境未发送邮件"}


@router.post("/auth/email/verify/confirm")
def confirm_email(payload: TokenIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(db, f"email-confirm:{request_fingerprint(request)}", settings.rate_limit_auth_per_minute, 60)
    user = consume_one_time_token(db, payload.token, "verify_email")
    if user is None:
        raise HTTPException(status_code=400, detail="验证链接无效或已过期")
    user.email_verified = True
    db.commit()
    audit(db, "email_verified", "user", str(user.id), user.id)
    return {"message": "邮箱验证成功"}


@router.post("/auth/password/forgot")
def forgot_password(payload: EmailIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(db, f"password-forgot:{request_fingerprint(request)}", settings.rate_limit_email_per_hour, 3600)
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        raw = create_one_time_token(db, user, "password_reset", 20)
        sent = send_account_email(
            user.email, "AI 漫剧手机版密码重置",
            f"请在20分钟内打开以下链接重置密码：{settings.app_base_url}/reset-password?token={raw}",
        )
        if not sent and settings.app_env == "production":
            raise HTTPException(status_code=503, detail="邮件服务暂不可用")
    return {"message": "如果该邮箱已注册，系统将发送密码重置邮件"}


@router.post("/auth/password/reset")
def reset_password(payload: PasswordResetIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(db, f"password-reset:{request_fingerprint(request)}", settings.rate_limit_auth_per_minute, 60)
    user = consume_one_time_token(db, payload.token, "password_reset")
    if user is None:
        raise HTTPException(status_code=400, detail="重置链接无效或已过期")
    user.password_hash = hash_password(payload.new_password)
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).update(
        {UserSession.revoked_at: utc_now()}, synchronize_session=False
    )
    db.commit()
    audit(db, "password_reset", "user", str(user.id), user.id)
    return {"message": "密码已重置，请使用新密码登录"}


@router.get("/store/products")
def list_products(db: Session = Depends(get_db)):
    rows = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.amount_minor)).all()
    return [{"code": p.code, "name": p.name, "description": p.description,
             "amount_minor": p.amount_minor, "currency": p.currency} for p in rows]


@router.post("/orders")
def create_order(
    payload: OrderCreateIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    enforce_rate_limit(db, f"create-order:{request_fingerprint(request)}", 10, 3600)
    if settings.require_email_verification and not (user.email_verified or user.phone_verified):
        raise HTTPException(status_code=403, detail="请先完成邮箱验证")
    code = payload.product_code
    product = db.scalar(select(Product).where(Product.code == code, Product.active.is_(True)))
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在或暂未开放购买")
    order = Order(
        order_no=f"ACM-{uuid4().hex[:20].upper()}", user_id=user.id, product_id=product.id,
        amount_minor=product.amount_minor, currency=product.currency, status="pending",
        provider="unconfigured",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    audit(db, "order_created", "order", order.order_no, user.id)
    return {
        "order_no": order.order_no, "status": order.status,
        "amount_minor": order.amount_minor, "currency": order.currency,
        "checkout_url": None,
        "payment_configured": False,
        "message": "尚未接入具体支付服务商；当前只创建待支付订单，不能解锁永久授权"
    }


@router.get("/orders")
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Order).where(Order.user_id == user.id).order_by(desc(Order.created_at)).limit(100)).all()
    return [{"order_no": o.order_no, "status": o.status, "amount_minor": o.amount_minor,
             "currency": o.currency, "created_at": _safe_dt(o.created_at), "paid_at": _safe_dt(o.paid_at)} for o in rows]


@router.post("/payments/webhook")
async def payment_webhook(request: Request, x_payment_signature: str = Header(default=""), db: Session = Depends(get_db)):
    if not settings.payment_webhook_secret:
        raise HTTPException(status_code=503, detail="支付渠道尚未配置")
    raw = await request.body()
    expected = hmac.new(settings.payment_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not x_payment_signature or not hmac.compare_digest(expected, x_payment_signature.removeprefix("sha256=")):
        raise HTTPException(status_code=401, detail="支付回调签名无效")
    try:
        data = json.loads(raw)
        event_id = str(data["event_id"])
        order_no = str(data["order_no"])
        status_value = str(data["status"])
        amount = int(data["amount_minor"])
        currency = str(data["currency"]).upper()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="支付回调数据格式错误")
    if db.scalar(select(PaymentEvent).where(PaymentEvent.provider_event_id == event_id)):
        return {"received": True, "duplicate": True}
    order = db.scalar(select(Order).where(Order.order_no == order_no))
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if status_value != "paid":
        return {"received": True, "ignored": True}
    if order.status == "paid":
        return {"received": True, "already_paid": True}
    if order.status != "pending":
        raise HTTPException(status_code=409, detail="订单当前状态不允许支付")
    if amount != order.amount_minor or currency != order.currency:
        raise HTTPException(status_code=409, detail="订单金额或币种不匹配")
    product = db.get(Product, order.product_id)
    if product is None:
        raise HTTPException(status_code=409, detail="订单商品不存在")
    order.status = "paid"
    order.provider = "configured_webhook"
    order.provider_transaction_id = str(data.get("transaction_id", ""))[:128] or None
    order.paid_at = utc_now()
    db.add(PaymentEvent(
        provider_event_id=event_id, order_no=order_no,
        payload_hash=hashlib.sha256(raw).hexdigest(),
    ))
    if product.grants_permanent_license:
        license_record = db.scalar(select(License).where(License.user_id == order.user_id))
        if license_record is None:
            license_record = License(user_id=order.user_id)
            db.add(license_record)
        license_record.permanent = True
        license_record.permanent_granted_at = utc_now()
        license_record.source_order_id = order.order_no
    db.commit()
    audit(db, "payment_verified", "order", order.order_no, order.user_id)
    return {"received": True, "authorized": bool(product.grants_permanent_license)}


@router.post("/admin/orders/{order_no}/confirm-paid")
def admin_confirm_manual_payment(
    order_no: str, payload: ManualPaymentConfirmIn,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    order = db.scalar(select(Order).where(Order.order_no == order_no))
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "paid":
        raise HTTPException(status_code=409, detail="该订单已经核验并授权，不能重复确认")
    if order.status != "pending":
        raise HTTPException(status_code=409, detail="订单状态不允许核验")
    if order.amount_minor != 3000 or order.currency != "CNY":
        raise HTTPException(status_code=409, detail="订单金额不符合30元永久授权规则")
    product = db.get(Product, order.product_id)
    if product is None or not product.grants_permanent_license:
        raise HTTPException(status_code=409, detail="订单商品不是永久授权商品")
    order.status = "paid"
    order.provider = "manual_verified"
    order.provider_transaction_id = payload.transaction_id.strip()
    order.paid_at = utc_now()
    license_record = db.scalar(select(License).where(License.user_id == order.user_id))
    if license_record is None:
        license_record = License(user_id=order.user_id)
        db.add(license_record)
    license_record.permanent = True
    license_record.permanent_granted_at = utc_now()
    license_record.source_order_id = order.order_no
    db.commit()
    audit(db, "manual_payment_verified", "order", order.order_no, admin.id)
    return {"order_no": order.order_no, "status": "paid", "permanent_license_granted": True}


@router.get("/devices")
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    devices = db.scalars(select(DeviceActivation).where(DeviceActivation.user_id == user.id)).all()
    return [{"device_id": d.device_id, "platform": d.platform,
             "first_seen_at": _safe_dt(d.first_seen_at), "last_seen_at": _safe_dt(d.last_seen_at)} for d in devices]


@router.delete("/devices/{device_id}")
def remove_device(device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    device = db.scalar(select(DeviceActivation).where(
        DeviceActivation.user_id == user.id, DeviceActivation.device_id == device_id
    ))
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    db.delete(device)
    db.commit()
    audit(db, "device_removed", "device", device_id, user.id)
    return {"message": "设备已解除绑定；账号永久授权不会因此丢失"}


@router.get("/notices")
def list_notices(db: Session = Depends(get_db)):
    rows = db.scalars(select(Notice).where(Notice.published.is_(True)).order_by(desc(Notice.created_at)).limit(50)).all()
    return [{"id": n.id, "title": n.title, "body": n.body, "created_at": _safe_dt(n.created_at)} for n in rows]


@router.get("/releases")
def list_releases(platform: str | None = None, db: Session = Depends(get_db)):
    query = select(Release).where(Release.published.is_(True))
    if platform:
        query = query.where(Release.platform == platform)
    rows = db.scalars(query.order_by(desc(Release.created_at)).limit(30)).all()
    return [{"release_id": r.id, "platform": r.platform, "version": r.version,
             "notes": r.notes, "minimum_supported_version": r.minimum_supported_version} for r in rows]


@router.get("/releases/{release_id}/download")
def download_release(
    release_id: int, user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    license_record = db.scalar(select(License).where(License.user_id == user.id))
    if license_record is None or not license_record.permanent:
        raise HTTPException(status_code=403, detail="此正式版下载仅对已获得永久授权的账号开放")
    release = db.scalar(select(Release).where(Release.id == release_id, Release.published.is_(True)))
    if release is None:
        raise HTTPException(status_code=404, detail="版本不存在或已下架")
    if not release.download_url.startswith("https://"):
        raise HTTPException(status_code=503, detail="该版本下载地址尚未安全配置")
    audit(db, "release_download_authorized", "release", str(release.id), user.id)
    return RedirectResponse(url=release.download_url, status_code=302)


@router.post("/admin/products")
def admin_create_product(payload: ProductIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.amount_minor != 3000 or payload.currency.upper() != "CNY":
        raise HTTPException(status_code=422, detail="永久授权售价固定为人民币 30.00 元")
    if not payload.grants_permanent_license:
        raise HTTPException(status_code=422, detail="本商品必须授予永久授权")
    if db.scalar(select(Product).where(Product.code == payload.code)):
        raise HTTPException(status_code=409, detail="商品编码已存在")
    values = payload.model_dump()
    values["currency"] = payload.currency.upper()
    item = Product(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    audit(db, "product_created", "product", str(item.id), admin.id)
    return {"id": item.id, "code": item.code}


@router.post("/admin/notices")
def admin_create_notice(payload: NoticeIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = Notice(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    audit(db, "notice_created", "notice", str(item.id), admin.id)
    return {"id": item.id}


@router.post("/admin/releases")
def admin_create_release(payload: ReleaseIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not payload.download_url.startswith("https://"):
        raise HTTPException(status_code=422, detail="下载地址必须使用 HTTPS")
    item = Release(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    audit(db, "release_created", "release", str(item.id), admin.id)
    return {"id": item.id}


@router.get("/admin/audit")
def admin_audit(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..models import AuditEvent
    rows = db.scalars(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(200)).all()
    return [{"user_id": e.user_id, "action": e.action, "subject_type": e.subject_type,
             "subject_id": e.subject_id, "created_at": _safe_dt(e.created_at)} for e in rows]


@router.post("/projects")
def create_project(payload: ProjectIn, user: User = Depends(require_active_license), db: Session = Depends(get_db)):
    item = Project(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "title": item.title, "status": item.status}


@router.get("/projects")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Project).where(Project.user_id == user.id).order_by(desc(Project.created_at))).all()
    return [{"id": p.id, "title": p.title, "description": p.description, "status": p.status} for p in rows]


@router.get("/projects/{project_id}/novels")
def list_project_novels(
    project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    novels = db.scalars(select(Novel).where(Novel.project_id == project_id).order_by(desc(Novel.id))).all()
    return [{
        "id": novel.id,
        "title": novel.title,
        "analysis_status": novel.analysis_status,
        "chapter_count": db.query(Chapter).filter(Chapter.novel_id == novel.id).count(),
        "analyzed_chapter_count": db.query(Chapter).filter(Chapter.novel_id == novel.id, Chapter.analysis_json.is_not(None)).count(),
    } for novel in novels]


@router.post("/projects/{project_id}/novels")
def import_novel(project_id: int, payload: NovelIn, user: User = Depends(require_active_license), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    novel = Novel(project_id=project.id, title=payload.title, source_text=payload.text, analysis_status="pending")
    db.add(novel)
    db.flush()
    import re
    pattern = re.compile(r"(?m)^\s*(第[零一二三四五六七八九十百千万0-9]+[章节回].*|Chapter\s+\d+.*)$", re.I)
    matches = list(pattern.finditer(payload.text))
    if not matches:
        db.add(Chapter(novel_id=novel.id, chapter_no=1, title=payload.title, content=payload.text))
    else:
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(payload.text)
            block = payload.text[start:end].strip()
            lines = block.splitlines()
            title = lines[0].strip() if lines else f"第{idx + 1}章"
            body = "\n".join(lines[1:]).strip()
            db.add(Chapter(novel_id=novel.id, chapter_no=idx + 1, title=title, content=body))
    db.commit()
    db.refresh(novel)
    chapter_count = db.query(Chapter).filter(Chapter.novel_id == novel.id).count()
    return {"novel_id": novel.id, "chapter_count": chapter_count, "analysis_status": "pending",
            "message": "小说已导入并拆分章节；AI 深度解析需要配置模型服务后执行"}


@router.post("/projects/{project_id}/novels/{novel_id}/analyze")
async def analyze_novel(
    project_id: int, novel_id: int, request: Request, limit: int = 10, offset: int = 0,
    user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    enforce_rate_limit(db, f"ai-analysis:{user.id}:{request_fingerprint(request)}", 5, 3600)
    if limit < 1 or limit > 20 or offset < 0:
        raise HTTPException(status_code=422, detail="每次最多解析20章")
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    if project is None or novel is None:
        raise HTTPException(status_code=404, detail="项目或小说不存在")
    chapters = db.scalars(select(Chapter).where(Chapter.novel_id == novel.id).order_by(Chapter.chapter_no).offset(offset).limit(limit)).all()
    if not chapters:
        raise HTTPException(status_code=404, detail="没有可解析的章节")
    total_chapters = db.query(Chapter).filter(Chapter.novel_id == novel.id).count()
    results = []
    entities_created = 0
    for chapter in chapters:
        if len(chapter.content) > 30000:
            raise HTTPException(status_code=413, detail=f"第{chapter.chapter_no}章超过单次AI解析长度限制，请先拆分章节")
        result = await chat_json(
            "你是专业漫剧编剧与故事分析师。只返回JSON，字段包括 summary、characters、scenes、props、events、relationships、timeline、continuity_notes。保留原作主线，不编造原文没有的重要事实。",
            f"小说：{novel.title}\n章节：{chapter.title}\n正文：\n{chapter.content}",
            db=db, user_id=user.id,
        )
        chapter.analysis_json = json.dumps(result, ensure_ascii=False)
        for field_name, entity_type in (("characters", "character"), ("scenes", "scene"), ("props", "prop")):
            candidates = result.get(field_name, [])
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                if isinstance(candidate, str):
                    name, description, attributes = candidate.strip(), "", {}
                elif isinstance(candidate, dict):
                    name = str(candidate.get("name") or candidate.get("canonical_name") or candidate.get("title") or "").strip()
                    description = str(candidate.get("description") or candidate.get("appearance") or "")
                    attributes = candidate
                else:
                    continue
                if not name:
                    continue
                existing = db.scalar(select(StoryEntity).where(
                    StoryEntity.novel_id == novel.id,
                    StoryEntity.entity_type == entity_type,
                    StoryEntity.canonical_name == name,
                ))
                if existing is None:
                    db.add(StoryEntity(
                        entity_uuid=str(uuid4()), novel_id=novel.id, entity_type=entity_type,
                        canonical_name=name, description=description[:4000],
                        attributes_json=json.dumps(attributes, ensure_ascii=False),
                    ))
                    entities_created += 1
        results.append({"chapter_no": chapter.chapter_no, "analysis": result})
    has_more = offset + len(results) < total_chapters
    novel.analysis_status = "partially_analyzed" if has_more else "analyzed"
    db.commit()
    return {"novel_id": novel.id, "processed_chapters": len(results), "next_offset": offset + len(results), "has_more": has_more, "entities_created": entities_created, "results": results,
            "message": "章节解析已完成；请人工审核人物、场景、道具和关系识别结果"}


def _license_expired(started_at: datetime) -> bool:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= started_at + timedelta(hours=settings.trial_hours)


async def _generate_artifact(
    artifact_type: str, project_id: int, novel_id: int, payload: ArtifactRequest,
    request: Request, user: User, db: Session,
):
    enforce_rate_limit(db, f"ai-generation:{user.id}:{request_fingerprint(request)}", 20, 3600)
    if not user.license or (not user.license.permanent and (not user.license.trial_started_at or _license_expired(user.license.trial_started_at))):
        raise HTTPException(status_code=402, detail="免费试用已结束，请购买永久授权")
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    chapter = db.scalar(select(Chapter).where(Chapter.novel_id == novel_id, Chapter.chapter_no == payload.chapter_no))
    if project is None or novel is None or chapter is None:
        raise HTTPException(status_code=404, detail="项目、小说或章节不存在")
    if len(chapter.content) > 30000:
        raise HTTPException(status_code=413, detail="章节超过单次生成长度限制，请先拆分章节")
    if artifact_type == "script":
        system = "你是专业漫剧编剧。根据原文改编成可拍摄的漫剧剧本，保留主线、人物动机和关键事件。只返回JSON，包含 title、logline、scenes 数组，每场包含 location、time、characters、action、dialogue、emotion。"
    else:
        system = "你是专业分镜导演。将剧本/小说章节拆解为可执行分镜。只返回JSON，包含 aspect_ratio、shots 数组，每镜包含 shot_no、duration_seconds、shot_size、camera_move、visual_prompt、dialogue、sound、transition。"
    result = await chat_json(
        system,
        f"小说：{novel.title}\n章节：{chapter.title}\n正文：\n{chapter.content}\n用户补充要求：{payload.instructions}",
        db=db, user_id=user.id,
    )
    item = CreativeArtifact(
        project_id=project.id, novel_id=novel.id, artifact_type=artifact_type,
        title=f"{chapter.title or '章节'+str(chapter.chapter_no)}-{artifact_type}",
        content_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "artifact_type": item.artifact_type, "content": result}


@router.post("/projects/{project_id}/novels/{novel_id}/script")
async def generate_script(
    project_id: int, novel_id: int, payload: ArtifactRequest, request: Request,
    user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    return await _generate_artifact("script", project_id, novel_id, payload, request, user, db)


@router.post("/projects/{project_id}/novels/{novel_id}/storyboard")
async def generate_storyboard(
    project_id: int, novel_id: int, payload: ArtifactRequest, request: Request,
    user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    return await _generate_artifact("storyboard", project_id, novel_id, payload, request, user, db)


@router.get("/projects/{project_id}/novels/{novel_id}/artifacts")
def list_artifacts(
    project_id: int, novel_id: int,
    user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    if project is None or novel is None:
        raise HTTPException(status_code=404, detail="项目或小说不存在")
    rows = db.scalars(select(CreativeArtifact).where(
        CreativeArtifact.project_id == project_id, CreativeArtifact.novel_id == novel_id
    ).order_by(desc(CreativeArtifact.created_at))).all()
    return [{"id": a.id, "type": a.artifact_type, "title": a.title,
             "content": json.loads(a.content_json), "created_at": _safe_dt(a.created_at)} for a in rows]


@router.get("/projects/{project_id}/novels/{novel_id}/entities")
def list_story_entities(
    project_id: int, novel_id: int,
    user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    if project is None or novel is None:
        raise HTTPException(status_code=404, detail="项目或小说不存在")
    rows = db.scalars(select(StoryEntity).where(StoryEntity.novel_id == novel_id).order_by(StoryEntity.entity_type, StoryEntity.canonical_name)).all()
    return [{"id": e.id, "entity_uuid": e.entity_uuid, "type": e.entity_type,
             "name": e.canonical_name, "description": e.description,
             "attributes": json.loads(e.attributes_json), "approved": e.approved, "visual_asset_id": e.visual_asset_id} for e in rows]


@router.patch("/projects/{project_id}/novels/{novel_id}/entities/{entity_id}")
def review_story_entity(
    project_id: int, novel_id: int, entity_id: int, payload: EntityReviewIn,
    user: User = Depends(require_active_license), db: Session = Depends(get_db)
):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    entity = db.scalar(select(StoryEntity).where(StoryEntity.id == entity_id, StoryEntity.novel_id == novel_id))
    if project is None or novel is None or entity is None:
        raise HTTPException(status_code=404, detail="素材记录不存在")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(entity, key, value)
    db.commit()
    return {"id": entity.id, "approved": entity.approved, "name": entity.canonical_name}


@router.get("/projects/{project_id}/export")
def export_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    novels = db.scalars(select(Novel).where(Novel.project_id == project.id).order_by(Novel.id)).all()
    project_assets = db.scalars(select(MediaAsset).where(MediaAsset.project_id == project.id, MediaAsset.user_id == user.id)).all()
    result = {"project": {"id": project.id, "title": project.title, "description": project.description},
              "novels": [],
              "media_assets": [{"id": a.asset_uuid, "type": a.asset_type, "title": a.title,
                                "file_name": a.file_name, "sha256": a.sha256, "size_bytes": a.size_bytes}
                               for a in project_assets]}
    for novel in novels:
        chapters = db.scalars(select(Chapter).where(Chapter.novel_id == novel.id).order_by(Chapter.chapter_no)).all()
        entities = db.scalars(select(StoryEntity).where(StoryEntity.novel_id == novel.id)).all()
        artifacts = db.scalars(select(CreativeArtifact).where(CreativeArtifact.novel_id == novel.id)).all()
        result["novels"].append({
            "id": novel.id, "title": novel.title, "source_text": novel.source_text,
            "analysis_status": novel.analysis_status,
            "chapters": [{"chapter_no": ch.chapter_no, "title": ch.title, "content": ch.content,
                          "analysis": json.loads(ch.analysis_json)} for ch in chapters],
            "entities": [{"id": e.entity_uuid, "type": e.entity_type, "name": e.canonical_name,
                          "description": e.description, "attributes": json.loads(e.attributes_json),
                          "approved": e.approved} for e in entities],
            "artifacts": [{"type": a.artifact_type, "title": a.title,
                           "content": json.loads(a.content_json)} for a in artifacts],
        })
    return result


@router.post("/publishing/jobs")
def create_publish_job(payload: PublishIn, user: User = Depends(require_active_license), db: Session = Depends(get_db)):
    item = PublishJob(
        user_id=user.id, platform=payload.platform, title=payload.title,
        description=payload.description, media_url=payload.media_url,
        status="manual_required",
        last_error="尚未完成平台官方开发者资质与接口授权；请通过平台官方入口手动发布",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    audit(db, "publish_draft_created", "publish_job", str(item.id), user.id)
    return {"id": item.id, "platform": item.platform, "status": item.status,
            "auto_publish_available": False, "message": item.last_error}


@router.get("/publishing/jobs")
def list_publish_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(PublishJob).where(PublishJob.user_id == user.id).order_by(desc(PublishJob.created_at))).all()
    return [{"id": p.id, "platform": p.platform, "title": p.title, "status": p.status,
             "last_error": p.last_error, "created_at": _safe_dt(p.created_at)} for p in rows]
