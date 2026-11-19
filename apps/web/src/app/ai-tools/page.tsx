"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Tool = { id:string; name:string; category:string; url:string; tasks:string[] };
type Data = { modes:{id:string;name:string;description:string;configured:boolean;configuration_note?:string;capabilities:Record<string,boolean>}[]; web_tools:Tool[]; workflow:string[]; limitations:string[] };

const categoryNames:Record<string,string> = {
  text:"文本创作与分析", "text-image":"文本与图片理解", "image-video":"图片与视频", video:"视频生成", "video-editing":"AI视频剪辑"
};

export default function AIToolsPage() {
  const [data,setData]=useState<Data|null>(null);
  const [error,setError]=useState("");
  const [filter,setFilter]=useState("all");
  useEffect(()=>{
    fetch(API+"/api/v1/ai-tools",{credentials:"include"}).then(async r=>{
      if(!r.ok) throw new Error(r.status===401?"请先登录后查看AI工具。":"读取AI工具列表失败。");
      setData(await r.json());
    }).catch(e=>setError(e instanceof Error?e.message:"读取失败"));
  },[]);
  const tools=data?.web_tools.filter(t=>filter==="all"||t.category===filter||(filter==="video-editing"&&t.category==="video"))||[];
  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">AI TOOL CENTER</span></header>
    <section className="account-wrap" style={{width:"min(960px,100%)"}}>
      <a className="account-back" href="/">← 返回创作中心</a>
      <div className="account-card">
        <p className="eyebrow">DUAL AI WORKFLOW</p><h1>AI 工具中心</h1>
        <p>软件内置 AI 接口和网页版 AI 工具两种方式并存。漫剧创作与 AI 视频剪辑都可以选择适合自己的工具。</p>
        {error&&<p className="account-message">{error}</p>}
        <h2>两种使用方式</h2>
        {data?.modes.map(mode=><article className="portal-card" key={mode.id}>
          <strong>{mode.name}</strong><p>{mode.description}</p>
          {mode.id==="built-in"&&<><p>文本模型：{mode.capabilities.text?"已配置":"未配置"} · 图片模型：{mode.capabilities.image?"已配置":"未配置"} · 配音模型：{mode.capabilities.audio?"已配置":"未配置"}</p><p>{mode.configuration_note}</p></>}
          {mode.id==="web"&&<p>网页版模式无需在本软件填写 API Key，但需要用户拥有对应网站账号，并手动下载、导入结果。</p>}
        </article>)}
        <h2>网页版 AI 工具</h2>
        <div className="account-form"><label>工具分类<select value={filter} onChange={e=>setFilter(e.target.value)}>
          <option value="all">全部工具</option><option value="text">文本创作与分析</option><option value="image-video">图片与视频</option><option value="video">视频生成</option><option value="video-editing">AI视频剪辑</option>
        </select></label></div>
        <div className="module-grid">{tools.map(tool=><article className="module-card" key={tool.id}>
          <span className="module-number">AI</span><div className="module-content"><span className="module-status">{categoryNames[tool.category]||tool.category}</span><h3>{tool.name}</h3><p>{tool.tasks.join(" · ")}</p><a className="account-submit" href={tool.url} target="_blank" rel="noopener noreferrer">打开官方网站 ↗</a></div>
        </article>)}</div>
        <h2>网页版工具使用流程</h2><ol>{data?.workflow.map((item,i)=><li key={i}>{item}</li>)}</ol>
        <h2>使用边界</h2><ul>{data?.limitations.map((item,i)=><li key={i}>{item}</li>)}</ul>
        <p className="account-message">网页版生成的内容不会自动同步到软件。下载后请进入素材库上传，再关联到相应创作项目。</p>
      </div>
    </section>
  </main>;
}
