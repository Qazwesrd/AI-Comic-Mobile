# Android 原生分享接收（阶段实施说明）

## 目标

让其他 Android 应用通过系统分享菜单把图片、视频、音频、字幕和文档交给 AI 漫剧手机版。接收后由用户选择暂存素材库或关联漫剧项目，再走现有 8MB 分片上传接口。

## 当前仓库状态

当前前端已经使用 Capacitor 7，但仓库主分支没有提交生成后的 `apps/web/android` 原生工程，也没有可直接安装的原生分享接收器。仅有 PWA 页面无法注册 Android 系统的 ACTION_SEND / ACTION_SEND_MULTIPLE 分享目标。

因此本阶段先固定原生接入契约和安全边界；不能把“有 Capacitor 配置”误报为“分享接收已经可用”。生成 Android 工程后，必须把原生实现接入 MainActivity，并在 AndroidManifest.xml 注册 Intent Filter，再执行真机验收。

## Intent 约定

- Activity 接收 `android.intent.action.SEND` 和 `android.intent.action.SEND_MULTIPLE`。
- MIME 范围：`image/*`、`video/*`、`audio/*`、`text/*`、`application/pdf`。
- 读取 `EXTRA_STREAM` 与 `ClipData`，保留 `FLAG_GRANT_READ_URI_PERMISSION` 授权。
- 通过 ContentResolver 流式复制到应用私有缓存；不得假设第三方 URI 是真实文件路径。
- 大文件必须分块读取/上传，不得一次性转成 Base64 或读入内存。
- 接收后仅显示待导入列表；用户确认素材类型和目标项目后才上传。不得自动猜测项目。
- 临时文件在上传成功或用户取消后清理；失败时保留重试入口。
- 不申请 QUERY_ALL_PACKAGES；客户端探测仍采用逐个声明目标应用包名的策略。

## 安全与兼容

- 只处理系统授予读取权限的 content:// URI；拒绝未知 scheme。
- 文件名从 ContentResolver DISPLAY_NAME 获取并清理路径分隔符。
- MIME 只作提示，扩展名和服务端白名单仍需校验。
- 限制每次分享的文件数量和单文件大小，具体上限与服务端配置一致。
- 不读取第三方应用私有目录，不模拟点击，不绕过登录、会员或验证码。

## 验收清单

1. Android 13/14/15 真机上，图片、视频、音频、PDF分别能在系统分享菜单看到本应用。
2. 单文件与多文件分享均可接收，文件名、MIME、大小正确。
3. 100MB以上视频以流式方式暂存并分片上传，不发生整文件内存加载。
4. 分享后冷启动和应用已在后台两种状态都能接收。
5. 用户取消、上传失败、网络中断、重复分享均有明确状态。
6. 跨用户素材隔离、项目归属校验仍由服务端执行。
7. 至少测试 ChatGPT、DeepSeek、豆包、即梦 AI；是否显示分享目标取决于各应用实际分享能力。

## 下一步

在 Android 原生工程生成后，加入原生 Intent Filter 与 Capacitor 插件桥接，再让素材交接页面消费分享事件并复用现有分片上传逻辑。未通过真机清单前，不宣传该功能已上线。
