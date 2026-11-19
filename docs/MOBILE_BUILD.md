# 移动端构建说明

## PWA / iPhone

网页采用 Next.js 静态导出，PWA manifest 和 service worker 提供基础离线壳。部署 HTTPS 域名后，iPhone 用户使用 Safari 打开官网，选择“添加到主屏幕”。这不是原生 IPA；原生 iOS 构建需要 macOS、Xcode、Apple 开发者签名与分发配置。

## Android APK

仓库提供 GitHub Actions 工作流：Android Debug APK。正式运行前：

1. 在 GitHub 仓库 Settings → Secrets and variables → Actions → Variables 中设置 NEXT_PUBLIC_API_BASE_URL，值必须是部署后的 HTTPS API 地址。
2. 合并代码到 main。
3. 打开 Actions → Android Debug APK → Run workflow。
4. 构建成功后，在该次 workflow run 的 Artifacts 下载 ai-comic-mobile-android-debug。
5. 这是 debug APK，仅用于内部安装验证；正式发布需要 Android release keystore、签名配置、版本号管理和真实设备验收。

本地 Windows 开发机可在 apps/web 目录执行：

```powershell
npm install
$env:NEXT_PUBLIC_API_BASE_URL = "https://你的API域名"
npm run build
npx cap add android
npx cap sync android
npx cap open android
```

Android Studio 中选择 Build → Generate Signed Bundle / APK 生成签名发布包。不要把 keystore 或密码提交到 GitHub。

## 注意

- API URL 在 Next.js 构建时写入前端资源；更换后端域名需要重新构建。
- 默认 127.0.0.1 地址只适用于本机联调，不能用于用户手机安装包。
- 尚未完成 Android 真机验证、iOS Safari 真机验证或正式签名发布。
