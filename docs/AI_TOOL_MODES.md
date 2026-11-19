# Android 双模式 AI 工具接入

## 产品规则

AI 漫剧与独立 AI 视频剪辑共用两种方式：

1. **软件内置 AI API**：后端调用部署方配置的文本、图片和语音模型，API Key 不下发到手机。
2. **手机已安装的 AI 客户端**：Android 端通过 Capacitor App Launcher 检测指定官方应用包名，并启动已安装客户端。

当前目录仅收录已核实包名的 Android 客户端：ChatGPT、DeepSeek、Claude、豆包、即梦 AI。包名分别为 `com.openai.chatgpt`、`com.deepseek.chat`、`com.anthropic.claude`、`com.larus.nova`、`com.bytedance.dreamina`。应用商店入口作为未安装时的安装指引。

## 使用流程

选择客户端 → 检查是否安装 → 复制本次任务提示词 → 启动第三方客户端 → 用户自行登录、上传和操作 → 将结果保存到手机 → 回到本软件素材库选择文件导入 → 用户确认素材归属。

## Android 包可见性

Android 11+ 要求在 `AndroidManifest.xml` 的 `<queries>` 中声明需要检测的包名。本仓库的 Android Debug APK 工作流在生成原生工程后，仅添加上面五个已核实应用的包名，不申请广泛的 `QUERY_ALL_PACKAGES` 权限。

## 明确限制

- 能检测并启动应用，不代表可以自动控制第三方 App 的界面。
- 不读取第三方 App 私有数据，不模拟登录，不自动点击生成，不绕过验证码。
- 当前素材回传采用用户保存文件后，通过本软件素材库导入；并非第三方 App 自动回传。
- 第三方账号、会员、地区、额度、功能和导出权限由服务商决定。
- 未核实的应用包名不加入检测清单；剪映/CapCut、可灵、Runway 等移动端适配待逐一核实后再添加。
- 本阶段只交付 Android；iOS 暂缓，后续按实际需求评估。

## 内置 API 配置

当前部署环境变量：
- `AI_API_BASE_URL`、`AI_API_KEY`、`AI_MODEL`
- `IMAGE_API_BASE_URL`、`IMAGE_API_KEY`、`IMAGE_MODEL`
- `AUDIO_API_BASE_URL`、`AUDIO_API_KEY`、`AUDIO_MODEL`

账号级 API 配置、加密凭据管理、连通性测试、费用风险提示和调用日志仍在后续开发范围。
