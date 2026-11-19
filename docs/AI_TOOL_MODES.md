# Android 双模式 AI 工具接入

## 产品规则

AI 漫剧与独立 AI 视频剪辑共用两种方式：

1. **软件内置 AI API**：后端调用部署方配置的文本、图片和语音模型，API Key 不下发到手机。
2. **手机已安装的 AI 客户端**：Android 端通过 Capacitor App Launcher 检测指定官方应用包名，并启动已安装客户端。

当前目录仅收录已核实包名的 Android 客户端：ChatGPT、DeepSeek、Claude、豆包、即梦 AI、CapCut。包名分别为 `com.openai.chatgpt`、`com.deepseek.chat`、`com.anthropic.claude`、`com.larus.nova`、`com.bytedance.dreamina`、`com.lemon.lvoverseas`。应用商店入口作为未安装时的安装指引。

## 使用流程

选择客户端 → 检查是否安装 → 复制本次任务提示词 → 启动第三方客户端 → 用户自行登录、上传和操作 → 将结果保存到手机 → 回到本软件素材库选择文件导入 → 用户确认素材归属。

## Android 包可见性

Android 11+ 要求在 `AndroidManifest.xml` 的 `<queries>` 中声明需要检测的包名。本仓库的 Android Debug APK 工作流在生成原生工程后，仅添加上面六个已核实应用的包名，不申请广泛的 `QUERY_ALL_PACKAGES` 权限。

## 明确限制

- 能检测并启动应用，不代表可以自动控制第三方 App 的界面。
- 不读取第三方 App 私有数据，不模拟登录，不自动点击生成，不绕过验证码。
- 当前素材回传采用用户保存文件后，通过本软件素材库导入；并非第三方 App 自动回传。
- 第三方账号、会员、地区、额度、功能和导出权限由服务商决定。
- 未核实的应用包名不加入检测清单；可灵、Runway 等移动端适配待逐一核实后再添加。
- 本阶段只交付 Android；iOS 暂缓，后续按实际需求评估。

## 内置 API 配置

当前部署环境变量：
- `AI_API_BASE_URL`、`AI_API_KEY`、`AI_MODEL`
- `IMAGE_API_BASE_URL`、`IMAGE_API_KEY`、`IMAGE_MODEL`
- `AUDIO_API_BASE_URL`、`AUDIO_API_KEY`、`AUDIO_MODEL`

账号级 API 配置、加密凭据管理、连通性测试、费用风险提示和调用日志仍在后续开发范围。


## 安卓素材交接中心（第一批）

- 在安卓应用内通过系统文件选择器一次选择多个文件。
- 按文件扩展名和浏览器提供的 MIME 类型预判素材分类；用户可在上传前手动修改。
- 支持图片、视频、音频、SRT/VTT、TXT/Markdown/JSON/CSV 和 PDF。
- 批量上传逐个执行现有 8 MiB 分片流程；单文件上限遵循服务端配置（默认 2 GiB）。
- 上传时可选择一个本人拥有的漫剧项目；已入库素材也可修改项目归属、取消关联和人工确认。
- 后端对项目归属和素材所有权做服务端校验；不允许跨账号读取或修改。
- 纯文本文件保存为素材，不会自动执行或导入为小说正文。
- 本批次通过系统文件选择器导入；Android 分享菜单直接“分享至本软件”的原生接收能力仍待单独实现。
- 文件分类只是按扩展名/MIME 的初步判断，不是 AI 视觉识别；内容理解和自动关联建议后续接入。
