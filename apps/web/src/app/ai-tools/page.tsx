"use client";

import { useEffect, useMemo, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { AppLauncher } from "@capacitor/app-launcher";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Tool = { id:string; name:string; category:string; package_name:string; store_url:string; tasks:string[]; handoff:string };
type Data = { modes:{id:string;name:string;description:string;configured:boolean;configuration_note?:string;capabilities:Record<string,boolean>}[]; android_apps:Tool[]; workflow:string[]; limitations:string[] };

const categoryNames:Record<string,string> = {
  text:"文本创作与分析", "text-image":"文本与图片理解", "image-video":"图片与视频创作"
};

const taskPrompt = (tool:Tool) =>
  `我正在使用 AI 漫剧手机版制作漫剧/剪辑视频。请协助完成：${tool.tasks.join("、")}。请输出结构清晰、方便导入创作软件的结果；如涉及人物、场景、道具，请分别标注名称、描述和关联剧情。不要擅自改变原故事核心情节。`;

export default function AIToolsPage() {
  const [data,setData]=useState<Data|null>(null);
  const [error,setError]=useState("");
  const [filter,setFilter]=useState("all");
  const [installed,setInstalled]=useState<Record<string,boolean>>({});
  const [checking,setChecking]=useState(false);
  const [notice,setNotice]=useState("");

  useEffect(()=>{
    fetch(API+"/api/v1/ai-tools",{credentials:"include"}).then(async r=>{
      if(!r.ok) throw new Error(r.status===401?"请先登录后查看AI工具。":"读取AI工具列表失败。");
      setData(await r.json());
    }).catch(e=>setError(e instanceof Error?e.message:"读取失败"));
  },[]);

  useEffect(()=>{
    if(!data || Capacitor.getPlatform()!=="android") return;
    let active=true;
    setChecking(true);
    Promise.all(data.android_apps.map(async app=>{
      try {
        const result=await AppLauncher.canOpenUrl({url:app.package_name});
        return [app.id,result.value] as const;
      } catch { return [app.id,false] as const; }
    })).then(results=>{
      if(active) setInstalled(Object.fromEntries(results));
    }).finally(()=>{ if(active) setChecking(false); });
    return ()=>{active=false;};
  },[data]);

  const tools=useMemo(()=>data?.android_apps.filter(t=>filter==="all"||t.category===filter)||[],[data,filter]);
  const isAndroid=Capacitor.getPlatform()==="android";

  async function launch(tool:Tool) {
    setNotice("");
    if(!isAndroid) {
      window.open(tool.store_url,"_blank","noopener,noreferrer");
      setNotice("当前不是安卓版运行环境，已打开该应用的官方商店页面。");
      return;
    }
    try {
      const canOpen=await AppLauncher.canOpenUrl({url:tool.package_name});
      if(!canOpen.value) {
        window.open(tool.store_url,"_blank","noopener,noreferrer");
        setNotice(`未检测到已安装的${tool.name}，已打开官方应用商店页面。`);
        return;
      }
      await AppLauncher.openUrl({url:tool.package_name});
    } catch {
      setNotice(`暂时无法启动${tool.name}。请确认已安装官方客户端后重试。`);
    }
  }

  async function copyPrompt(tool:Tool) {
    try {
      await navigator.clipboard.writeText(taskPrompt(tool));
      setNotice(`已复制${tool.name}任务提示词。启动客户端后可直接粘贴使用。`);
    } catch {
      setNotice("复制失败，请检查系统剪贴板权限。");
    }
  }

  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">ANDROID AI CENTER</span></header>
    <section className="account-wrap" style={{width:"min(960px,100%)"}}>
      <a className="account-back" href="/">← 返回创作中心</a>
      <div className="account-card">
        <p className="eyebrow">ANDROID · DUAL AI WORKFLOW</p><h1>AI 工具中心</h1>
        <p>两种方式并行：软件内置 AI API，或调用手机上已经安装的 AI 客户端。AI 漫剧与 AI 视频剪辑共用此工具中心。</p>
        {error&&<p className="account-message">{error}</p>}
        {notice&&<p className="account-message" role="status">{notice}</p>}
        <h2>AI 使用模式</h2>
        {data?.modes.map(mode=><article className="portal-card" key={mode.id}>
          <strong>{mode.name}</strong><p>{mode.description}</p>
          {mode.id==="built-in"&&<><p>文本模型：{mode.capabilities.text?"已配置":"未配置"} · 图片模型：{mode.capabilities.image?"已配置":"未配置"} · 配音模型：{mode.capabilities.audio?"已配置":"未配置"}</p><p>{mode.configuration_note}</p></>}
          {mode.id==="android-client"&&<p>安卓版可检测并启动已核实的客户端。第三方生成结果需要保存到手机后，再通过素材库导入。</p>}
        </article>)}
        <h2>手机 AI 客户端</h2>
        <div className="account-form"><label>工具分类<select value={filter} onChange={e=>setFilter(e.target.value)}>
          <option value="all">全部工具</option><option value="text">文本创作与分析</option><option value="text-image">文本与图片理解</option><option value="image-video">图片与视频创作</option>
        </select></label></div>
        <p className="account-message">{isAndroid?(checking?"正在检查手机已安装的 AI 客户端…":"已根据 Android 系统应用可见性规则检查客户端。"):"请在安卓版 APK 中使用客户端检测和启动功能。"}</p>
        <div className="module-grid">{tools.map(tool=><article className="module-card" key={tool.id}>
          <span className="module-number">AI</span><div className="module-content">
            <span className="module-status">{categoryNames[tool.category]||tool.category}</span><h3>{tool.name}</h3><p>{tool.tasks.join(" · ")}</p>
            {isAndroid&&<p>{checking?"检测中…":installed[tool.id]?"已检测到客户端":"未检测到客户端"}</p>}
            <button className="account-submit" type="button" onClick={()=>copyPrompt(tool)}>复制任务提示词</button>
            <button className="account-submit" type="button" onClick={()=>launch(tool)}>{isAndroid?"启动手机客户端":"查看官方安装入口"} ↗</button>
          </div>
        </article>)}</div>
        <h2>素材交接流程</h2><ol>{data?.workflow.map((item,i)=><li key={i}>{item}</li>)}</ol>
        <h2>使用边界</h2><ul>{data?.limitations.map((item,i)=><li key={i}>{item}</li>)}</ul>
        <p className="account-message">注意：本软件不会接管第三方 AI 客户端。生成完成后，请在第三方应用中保存图片、视频、音频或文本，再回到「素材库」导入。之后可以关联到漫剧或视频剪辑项目。</p>
      </div>
    </section>
  </main>;
}
