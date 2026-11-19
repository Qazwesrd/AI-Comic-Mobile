from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/api/v1/ai-tools", tags=["ai-tools"])

# Official entry points only; no third-party login automation or scraping.
WEB_TOOLS = [
    {"id": "chatgpt", "name": "ChatGPT", "category": "text", "url": "https://chatgpt.com/", "tasks": ["小说分析", "人物关系", "剧本改编", "分镜规划"]},
    {"id": "deepseek", "name": "DeepSeek", "category": "text", "url": "https://chat.deepseek.com/", "tasks": ["小说分析", "剧情梳理", "剧本润色"]},
    {"id": "gemini", "name": "Google Gemini", "category": "text-image", "url": "https://gemini.google.com/", "tasks": ["文本创作", "图片理解", "创意整理"]},
    {"id": "grok", "name": "Grok", "category": "text-image", "url": "https://grok.com/", "tasks": ["文本创作", "创意分析"]},
    {"id": "doubao", "name": "豆包", "category": "text-image", "url": "https://www.doubao.com/", "tasks": ["人物形象", "场景概念", "道具设计"]},
    {"id": "jimeng", "name": "即梦 AI", "category": "image-video", "url": "https://jimeng.jianying.com/", "tasks": ["人物三视图", "场景图", "视频生成"]},
    {"id": "kling", "name": "可灵 AI", "category": "video", "url": "https://klingai.com/", "tasks": ["图生视频", "文生视频", "视频创作"]},
    {"id": "runway", "name": "Runway", "category": "video-editing", "url": "https://app.runwayml.com/", "tasks": ["AI 视频编辑", "视频生成", "画面处理"]},
    {"id": "capcut", "name": "剪映 / CapCut", "category": "video-editing", "url": "https://www.capcut.com/", "tasks": ["时间线剪辑", "字幕", "音频处理"]},
    {"id": "claude", "name": "Claude", "category": "text", "url": "https://claude.ai/", "tasks": ["长文本分析", "剧本编辑", "内容整理"]},
]


@router.get("")
def list_ai_tool_modes(user=Depends(get_current_user)):
    text_ready = bool(settings.ai_api_base_url and settings.ai_api_key and settings.ai_model)
    image_ready = bool(settings.image_api_base_url and settings.image_api_key and settings.image_model)
    audio_ready = bool(settings.audio_api_base_url and settings.audio_api_key and settings.audio_model)
    return {
        "modes": [
            {
                "id": "built-in", "name": "软件内置 AI 接口",
                "description": "软件后端调用已配置的模型服务，密钥不会返回到手机端。",
                "configured": text_ready,
                "capabilities": {"text": text_ready, "image": image_ready, "audio": audio_ready},
                "configuration_note": "当前由部署环境配置 AI_API_BASE_URL / AI_API_KEY / AI_MODEL、IMAGE_API_* 和 AUDIO_API_*。账号级自助配置将在后续阶段实现。",
            },
            {
                "id": "web", "name": "网页版 AI 工具",
                "description": "打开官方网页，由用户自行登录和操作；完成后下载文件，再导入本软件素材库。",
                "configured": True,
                "capabilities": {"text": True, "image": True, "video": True, "video_editing": True},
            },
        ],
        "web_tools": WEB_TOOLS,
        "workflow": [
            "选择网页版工具并打开官方网站",
            "用户自行登录、上传素材并完成生成或剪辑",
            "从网页版下载图片、视频、剧本、音频或字幕文件",
            "返回本软件素材库上传文件，再关联到小说、分镜或剪辑项目",
        ],
        "limitations": [
            "本软件不会读取第三方网页登录态、自动点击生成按钮或绕过验证码",
            "第三方网页生成结果不会自动回传；需要用户下载后导入",
            "各网站账号、地区、套餐、额度和版权规则由其服务商决定",
        ],
    }
