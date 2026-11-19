"use client";

import { useEffect, useMemo, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { registerPlugin } from "@capacitor/core";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Tool = {
  id: string;
  name: string;
  category: string;
  package_name: string;
  store_url: string;
  web_url: string;
  tasks: string[];
};

type AIAppLauncherPlugin = { isInstalled(options: { packageName: string }): Promise<{ installed: boolean }>; launch(options: { packageName: string }): Promise<void> };
const AIAppLauncher = registerPlugin<AIAppLauncherPlugin>("AIAppLauncher");

type Props = {
  projectTitle: string;
  aspectRatio: string;
  instruction: string;
  sources: { id: number; file_name: string; duration_ms: number | null; probe_status: string }[];
  keyframes?: { source_id: number; asset_id: number; timestamp_ms: number; file_name: string }[];
};

export default function AIToolHandoff({ projectTitle, aspectRatio, instruction, sources, keyframes = [] }: Props) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [selectedId, setSelectedId] = useState("chatgpt");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const android = Capacitor.getPlatform() === "android";

  useEffect(() => {
    let active = true;
    fetch(API + "/api/v1/ai-tools", { credentials: "include" })
      .then(async response => {
        if (!response.ok) throw new Error("请先登录，再使用 AI 客户端交接。");
        const data = await response.json();
        if (active) setTools((data.android_apps || []).filter((tool: Tool) =>
          tool.category === "video-editing" || tool.category === "text" || tool.category === "text-image"
        ));
      })
      .catch(error => { if (active) setMessage(error instanceof Error ? error.message : "读取 AI 客户端失败"); });
    return () => { active = false; };
  }, []);

  const selected = useMemo(() => tools.find(tool => tool.id === selectedId) || tools[0], [tools, selectedId]);
  const prompt = useMemo(() => {
    const frameLines = keyframes.map(frame => `源素材 #${frame.source_id} 的关键帧：素材 #${frame.asset_id}，时间点 ${(frame.timestamp_ms / 1000).toFixed(1)} 秒（请用户从素材库下载并上传此图片）。`).join("
");
    const sourceLines = sources.map((source, index) =>
      `${index + 1}. 素材编号 ${source.id}：${source.file_name}；时长：${source.duration_ms === null ? "尚未探测" : (source.duration_ms / 1000).toFixed(2) + "秒"}；媒体探测：${source.probe_status}`
    ).join("
");
    return [
      "你是专业短视频剪辑导演和时间线规划师，请根据以下资料帮助我完成视频剪辑。",
      `项目：${projectTitle}`,
      `目标画幅：${aspectRatio}`,
      `剪辑要求：${instruction || "请先根据素材给出剪辑思路，并向我询问具体风格。"}`,
      "素材清单：",
      sourceLines || "尚未添加视频素材。",
      "已提取关键帧：",
      frameLines || "尚未提取关键帧；如需分析画面，请先提取并上传关键帧图片。",
      "",
      "请遵守：不要编造没有提供的画面内容或时间码；如果无法直接读取视频，请明确告诉我需要上传哪些视频或关键帧。",
      "请优先输出可执行的剪辑清单，包含素材编号、入点、出点、时间线位置、镜头理由、字幕/音效建议。",
      "时间码必须在已知素材时长范围内；无法确定时标记为待人工确认。",
      "如果你能直接剪辑视频，请说明支持的输入格式、输出格式和限制；不要声称已经导出文件，除非实际提供了文件。",
      "请用简体中文回答，保持原视频核心内容，不要覆盖原始素材。"
    ].join("
");
  }, [projectTitle, aspectRatio, instruction, sources, keyframes]);

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(prompt);
      setMessage("剪辑任务提示词已复制。打开 AI 后粘贴，并按客户端能力上传视频。");
    } catch {
      setMessage("复制失败，请检查手机剪贴板权限。");
    }
  }

  async function openClient() {
    if (!selected) return;
    setBusy(true);
    try {
      if (!android) {
        window.open(selected.web_url, "_blank", "noopener,noreferrer");
        setMessage("已打开网页版 AI。请粘贴任务提示词并按需上传视频。");
        return;
      }
      const result = await AppLauncher.canOpenUrl({ url: selected.package_name });
      if (!result.value) {
        window.open(selected.store_url, "_blank", "noopener,noreferrer");
        setMessage(`未检测到 ${selected.name} 客户端，已打开官方安装页面。`);
        return;
      }
      await AIAppLauncher.launch({ packageName: selected.package_name });
      setMessage(`已请求启动 ${selected.name}。请在客户端中粘贴提示词并自行选择视频素材。`);
    } catch {
      setMessage(`无法启动 ${selected.name}，可以改用网页版。`);
    } finally {
      setBusy(false);
    }
  }

  function openWeb() {
    if (!selected) return;
    window.open(selected.web_url, "_blank", "noopener,noreferrer");
    setMessage("已打开网页版 AI。请粘贴任务提示词并按需上传视频。");
  }

  return <section className="portal-card" aria-label="AI 客户端剪辑交接">
    <h3>使用 AI 客户端 / 网页版协助剪辑</h3>
    <p>与 AI 漫剧共用同一套 AI 工具中心。先提取关键帧并复制本项目剪辑任务，再打开客户端或网页版；视频/图片上传、分析和结果保存由你在第三方服务中确认操作。</p>
    <div className="account-form">
      <label>选择 AI 工具
        <select value={selected?.id || selectedId} onChange={event => setSelectedId(event.target.value)}>
          {tools.map(tool => <option key={tool.id} value={tool.id}>{tool.name}{tool.category === "video-editing" ? "（视频剪辑）" : "（分析/规划）"}</option>)}
        </select>
      </label>
      <button className="account-submit" type="button" disabled={!selected} onClick={() => void copyPrompt()}>复制本项目剪辑提示词</button>
      <button className="account-submit" type="button" disabled={!selected || busy} onClick={() => void openClient()}>{busy ? "正在打开…" : android ? "启动手机 AI 客户端" : "打开 AI 网页版"}</button>
      {android && <button className="account-submit" type="button" disabled={!selected} onClick={openWeb}>改用网页版</button>}
    </div>
    {message && <p className="account-message" role="status">{message}</p>}
    <p style={{fontSize:11,color:"#8c90b2"}}>注意：软件只检测并启动已安装的客户端，不会自动上传视频、读取聊天内容或控制第三方界面。可将关键帧图片下载后手动上传；完成后将结果或文件手动导入素材库。</p>
  </section>;
}
