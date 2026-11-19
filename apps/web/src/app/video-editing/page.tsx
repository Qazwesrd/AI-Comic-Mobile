"use client";

import { useEffect, useState } from "react";
import { csrfHeaders } from "../../lib/api";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Project = { id:number; title:string; description:string; aspect_ratio:string; source_count:number; revision:number };
type Asset = { id:number; asset_type:string; title:string; file_name:string; size_bytes:number };
type Source = { id:number; asset_id:number; title:string; file_name:string; duration_ms:number|null; probe_status:string };
type Clip = { id:string; source_id:number; start_ms:number; end_ms:number; position_ms:number; volume:number; transition:"none"|"fade"|"dissolve" };
type Plan = { id:number; summary:string; limitations:string[]; clips:{source_id:number;start_ms:number;end_ms:number;position_ms:number;reason:string}[] };

export default function VideoEditingPage() {
  const [projects,setProjects]=useState<Project[]>([]);
  const [assets,setAssets]=useState<Asset[]>([]);
  const [selected,setSelected]=useState<Project|null>(null);
  const [sources,setSources]=useState<Source[]>([]);
  const [title,setTitle]=useState("");
  const [aspect,setAspect]=useState("16:9");
  const [assetId,setAssetId]=useState("");
  const [instruction,setInstruction]=useState("");
  const [plan,setPlan]=useState<Plan|null>(null);
  const [clips,setClips]=useState<Clip[]>([]);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [revision,setRevision]=useState(0);

  async function loadProjects() {
    const response=await fetch(API+"/api/v1/video-editing/projects",{credentials:"include"});
    if(response.ok)setProjects(await response.json());
  }
  async function loadAssets() {
    const response=await fetch(API+"/api/v1/assets?asset_type=video",{credentials:"include"});
    if(response.ok)setAssets(await response.json());
  }
  async function openProject(project:Project) {
    setSelected(project);setPlan(null);setClips([]);
    const response=await fetch(API+"/api/v1/video-editing/projects/"+project.id,{credentials:"include"});
    if(!response.ok){setMessage("读取剪辑项目失败");return;}
    const data=await response.json();setSources(data.sources||[]);setRevision(data.revision||0);
    const timeline=await fetch(API+"/api/v1/video-editing/projects/"+project.id+"/timeline",{credentials:"include"});
    if(timeline.ok){const value=await timeline.json();setRevision(value.revision||0);const videoTrack=value.tracks?.find((t:{type:string})=>t.type==="video");setClips(videoTrack?.clips||[]);}
  }
  useEffect(()=>{void loadProjects();void loadAssets();},[]);

  async function createProject() {
    if(!title.trim())return;
    setBusy(true);setMessage("");
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects",{method:"POST",credentials:"include",headers,body:JSON.stringify({title,aspect_ratio:aspect})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"创建项目失败");
      setTitle("");await loadProjects();await openProject({...data,source_count:0,revision:0});
      setMessage("独立剪辑项目已创建。");
    } catch(e){setMessage(e instanceof Error?e.message:"创建失败");}
    finally{setBusy(false);}
  }
  async function attachSource() {
    if(!selected||!assetId)return;
    setBusy(true);
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects/"+selected.id+"/sources",{method:"POST",credentials:"include",headers,body:JSON.stringify({asset_id:Number(assetId)})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"添加视频失败");
      await openProject(selected);setMessage("视频素材已添加到剪辑项目。");
    }catch(e){setMessage(e instanceof Error?e.message:"添加失败");}
    finally{setBusy(false);}
  }
  async function createPlan() {
    if(!selected||instruction.trim().length<3)return;
    setBusy(true);setPlan(null);
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects/"+selected.id+"/ai-plan",{method:"POST",credentials:"include",headers,body:JSON.stringify({instruction})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"AI剪辑方案生成失败");
      setPlan(data);setMessage("AI建议已生成，请检查时间码后再应用到时间线。");
    }catch(e){setMessage(e instanceof Error?e.message:"AI剪辑方案生成失败");}
    finally{setBusy(false);}
  }
  function addClip(sourceId:number) {
    setClips(items=>[...items,{id:crypto.randomUUID(),source_id:sourceId,start_ms:0,end_ms:5000,position_ms:items.length?Math.max(...items.map(x=>x.position_ms+x.end_ms-x.start_ms)):0,volume:1,transition:"none"}]);
  }
  async function saveTimeline() {
    if(!selected)return;
    setBusy(true);
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects/"+selected.id+"/timeline",{method:"PUT",credentials:"include",headers,body:JSON.stringify({expected_revision:revision,tracks:[{id:"video-main",type:"video",clips}]})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail?.message||data.detail||"保存时间线失败");
      setRevision(data.revision);setMessage("时间线版本 "+data.revision+" 已保存。");
      await loadProjects();
    }catch(e){setMessage(e instanceof Error?e.message:"保存失败");}
    finally{setBusy(false);}
  }
  function applyPlan() {
    if(!plan)return;
    const sourceIds=new Set(sources.map(s=>s.id));
    const next=plan.clips.map(c=>({id:crypto.randomUUID(),source_id:c.source_id,start_ms:c.start_ms,end_ms:c.end_ms,position_ms:c.position_ms,volume:1,transition:"none" as const}));
    if(next.some(c=>!sourceIds.has(c.source_id))){setMessage("AI方案包含当前项目不存在的素材，不能应用");return;}
    setClips(next);setMessage("已载入AI建议。请检查并保存时间线。");
  }

  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">AI VIDEO EDITOR</span></header>
    <section className="account-wrap" style={{width:"min(900px,100%)"}}>
      <a className="account-back" href="/">← 返回创作中心</a>
      <div className="account-card">
        <p className="eyebrow">INDEPENDENT CREATIVE WORKSPACE</p>
        <h1>AI 视频剪辑</h1>
        <p>与AI漫剧并列的独立剪辑工具。上传已有视频，用文字描述剪辑目标；AI生成的建议可审核、修改后再保存。原始视频不会被覆盖。</p>
        <div className="account-form">
          <label>新建剪辑项目<input value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：旅行视频精选"/></label>
          <label>目标画幅<select value={aspect} onChange={e=>setAspect(e.target.value)}><option>16:9</option><option>9:16</option><option>1:1</option><option>2.35:1</option></select></label>
          <button className="account-submit" disabled={busy||!title.trim()} onClick={()=>void createProject()}>创建独立剪辑项目</button>
        </div>
        <h2>我的剪辑项目</h2>
        {projects.length===0&&<p>还没有剪辑项目。创建一个项目即可开始。</p>}
        <div className="module-grid">
          {projects.map(p=><button key={p.id} className="module-card" style={{textAlign:"left",color:"inherit",cursor:"pointer"}} onClick={()=>void openProject(p)}>
            <span className="module-number">#{p.id}</span><div className="module-content"><span className="module-status">{p.aspect_ratio} · {p.source_count} 个视频</span><h3>{p.title}</h3><p>时间线版本 {p.revision}</p></div>
          </button>)}
        </div>
        {selected&&<div style={{marginTop:30}}>
          <h2>{selected.title} · 剪辑工作区</h2>
          <div className="account-form">
            <label>从素材库添加视频<select value={assetId} onChange={e=>setAssetId(e.target.value)}><option value="">选择已有视频素材</option>{assets.map(a=><option key={a.id} value={a.id}>{a.title} · {a.file_name}</option>)}</select></label>
            <button className="account-submit" disabled={busy||!assetId} onClick={()=>void attachSource()}>添加到当前项目</button>
          </div>
          <h3>项目视频素材</h3>
          {sources.map(source=><article className="portal-card" key={source.id}><strong>{source.title}</strong><p>{source.file_name} · 媒体探测：{source.probe_status}{source.duration_ms?" · "+(source.duration_ms/1000).toFixed(1)+"秒":" · 时长尚未探测"}</p><button className="account-submit" onClick={()=>addClip(source.id)}>添加5秒片段到时间线</button></article>)}
          <h3>AI文字剪辑指令</h3>
          <div className="account-form">
            <label>告诉AI你想怎样剪辑<textarea rows={4} value={instruction} onChange={e=>setInstruction(e.target.value)} placeholder="例如：保留节奏紧凑的部分，删除停顿，按时间顺序组合，输出竖屏短视频。"/></label>
            <button className="account-submit" disabled={busy||sources.length===0||instruction.trim().length<3} onClick={()=>void createPlan()}>{busy?"处理中…":"生成AI剪辑建议"}</button>
          </div>
          {plan&&<article className="portal-card"><strong>AI建议（草稿）</strong><p>{plan.summary}</p>{plan.limitations.map((x,i)=><p key={i}>注意：{x}</p>)}<p>建议片段：{plan.clips.length}</p><button className="account-submit" disabled={!plan.clips.length} onClick={applyPlan}>应用到时间线</button></article>}
          <h3>时间线 · 版本 {revision}</h3>
          <p>当前提供基础视频轨道片段编辑；高级多轨、波形、转场预览与正式渲染将在后续阶段继续完善。</p>
          {clips.map((clip,index)=><article className="portal-card" key={clip.id}>
            <strong>片段 {index+1} · 源素材 #{clip.source_id}</strong>
            <div className="account-form">
              <label>源视频开始时间（毫秒）<input type="number" min="0" value={clip.start_ms} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,start_ms:Number(e.target.value)}:x))}/></label>
              <label>源视频结束时间（毫秒）<input type="number" min="1" value={clip.end_ms} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,end_ms:Number(e.target.value)}:x))}/></label>
              <label>时间线位置（毫秒）<input type="number" min="0" value={clip.position_ms} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,position_ms:Number(e.target.value)}:x))}/></label>
              <button className="account-submit" onClick={()=>setClips(items=>items.filter(x=>x.id!==clip.id))}>移除此片段</button>
            </div>
          </article>)}
          <button className="account-submit" disabled={busy||clips.length===0} onClick={()=>void saveTimeline()}>保存时间线版本</button>
        </div>}
        <p className="account-message">{message}</p>
        <p style={{fontSize:11,color:"#8c90b2"}}>当前阶段已实现项目/素材关联、基础时间线版本保存与AI结构化剪辑计划入口。视频画面理解、自动镜头识别、媒体时长探测和成片渲染尚未接通；没有配置AI服务时，AI建议不可用。</p>
      </div>
    </section>
  </main>;
}
