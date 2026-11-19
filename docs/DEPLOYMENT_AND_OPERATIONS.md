# 部署与外部服务配置

## 本地开发

1. 安装 Python 3.12。
2. 在 apps/api 创建虚拟环境并安装 requirements.txt。
3. 复制 .env.example 为 .env，至少设置随机 APP_SECRET_KEY。
4. 执行数据库迁移：

   ```powershell
   cd apps/api
   alembic upgrade head
   ```

5. 启动 API：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（从 apps/api 目录运行）。
6. 在 apps/web 安装 npm 依赖，复制 web .env.example，启动 Next.js。

开发环境启动时会调用 SQLAlchemy create_all 作为新数据库的便捷初始化；已有数据库结构升级仍应执行 Alembic。

## 生产环境必需项

- 使用 PostgreSQL，DATABASE_URL 采用 SQLAlchemy psycopg 连接格式。
- 设置足够长且随机的 APP_SECRET_KEY、独立 TOKEN_PEPPER。
- APP_ENV=production、HTTPS、精确 CORS_ORIGINS、WEB_ORIGIN 和 APP_BASE_URL。
- 执行 alembic upgrade head；生产服务启动不会自动创建或修改数据库结构。
- 设置 SMTP_HOST、SMTP_PORT、SMTP_USERNAME、SMTP_PASSWORD、SMTP_FROM_EMAIL，并启用 REQUIRE_EMAIL_VERIFICATION。
- 设置 ADMIN_BOOTSTRAP_EMAILS，只填写可信管理员邮箱；该邮箱首次注册或登录时被提升为管理员。
- AI_API_BASE_URL 应指向兼容 OpenAI Chat Completions 的服务地址（通常以 /v1 结尾），并设置 AI_API_KEY 与 AI_MODEL。密钥只放服务端环境变量。
- 配置数据库备份、日志脱敏、告警和密钥轮换。

## 邮件安全

验证邮箱令牌和重置密码令牌均只保存 HMAC 哈希，验证/重置成功后一次性失效。邮件功能只有在 SMTP 配置后才能真实发送。开发环境未配置 SMTP 时不会把原始令牌返回给浏览器。

## 支付边界（重要）

当前实现的是通用 HMAC webhook 验签与订单/授权业务逻辑，不是 Stripe、支付宝、微信支付等任何具体服务商的正式 SDK 适配器。支付订单接口目前只创建待支付订单；在真实支付服务商适配器、签名规范、查单接口、商户号和真实回调地址全部配置并通过测试之前，不应收款，也不会把 checkout URL 当作已接通支付。上线前必须实现对应服务商的正式验签、金额/币种/商户/订单核对、幂等和退款处理，并做真实小额测试。

## AI 创作边界

文本章节分析、剧本改编和分镜规划使用 OpenAI 兼容 Chat Completions 接口。尚未实现图像/三视图生成、音频生成、视频生成、时间线编辑和 FFmpeg 导出；不要把文本分镜 JSON 误认为已生成图片或视频。

## 视频发布边界

目前发布中心只保存用户发布草稿并明确标记 manual_required。抖音、红果短剧和快手的官方自动发布能力必须分别完成开发者资质、账号授权、平台审核和真实账号测试后才能启用。不能使用模拟登录、抓取私有接口或验证码绕过。

## 文件与移动端

当前小说文本导入接口有 5 MB 字符长度上限；尚未接入对象存储、分片视频上传和 CDN。APK 签名构建、iOS Safari 真机验证、Capacitor 原生封装和正式下载文件托管仍是上线前工作。


## 私有素材存储与分片上传

- 默认素材目录为 MEDIA_ROOT（默认 ./storage/media），生产环境应挂载持久化磁盘或迁移到对象存储。
- 单文件上限由 MAX_UPLOAD_BYTES 控制，默认 2 GiB；浏览器按 8 MiB 分片上传，上传任务 24 小时过期。
- 上传 API 校验账号归属、项目归属、扩展名/MIME 类型、分片长度，并计算最终 SHA-256。
- 素材下载必须经过账号鉴权；原始文件不暴露为公共静态 URL。
- 生产部署必须配置持久化卷、磁盘容量告警、备份和恶意文件扫描。当前尚未接入 S3/R2 等对象存储或 CDN。


## 分镜静帧合成

- 服务器必须安装 FFmpeg，并确保 API 运行进程的 PATH 能找到 ffmpeg。
- 合成接口把用户选择的图片按顺序和时长拼接为 MP4，可选循环背景音，支持横屏 16:9 与竖屏 9:16。
- 这是静帧分镜预览合成，不是 AI 动态视频生成，也不包含字幕烧录、转场动画或复杂时间线编辑。
- 当前任务由 FastAPI BackgroundTasks 在 API 进程内执行；进程重启可能中断任务。生产环境应迁移到 Celery/RQ 等持久化任务队列，并配置 CPU/内存/时长配额。


## AI 图片与配音服务

- IMAGE_API_BASE_URL、IMAGE_API_KEY、IMAGE_MODEL：需要兼容 OpenAI Images Generations 格式的图像服务。服务端会请求 /images/generations，支持返回 base64 或 HTTPS 图片 URL。
- AUDIO_API_BASE_URL、AUDIO_API_KEY、AUDIO_MODEL：需要兼容 OpenAI Audio Speech 格式的语音服务。服务端会请求 /audio/speech 并保存 MP3。
- 图片生成支持人物三视图参考图、场景概念图和道具三视图；生成结果先进入私有素材库，用户仍需人工审核。
- 不同厂商对图片/语音 API 的兼容程度不同；配置前应以对应厂商文档确认 endpoint、模型名、尺寸、语音和返回格式。未配置时 API 明确返回 503，不会假装生成成功。
