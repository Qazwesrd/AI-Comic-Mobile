# 云端部署指南（Cloudflare Pages + Render + Neon）

本项目已准备静态网站与 FastAPI 后端的部署模板。**创建三个账号不等于网站已经上线**；仍需在各平台完成授权、创建项目并填入环境变量。

## 架构

- Cloudflare Pages：托管 `apps/web` 的 Next.js 静态导出。
- Render：运行 `apps/api` FastAPI 服务（仓库根目录的 `render.yaml`）。
- Neon：提供 PostgreSQL 数据库。
- GitHub：作为代码来源，三个平台均通过 GitHub 仓库部署。

## 1. 先创建 Neon 数据库

1. 登录 Neon 控制台，创建一个 PostgreSQL 项目。
2. 选择离主要用户较近的欧洲区域。
3. 打开项目的 Connect 页面，复制连接字符串。
4. 将连接字符串格式调整为 SQLAlchemy psycopg 格式：`postgresql+psycopg://用户名:密码@主机/数据库?sslmode=require`。
5. 只把连接字符串粘贴到 Render 的 `DATABASE_URL` 环境变量中；不要提交到 GitHub，也不要发到聊天中。

## 2. 将 API 部署到 Render

1. 登录 Render，选择 **New → Blueprint**。
2. 连接 GitHub，并授权访问 `Qazwesrd/AI-Comic-Mobile`。
3. 选择仓库和分支 `main`。Render 会读取仓库根目录的 `render.yaml`。
4. 在首次创建服务时，填写模板中标记为手动配置的环境变量。
5. `DATABASE_URL` 使用 Neon 连接串；`ADMIN_BOOTSTRAP_EMAILS` 填写你用于管理员登录的邮箱。
6. 邮件验证为生产环境必需项，必须填写可用 SMTP 服务的主机、用户名、密码和发件邮箱。
7. 部署完成后，在 Render 服务页面复制 HTTPS 服务地址，例如 `https://你的服务名.onrender.com`。
8. 打开 `https://你的服务地址/health`，应返回 JSON 且 status 为 ok。

### Render 必填环境变量

- `DATABASE_URL`：Neon PostgreSQL 连接串。
- `WEB_ORIGIN`、`APP_BASE_URL`：稍后填写 Cloudflare Pages 的正式 HTTPS 域名。
- `CORS_ORIGINS`：填写 Cloudflare Pages 的完整 origin，不带末尾路径；若有多个 origin，用逗号分隔。
- `SMTP_HOST`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM_EMAIL`：可用邮件服务。
- `ADMIN_BOOTSTRAP_EMAILS`：管理员邮箱。
- `AI_CONFIG_ENCRYPTION_KEY`：使用 Fernet 生成的独立密钥。
- `PAYMENT_WEBHOOK_SECRET`：只有在配置真实支付服务商回调时才设置；收款二维码人工核账不等于自动支付回调。

Render Blueprint 会自动生成 `APP_SECRET_KEY` 和 `TOKEN_PEPPER`。不要更换已投入使用的密钥，否则可能使现有会话/令牌失效。

## 3. 将网站部署到 Cloudflare Pages

1. 登录 Cloudflare，打开 **Workers & Pages → Create → Pages → Connect to Git**。
2. 授权 GitHub，选择 `Qazwesrd/AI-Comic-Mobile`。
3. Production branch 选择 `main`。
4. Root directory 设为 `apps/web`。
5. Build command 填写 `npm run build`。
6. Build output directory 填写 `out`。
7. 添加环境变量 `NEXT_PUBLIC_API_BASE_URL`，值为上一步 Render 的 HTTPS API 地址。
8. 保存并部署。Cloudflare 会分配一个 `*.pages.dev` 网址，可用手机浏览器访问。

## 4. 回填 API 的网站域名

Cloudflare Pages 首次部署后，复制实际的 `https://项目名.pages.dev` 域名，回到 Render 环境变量，设置：

- `WEB_ORIGIN=https://项目名.pages.dev`
- `APP_BASE_URL=https://项目名.pages.dev`
- `CORS_ORIGINS=https://项目名.pages.dev`

保存后重新部署 Render。若以后绑定自定义域名，三个变量也要同步更新。

## 5. 当前免费部署限制与上线前检查

- Render 免费 Web Service 会在空闲时休眠，首次唤醒可能较慢。
- 免费实例本地磁盘不是持久化存储。当前媒体文件默认保存在本地目录；**不要把 Render 免费实例当作可靠的永久素材/安装包存储**。正式开放上传前，必须把媒体存储迁移到 Cloudflare R2 或其他对象存储，并测试下载权限。
- Neon 数据库负责保存账号、订单和授权；启用自动备份/定期导出，并限制数据库连接串权限。
- 生产环境要求 SMTP 邮件验证。没有配置真实 SMTP 前，用户注册/找回密码流程不能视为已可用。
- 当前微信收款二维码流程需要管理员人工核对真实到账；尚不能宣称已接通微信支付商户 API 自动回调。
- 付款后发放永久授权前，必须核对金额、订单号和实际到账记录；不能仅凭截图或“我已付款”按钮发放授权。
- 正式销售前还需完成真实支付服务商接入、回调验签/查单/幂等/退款、R2 私有存储、正式 APK 签名、备份恢复和手机真机验收。

## 6. Android APK

网站部署成功后，需将 Render 的 API HTTPS 地址写入 Android 构建环境变量 `NEXT_PUBLIC_API_BASE_URL`，重新执行 Capacitor 同步和 Android 构建。仅部署网站不会自动修改此前生成的 APK；必须重新构建并安装测试。

## 安全提醒

- 不要把 Google 密码、Neon 连接串、SMTP 密码、Render 环境变量或签名密钥发到聊天。
- 不要将任何密钥提交到仓库。
- 第一次部署建议先做测试环境，不要收真实客户款项。
