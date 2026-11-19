# AI 视频剪辑工作台技术方案

## 目标与边界

AI 视频剪辑与 AI 漫剧是并列的独立创作产品入口。剪辑项目可以导入用户已有视频，不要求先创建漫剧/小说项目；剪辑成片可选择保存到通用私有素材库。AI 漫剧仍保留小说解析、人物/场景/道具、剧本、分镜、配音字幕和漫剧合成流程。

本功能不自动发布到平台。需要发布时，用户主动进入现有发布中心；发布平台仍仅限抖音、红果短剧、快手，并遵守官方接口授权策略。

## 典型使用流程

1. 新建剪辑项目，设置名称、目标比例和可选输出用途。
2. 上传一个或多个源视频。上传支持分片、断点续传、哈希校验；原始文件不可被编辑任务覆盖。
3. 后端执行媒体探测，读取时长、分辨率、帧率、编码、音轨/字幕轨道，并生成代理预览、缩略图和音频波形。
4. 用户输入自然语言要求。AI结合媒体元数据、镜头/语音分析结果生成剪辑计划。
5. 剪辑计划必须是经过 Pydantic schema 校验的结构化 JSON：素材 ID、源入点/出点、目标时间线位置、轨道、排序、字幕、音量、转场和解释。拒绝越界时间码、未知素材 ID、不支持的滤镜/转场和任意 shell/FFmpeg 命令。
6. 用户在多轨时间线检查并编辑计划。AI建议只是草稿，用户可逐条接受、拒绝或再次描述修改。
7. 生成低清代理预览；用户确认后创建正式渲染任务。
8. 渲染任务进入持久化队列，支持进度、取消、失败原因、重试和进程重启恢复。成片保存为新的私有素材，不修改源视频。

## 第一阶段能力范围

- 单项目多源视频导入、文件管理和媒体元数据。
- 通过可配置 AI 服务生成剪辑计划；无视觉模型时可先基于用户提供的描述、字幕/转录文本和媒体元数据工作，并明确标注分析能力边界。
- 镜头切分、静音/停顿检测、语音转录、精彩片段推荐采用可插拔服务；供应商不可用时显示未配置，不伪造分析结果。
- 时间线至少包含视频、原声/配音、背景音乐和字幕轨道。
- 基础编辑：片段裁剪、分割、移动、排序、删除、静音/音量、字幕编辑、淡入淡出和基础转场。
- 输出横屏 16:9、竖屏 9:16、方形 1:1；编码、分辨率、帧率和码率只显示部署环境实际支持的选项。
- 支持 MP4 常见 H.264/AAC 输出；实际输入格式由服务器 FFmpeg 构建能力决定。

## 建议领域模型

- VideoEditProject：owner_id、title、status、aspect_ratio、created_at、updated_at。
- VideoSource：project_id、asset_id、duration_ms、width、height、fps、video_codec、audio_codec、probe_status。
- VideoEditPlan：project_id、source_revision、instruction、plan_json、provider、model、status、created_at。
- TimelineRevision：project_id、revision、timeline_json、created_by、created_at。
- VideoRenderJob：project_id、timeline_revision、status、progress、output_asset_id、error_code、error_message、started_at、finished_at。
- MediaAnalysisJob：source_id、analysis_type、provider、status、result_json、error_code。

所有模型必须关联 owner_id，并在每个读写/下载/任务状态接口进行服务端归属校验。时间线修改采用版本号或乐观锁，避免多端覆盖。

## API 草案

- POST /api/video-editing/projects：创建剪辑项目。
- GET /api/video-editing/projects：列出当前用户剪辑项目。
- GET/PATCH/DELETE /api/video-editing/projects/{project_id}：读取、更新、删除项目。
- POST /api/video-editing/projects/{project_id}/sources/init：初始化分片上传。
- POST /api/video-editing/projects/{project_id}/sources/{source_id}/complete：完成上传并排队媒体探测。
- GET /api/video-editing/projects/{project_id}/sources：列出源素材和媒体元数据。
- POST /api/video-editing/projects/{project_id}/ai-plan：提交自然语言剪辑要求并创建 AI 计划任务。
- GET /api/video-editing/plans/{plan_id}：获取分析状态和结构化计划。
- POST /api/video-editing/projects/{project_id}/timeline：保存新的时间线版本。
- GET /api/video-editing/projects/{project_id}/timeline：读取当前时间线。
- POST /api/video-editing/projects/{project_id}/renders：提交预览或正式渲染。
- GET /api/video-editing/renders/{job_id}：读取渲染状态和进度。
- POST /api/video-editing/renders/{job_id}/cancel：请求取消可取消任务。

路由名称为设计草案，编码时应先核对现有 API 约定，避免与现有素材/漫剧导出接口冲突。

## 后台任务与渲染

当前短任务 BackgroundTasks 不适合长视频处理。视频剪辑必须使用数据库持久化任务记录和独立 worker；可先采用数据库任务表 + worker 轮询，部署时再引入 Redis/Celery 或等价队列。worker 需具备任务租约/心跳、超时、最大重试、幂等输出、临时文件清理和崩溃恢复。

FFmpeg 参数只能由服务端根据经过校验的时间线生成。禁止把用户文本或模型返回内容拼接成 shell 命令。执行时使用参数数组、受控工作目录、资源/时长限制和进程超时。对上传文件做 MIME/魔数校验、路径隔离、大小限制和恶意文件防护。

## AI 适配器

定义统一接口但不假设所有厂商功能相同：
- InstructionPlanner：自然语言指令到剪辑决策。
- VideoUnderstanding：镜头/场景理解与片段描述。
- SpeechRecognition：语音转录与时间戳。
- SilenceAndSceneDetection：静音区间与镜头边界检测。

每个适配器声明能力、输入限制、支持格式、计费/配额信息和错误类型。没有配置供应商时返回可操作的配置错误；不能返回伪造成功结果。密钥只保存在服务端，调用前检查用户网络/付费开关及预算策略，记录用量与失败日志。

## 验收标准

- 用户可独立创建剪辑项目，不需要创建漫剧项目。
- 上传的原视频在整个剪辑和渲染过程中保持不变。
- AI计划中的素材引用和时间码全部通过 schema 和边界验证。
- 时间线保存、重新打开和版本恢复一致。
- 渲染进度可持久化；API/worker重启后任务不会静默丢失。
- 用户只能访问自己的项目、源视频、计划、时间线和成片。
- 取消、超时、磁盘不足、FFmpeg失败、AI供应商超时均有明确状态和错误提示。
- 通过小视频、长视频、多源素材、弱网续传、非法时间码和跨用户访问测试。
- 未接入真实供应商/未完成设备测试时，界面明确显示未配置或待验收，不宣称AI视觉分析或正式渲染已可用。
