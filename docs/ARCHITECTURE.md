# 技术架构

## 1. 总体结构
采用前后端分离、移动优先的架构：
- `apps/web`：Next.js + TypeScript + 响应式 UI，承载手机端应用与官网。
- `apps/api`：Python FastAPI，提供账号、项目、AI 编排、资产、导出、订单、授权和发布任务 API。
- `packages/shared`：共享类型、校验规则和 API 契约。
- `apps/mobile`：后续放置 Capacitor Android 工程与原生适配；iOS 首期以 PWA 交付。
- `infra`：部署、反向代理、数据库和对象存储配置。
- `docs`：产品、架构、安全和发布平台说明。

## 2. 技术选型
- Web/PWA：Next.js、React、TypeScript。
- Android 容器：优先评估 Capacitor；APK 由 CI 构建并签名。
- iOS：首期 Safari PWA；原生 App 后续按 Apple 官方分发要求决策。
- API：Python 3.12+、FastAPI、Pydantic。
- ORM/迁移：SQLAlchemy、Alembic。
- 数据库：本地开发 SQLite；线上 PostgreSQL。
- 文件：开发期本地存储适配器；生产环境对象存储适配器。
- 异步任务：先使用数据库任务表/轻量队列，负载增长后引入 Redis + worker。

## 3. 服务模块
- identity：注册、登录、会话、密码重置。
- projects：作品项目、小说导入、章节与版本。
- analysis：人物、关系、场景、道具、事件和世界设定识别。
- generation：剧本、角色/场景/道具图、分镜和漫剧生成任务编排。
- media：素材、上传、合成、导出；不实现 AI 视频剪辑。
- publishing：抖音/红果短剧/快手的适配器接口、授权状态、发布任务与回执。
- billing：商品、订单、支付回调验签和退款状态。
- licensing：72 小时试用、永久授权、设备绑定与恢复。
- admin：官网内容、版本、公告、订单和授权运营管理。
- audit：安全审计和关键操作记录。

## 4. 数据边界
关键实体建议包括 User、Session、Project、Novel、Chapter、Character、Scene、Prop、Script、Storyboard、MediaAsset、ExportJob、PlatformAccount、PublishJob、Order、PaymentEvent、License、DeviceActivation、AppRelease、Announcement。
所有用户数据实体必须包含 owner/user 关联并在服务端强制校验权限。支付回调事件应具备幂等键，授权发放需幂等。

## 5. 安全原则
- AI 服务密钥只保存在服务端加密配置中。
- 支付回调必须验证签名、金额、币种、商户订单号和最终支付状态。
- 客户端展示的付款成功页面不能作为授权凭证。
- 试用开始时间由服务端记录，使用 UTC 时间并由服务端判断到期。
- 访问令牌使用安全存储；管理后台启用强认证和角色权限。
- 发布平台授权令牌加密存储、最小权限、可撤销；不得记录明文令牌。
- 上传文件校验类型、大小、归属和恶意内容风险。

## 6. 部署方向
本地开发可一条命令启动 Web 与 API；线上部署 Web/API、PostgreSQL、对象存储和后台任务服务。开发、测试、生产环境配置隔离。所有密钥由环境变量或密钥管理服务提供，不提交到 Git。
