# 移动端与官网构建说明

## 产品边界

- 官网：Next.js 静态网站，只展示产品介绍、功能说明、使用教程、付款授权和授权后的下载入口；不作为创作工作台，也不提供 PWA 安装。
- Android App：通过 Capacitor 将独立的软件工作台打包进 APK。App 启动后进入 `/workspace/`，不显示官网首页；创作数据通过 HTTPS 连接云端 API。
- iOS App：使用同一套 Capacitor App 工作区和云端 API。iOS 构建需要 macOS/Xcode；签名安装包需要 Apple 开发者账号、证书和 provisioning profile。当前尚未配置签名发布流水线。

## 必需的 API 地址配置

Android APK 和 Cloudflare Pages 都是静态前端构建，API 地址会在构建时写入前端资源。不能使用 `127.0.0.1`、`localhost` 或 `*.invalid` 作为手机安装包的后端地址。

- GitHub：进入 Settings → Secrets and variables → Actions → Variables，新增仓库变量 `NEXT_PUBLIC_API_BASE_URL`，值填写真实部署的 HTTPS API 域名根地址。不要带 `/api/v1` 路径、查询参数或尾部斜杠。
- Cloudflare Pages：进入项目 `ai-comic-mobile` 的 Settings → Environment variables，为 Production 和 Preview 环境分别配置同名变量，然后重新部署。
- API 服务必须已部署并可通过 `https://你的真实-api-域名/health` 访问。不要把 API 密钥放进 `NEXT_PUBLIC_*` 变量。

Android 工作流会在编译前检查该变量；未配置、不是 HTTPS 或仍为本机/占位地址时会直接失败，不再生成无法连接服务器的 APK。

## Android APK

仓库提供 GitHub Actions 工作流：Android Debug APK。

1. 先按上面的说明配置真实的 `NEXT_PUBLIC_API_BASE_URL`。
2. 合并代码到 `main`，或在 GitHub Actions 中打开 Android Debug APK 工作流运行。
3. 构建成功后，在该次 workflow run 的 Artifacts 下载 `ai-comic-mobile-android-debug`。
4. 这是 debug APK，仅用于内部安装验证；正式发布需要 Android release keystore、签名配置、版本号管理和真实设备验收。

本地 Windows 开发机可在 `apps/web` 目录执行：

```powershell
npm install
$env:NEXT_PUBLIC_API_BASE_URL = "https://你的真实-api-域名"
npm run build
npx cap add android
npx cap sync android
npx cap open android
```

Android Studio 中选择 Build → Generate Signed Bundle / APK 生成签名发布包。不要把 keystore 或密码提交到 GitHub。

## iOS App

在 macOS 安装 Xcode 后，在 apps/web 目录执行：

```bash
npm install
export NEXT_PUBLIC_API_BASE_URL="https://你的真实-api-域名"
npm run build
npx cap add ios
npx cap sync ios
npx cap open ios
```

Xcode 中配置 Bundle Identifier、Apple Developer Team、签名证书和 provisioning profile 后，才能生成可安装到真实 iPhone 的签名包或通过 TestFlight 分发。Windows 电脑不能直接完成最终 iOS 签名构建。

## 注意

- API URL 在 Next.js 构建时写入前端资源；更换后端域名需要重新构建。
- 默认 127.0.0.1 地址只适用于本机联调，不能用于用户手机安装包。
- 测试版和正式版必须使用同一套 App 工作区代码；试用与永久授权状态由服务器区分。
- 正式下载接口只在服务器核实账号已获得永久授权后开放。
- 当前 Android 工作流产物为 debug APK，正式签名和 Android/iOS 真机验收仍需后续完成。
