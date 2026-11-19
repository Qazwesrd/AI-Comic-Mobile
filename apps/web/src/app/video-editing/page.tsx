"use client";

import { useEffect, useState } from "react";
import { csrfHeaders } from "../../lib/api";
import AIToolHandoff from "../../components/ai-tool-handoff";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Project = { id:number; title:string; description:string; aspect_ratio:string; source_count:number; revision:number };
type Asset = { id:number; asset_type:string; title:string; file_name:string; size_bytes:number };
type Source = { id:number; asset_id:number; title:string; file_name:string; duration_ms:number|null; probe_status:string };
type Clip = { id:string; source_id:number; start_ms:number; end_ms:number; position_ms:number; volume:number; transition:"none"|"fade"|"dissolve" };
type Subtitle = { id:string; start_ms:number; end_ms:number; text:string };
type Plan = { id:number; summary:string; limitations:string[]; clips:{source_id:number;start_ms:number;end_ms:number;position_ms:number;reason:string}[] };

export default function VideoEditingPage() {
  const [projects,setProjects]=useState<Project[]>([]);
  const [assets,setAssets]=useState<Asset[]>([]);
  const [audioAssets,setAudioAssets]=useState<Asset[]>([]);
  const [musicAssetId,setMusicAssetId]=useState("");
  const [exportAssetId,setExportAssetId]=useState<number|null>(null);
  const [selected,setSelected]=useState<Project|null>(null);
  const [sources,setSources]=useState<Source[]>([]);
  const [title,setTitle]=useState("");
  const [aspect,setAspect]=useState("16:9");
  const [assetId,setAssetId]=useState("");
  const [instruction,setInstruction]=useState("");
  const [plan,setPlan]=useState<Plan|null>(null);
  const [clips,setClips]=useState<Clip[]>([]);
  const [subtitles,setSubtitles]=useState<Subtitle[]>([]);
  const [subtitleText,setSubtitleText]=useState("");
  const [subtitleStart,setSubtitleStart]=useState(0);
  const [subtitleEnd,setSubtitleEnd]=useState(3000);
  const [exportSubtitleAssetId,setExportSubtitleAssetId]=useState<number|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [revision,setRevision]=useState(0);
  const [keyframes,setKeyframes]=useState<Record<number,{asset_id:number;timestamp_ms:number;file_name:string}[]>>({});

  async function loadProjects() {
    const response=await fetch(API+"/api/v1/video-editing/projects",{credentials:"include"});
    if(response.ok)setProjects(await response.json());
  }
  async function loadAssets() {
    const [videoResponse,audioResponse]=await Promise.all([fetch(API+"/api/v1/assets?asset_type=video",{credentials:"include"}),fetch(API+"/api/v1/assets?asset_type=audio",{credentials:"include"})]);
    if(videoResponse.ok)setAssets(await videoResponse.json());
    if(audioResponse.ok)setAudioAssets(await audioResponse.json());
  }
  async function openProject(project:Project) {
    setSelected(project);setPlan(null);setClips([]);setSubtitles([]);
    const response=await fetch(API+"/api/v1/video-editing/projects/"+project.id,{credentials:"include"});
    if(!response.ok){setMessage("读取剪辑项目失败");return;}
    const data=await response.json();setSources(data.sources||[]);setRevision(data.revision||0);
    const timeline=await fetch(API+"/api/v1/video-editing/projects/"+project.id+"/timeline",{credentials:"include"});
    if(timeline.ok){const value=await timeline.json();setRevision(value.revision||0);const videoTrack=value.tracks?.find((t:{type:string})=>t.type==="video");const subtitleTrack=value.tracks?.find((t:{type:string})=>t.type==="subtitle");setClips(videoTrack?.clips||[]);setSubtitles(subtitleTrack?.clips||[]);}
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
  async function extractKeyframes(sourceId:number) {
    if(!selected)return;
    setBusy(true);setMessage("");
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects/"+selected.id+"/sources/"+sourceId+"/keyframes?interval_seconds=5",{method:"POST",credentials:"include",headers});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"关键帧提取失败");
      setKeyframes(items=>({...items,[sourceId]:data.frames||[]}));
      await loadAssets();
      setMessage("已提取 "+data.count+" 张关键帧。它们已保存为待审核图片，可交给支持图片理解的 AI 客户端分析。");
    }catch(e){setMessage(e instanceof Error?e.message:"关键帧提取失败");}
    finally{setBusy(false);}
  }
  async function exportVideo() {
    if(!selected)return;
    setBusy(true);setMessage("");
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects/"+selected.id+"/export",{method:"POST",credentials:"include",headers,body:JSON.stringify({resolution:selected.aspect_ratio==="9:16"?"1080x1920":selected.aspect_ratio==="1:1"?"1080x1080":"1920x1080",fps:30,music_asset_id:musicAssetId?Number(musicAssetId):null})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"视频导出失败");
      setExportAssetId(data.asset_id);
      setExportSubtitleAssetId(data.subtitle_asset_id ?? null);
      await loadAssets();
      setMessage("视频导出完成，成片已保存到素材库，素材编号："+data.asset_id+"。");
    }catch(e){setMessage(e instanceof Error?e.message:"视频导出失败");}
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
  function addSubtitle() {
    if(!subtitleText.trim()||subtitleEnd<=subtitleStart)return;
    setSubtitles(items=>[...items,{id:crypto.randomUUID(),start_ms:subtitleStart,end_ms:subtitleEnd,text:subtitleText.trim()}]);
    setSubtitleText("");
  }
  async function saveTimeline() {
    if(!selected)return;
    setBusy(true);
    try {
      const headers=await csrfHeaders();
      const response=await fetch(API+"/api/v1/video-editing/projects/"+selected.id+"/timeline",{method:"PUT",credentials:"include",headers,body:JSON.stringify({expected_revision:revision,tracks:[{id:"video-main",type:"video",clips},{id:"subtitle-main",type:"subtitle",clips:subtitles.map(item=>({...item,source_id:null,position_ms:item.start_ms,volume:1,transition:"none"}))}]})});
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
          {sources.map(source=><article className="portal-card" key={source.id}><strong>{source.title}</strong><p>{source.file_name} · 媒体探测：{source.probe_status}{source.duration_ms?" · "+(source.duration_ms/1000).toFixed(1)+"秒":" · 时长尚未探测"}</p><button className="account-submit" onClick={()=>addClip(source.id)}>添加5秒片段到时间线</button><button className="account-submit" disabled={busy||!source.duration_ms} onClick={()=>void extractKeyframes(source.id)}>提取关键帧（每5秒）</button>{(keyframes[source.id]||[]).map(frame=><p key={frame.asset_id}>关键帧 {Math.round(frame.timestamp_ms/1000)}秒 · 素材 #{frame.asset_id} · <a href={API+"/api/v1/assets/"+frame.asset_id+"/download"} target="_blank" rel="noreferrer">查看图片</a></p>)}</article>)}
          <h3>背景音乐</h3>
          <div className="account-form"><label>选择背景音乐（可选）<select value={musicAssetId} onChange={e=>setMusicAssetId(e.target.value)}><option value="">不添加背景音乐</option>{audioAssets.map(a=><option key={a.id} value={a.id}>{a.title} · {a.file_name}</option>)}</select></label></div>
          <h3>AI文字剪辑指令</h3>
          <div className="account-form">
            <label>告诉AI你想怎样剪辑<textarea rows={4} value={instruction} onChange={e=>setInstruction(e.target.value)} placeholder="例如：保留节奏紧凑的部分，删除停顿，按时间顺序组合，输出竖屏短视频。"/></label>
            <button className="account-submit" disabled={busy||sources.length===0||instruction.trim().length<3} onClick={()=>void createPlan()}>{busy?"处理中…":"生成AI剪辑建议"}</button>
          </div>
          <AIToolHandoff projectTitle={selected.title} aspectRatio={selected.aspect_ratio} instruction={instruction} sources={sources.map(source=>({id:source.id,file_name:source.file_name,duration_ms:source.duration_ms,probe_status:source.probe_status}))} keyframes={sources.flatMap(source=>(keyframes[source.id]||[]).map(frame=>({...frame,source_id:source.id})))} />
          {plan&&<article className="portal-card"><strong>AI建议（草稿）</strong><p>{plan.summary}</p>{plan.limitations.map((x,i)=><p key={i}>注意：{x}</p>)}<p>建议片段：{plan.clips.length}</p><button className="account-submit" disabled={!plan.clips.length} onClick={applyPlan}>应用到时间线</button></article>}
          <h3>字幕轨道</h3>
          <div className="account-form">
            <label>字幕内容<textarea rows={2} value={subtitleText} onChange={e=>setSubtitleText(e.target.value)} placeholder="输入要显示的字幕文字"/></label>
            <label>字幕开始时间（毫秒）<input type="number" min="0" value={subtitleStart} onChange={e=>setSubtitleStart(Number(e.target.value))}/></label>
            <label>字幕结束时间（毫秒）<input type="number" min="1" value={subtitleEnd} onChange={e=>setSubtitleEnd(Number(e.target.value))}/></label>
            <button className="account-submit" disabled={!subtitleText.trim()||subtitleEnd<=subtitleStart} onClick={addSubtitle}>添加字幕片段</button>
          </div>
          {subtitles.map(item=><article className="portal-card" key={item.id}><strong>{item.text}</strong><p>{item.start_ms}ms – {item.end_ms}ms</p><button className="account-submit" onClick={()=>setSubtitles(items=>items.filter(x=>x.id!==item.id))}>删除字幕</button></article>)}
          <h3>时间线 · 版本 {revision}</h3>
          <p>可提取关键帧交给支持图片理解的 AI 客户端；视频轨道可编辑并导出 MP4，支持可选背景音乐接口。</p>
          {clips.map((clip,index)=><article className="portal-card" key={clip.id}>
            <strong>片段 {index+1} · 源素材 #{clip.source_id}</strong>
            <div className="account-form">
              <label>源视频开始时间（毫秒）<input type="number" min="0" value={clip.start_ms} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,start_ms:Number(e.target.value)}:x))}/></label>
              <label>源视频结束时间（毫秒）<input type="number" min="1" value={clip.end_ms} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,end_ms:Number(e.target.value)}:x))}/></label>
              <label>时间线位置（毫秒）<input type="number" min="0" value={clip.position_ms} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,position_ms:Number(e.target.value)}:x))}/></label>
              <label>片段淡入淡出<select value={clip.transition==="fade"?"fade":"none"} onChange={e=>setClips(items=>items.map(x=>x.id===clip.id?{...x,transition:e.target.value as "none"|"fade"}:x))}><option value="none">无</option><option value="fade">淡入淡出</option></select></label>
              <button className="account-submit" onClick={()=>setClips(items=>items.filter(x=>x.id!==clip.id))}>移除此片段</button>
            </div>
          </article>)}
          <button className="account-submit" disabled={busy||clips.length===0} onClick={()=>void saveTimeline()}>保存时间线版本</button><button className="account-submit" disabled={busy||clips.length===0} onClick={()=>void exportVideo()}>{busy?"处理中…":"导出 MP4 成片"}</button>
          {exportAssetId!==null&&<article className="portal-card"><strong>最近导出的成片</strong><p>素材编号：{exportAssetId}</p><video controls playsInline style={{width:"100%",maxHeight:360}} src={API+"/api/v1/assets/"+exportAssetId+"/download"} /><a href={API+"/api/v1/assets/"+exportAssetId+"/download"}>下载 MP4 成片</a>{exportSubtitleAssetId!==null&&<p><a href={API+"/api/v1/assets/"+exportSubtitleAssetId+"/download"}>下载 SRT 字幕文件</a></p>}</article>}
        </div>}
        <p className="account-message">{message}</p>
        <p style={{fontSize:11,color:"#8c90b2"}}>关键帧提取仅负责抽帧，不代表软件已自动理解画面；AI 视觉分析仍需通过支持图片理解的客户端或已配置视觉模型完成。MP4 导出由服务端 FFmpeg 执行，原始视频不会覆盖。</p>
      </div>
    </section>
  </main>;
}
