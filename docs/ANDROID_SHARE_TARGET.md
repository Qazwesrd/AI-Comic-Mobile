# Android 原生分享接收：首版实现

## 当前实现

Android Debug APK 工作流在 `npx cap add android` 之后执行 `scripts/configure-android-share.py`，生成并配置：

- Capacitor `MainActivity` 注册 `ShareReceiver` 原生插件。
- 注册 `ACTION_SEND` 与 `ACTION_SEND_MULTIPLE`，支持图片、视频、音频、文本和 PDF MIME。
- 通过 ContentResolver 读取分享的 `content://` URI，不把 URI 当成本地文件路径。
- 复制到应用私有缓存；不把整个视频转成 Base64。
- JS 端按 8 MiB 请求原生分块，复用现有分片上传 API。
- 素材进入待导入队列，用户仍需确认分类和项目后再上传。

## 构建

在仓库 Actions 运行 **Android Debug APK**。需要先配置仓库变量 `NEXT_PUBLIC_API_BASE_URL` 为可从手机访问的 HTTPS API 地址。构建成功后下载 artifact `ai-comic-mobile-android-debug`。

## 重要限制

- 当前代码需要 Android Debug APK 构建成功后才能确认原生代码与 Capacitor 版本兼容。
- 还没有 Android 真机测试结论；不能保证所有第三方应用都提供可分享的文件 URI。
- 当前缓存清理策略依赖 Android 系统缓存回收；后续应增加显式清理和失败恢复。
- Android 分享目标显示名称和 MIME 选择由来源应用及系统共同决定。
- 不读取第三方应用私有数据，不模拟点击、不绕过登录或验证码。
- 当前分享入口在素材交接页面读取待处理文件；如果应用从分享菜单冷启动，用户打开素材交接中心后读取待导入项。

## 真机验收清单

- [ ] Android 13、14、15 上本应用显示在图片/视频/音频/PDF分享目标中。
- [ ] ACTION_SEND 单文件分享。
- [ ] ACTION_SEND_MULTIPLE 多文件分享。
- [ ] 应用冷启动与后台唤醒两种状态。
- [ ] 100 MiB 以上视频以 8 MiB 分块读取和上传。
- [ ] 网络中断、重复分享、取消和上传失败的处理。
- [ ] ChatGPT、DeepSeek、豆包、即梦 AI 的分享菜单逐一验证（以各 App 实际提供的分享能力为准）。
