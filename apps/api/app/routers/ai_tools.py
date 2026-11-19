from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/api/v1/ai-tools", tags=["ai-tools"])

# Android package IDs are listed only where verified against an official app-store listing.
# Launching a client does not grant control over its UI or access to its private data.
ANDROID_APPS = [
    {
        "id": "chatgpt", "name": "ChatGPT", "category": "text",
        "package_name": "com.openai.chatgpt",
        "store_url": "https://play.google.com/store/apps/details?id=com.openai.chatgpt",
        "tasks": ["小说分析", "人物关系", "剧本改编", "分镜规划", "图片理解"],
        "handoff": "copy_prompt_and_manual_import",
    },
    {
        "id": "deepseek", "name": "DeepSeek", "category": "text",
        "package_name": "com.deepseek.chat",
        "store_url": "https://play.google.com/store/apps/details?id=com.deepseek.chat",
        "tasks": ["长篇小说分析", "剧情梳理", "剧本润色"],
        "handoff": "copy_prompt_and_manual_import",
    },
    {
        "id": "claude", "name": "Claude", "category": "text",
        "package_name": "com.anthropic.claude",
        "store_url": "https://play.google.com/store/apps/details?id=com.anthropic.claude",
        "tasks": ["长文本分析", "剧本编辑", "图片理解", "内容整理"],
        "handoff": "copy_prompt_and_manual_import",
    },
    {
        "id": "doubao", "name": "豆包", "category": "text-image",
        "package_name": "com.larus.nova",
        "store_url": "https://play.google.com/store/apps/details?id=com.larus.nova",
        "tasks": ["人物形象构思", "场景概念", "道具设计", "文本创作"],
        "handoff": "copy_prompt_and_manual_import",
    },
    {
        "id": "jimeng", "name": "即梦 AI", "category": "image-video",
        "package_name": "com.bytedance.dreamina",
        "store_url": "https://app.mi.com/details?id=com.bytedance.dreamina",
        "tasks": ["人物三视图", "场景图", "道具概念图", "图生视频"],
        "handoff": "copy_prompt_and_manual_import",
    },
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
                "id": "android-client", "name": "手机已安装的 AI 客户端",
                "description": "在 Android 原生应用中检测并启动已安装的官方 AI 客户端。",
                "configured": True,
                "capabilities": {"text": True, "image": True, "video": True, "video_editing": True},
            },
        ],
        "android_apps": ANDROID_APPS,
        "workflow": [
            "选择 AI 客户端，软件检查该官方应用是否已安装",
            "复制本次创作任务提示词，然后启动对应 AI 客户端",
            "在第三方客户端中自行登录、上传素材并操作生成或剪辑",
            "将生成结果保存到手机，再返回本软件素材库选择文件导入",
            "确认素材类型后关联到漫剧项目、分镜或独立视频剪辑项目",
        ],
        "limitations": [
            "当前支持检测和启动已核实包名的 Android 客户端；浏览器预览模式无法检测手机安装情况",
            "启动第三方客户端不等于可以自动点击、自动上传或读取其内部数据",
            "第三方客户端必须由用户自行登录和操作；不模拟登录、不绕过验证码",
            "生成结果需通过系统文件选择器手动导入；自动回传仅在第三方官方支持时才能实现",
            "应用可用地区、账号、套餐、额度和导出能力由第三方服务商决定",
        ],
    }
}
