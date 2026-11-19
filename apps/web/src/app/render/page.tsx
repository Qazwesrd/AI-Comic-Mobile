"use client";

import { useEffect,useState } from "react";
import { csrfHeaders } from "../../lib/api";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Asset={id:number;asset_type:string;title:string;file_name:string;size_bytes:number};
type Job={id:number;status:string;output_asset_id:number|null;error_message:string|null;created_at:string};

export default function RenderPage(){
  const [assets,setAssets]=useState<Asset[]>([]);
  const [selected,setSelected]=useState<number[]>([]);
  const [audio,setAudio]=useState("");
  const [duration,setDuration]=useState(3);
  const [resolution,setResolution]=useState("1280x720");
  const [jobs,setJobs]=useState<Job[]>([]);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);

  async function load(){
    try{
      const [a,j]=await Promise.all([
        fetch(`${API}/api/v1/assets`,{credentials:"include"}),
        fetch(`${API}/api/v1/renders`,{credentials:"include"})
      ]);
      if(a.ok)setAssets(await a.json());
      if(j.ok)setJobs(await j.json());
    }catch{setMessage("无法读取素材或渲染任务");}
  }
  useEffect(()=>{void load();},[]);

  function toggle(id:number){
    setSelected(items=>items.includes(id)?items.filter(x=>x!==id):[...items,id]);
  }

  async function create(){
    if(!selected.length){setMessage("请先从素材库选择至少一张图片");return;}
    setBusy(true);setMessage("正在创建合成任务…");
    try{
      const headers=await csrfHeaders();
      const r=await fetch(`${API}/api/v1/renders`,{
        method:"POST",credentials:"include",headers,
        body:JSON.stringify({
          shots:selected.map(asset_id=>({asset_id,duration_seconds:duration})),
          audio_asset_id:audio?Number(audio):null,resolution,fps:24
        })
      });
      const d=await r.json();if(!r.ok)throw new Error(d.detail||"创建任务失败");
      setMessage(d.message);setSelected([]);await load();
    }catch(e){setMessage(e instanceof Error?e.message:"渲染服务不可用");}
    finally{setBusy(false);}
  }

  async function download(assetId:number){
    const r=await fetch(`${API}/api/v1/assets/${assetId}/download`,{credentials:"include"});
    if(!r.ok){setMessage("视频下载失败");return;}
    const url=URL.createObjectURL(await r.blob());const a=document.createElement("a");a.href=url;a.download=`storyboard-preview-${assetId}.mp4`;a.click();URL.revokeObjectURL(url);
  }

  const images=assets.filter(a=>["image","character","scene","prop"].includes(a.asset_type));
  const audios=assets.filter(a=>a.asset_type==="audio");

  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">分镜合成</span></header>
    <section className="account-wrap"><div className="account-card">
      <p className="eyebrow">STORYBOARD VIDEO ASSEMBLY</p><h1>分镜静帧合成</h1>
      <p>把素材库中的分镜图片按顺序合成为 MP4 预览，可选背景音。此功能是静帧视频合成，不是 AI 动态视频生成；服务器必须安装 FFmpeg。</p>
      <div className="account-form">
        <h2>1. 选择分镜图片（按选择顺序排列）</h2>
        {images.map(asset=><label className="asset-check" key={asset.id}><input type="checkbox" checked={selected.includes(asset.id)} onChange={()=>toggle(asset.id)}/><span>{asset.title} · {asset.file_name}</span></label>)}
        <label>每张图片显示时长（秒）<input type="number" min={1} max={60} value={duration} onChange={e=>setDuration(Number(e.target.value))}/></label>
        <label>视频比例<select value={resolution} onChange={e=>setResolution(e.target.value)}><option value="1280x720">横屏 16:9（1280×720）</option><option value="1920x1080">横屏高清（1920×1080）</option><option value="1080x1920">竖屏 9:16（1080×1920）</option></select></label>
        <label>背景音（可选）<select value={audio} onChange={e=>setAudio(e.target.value)}><option value="">不添加</option>{audios.map(a=><option key={a.id} value={a.id}>{a.title}</option>)}</select></label>
        <button className="account-submit" disabled={busy||!selected.length} onClick={()=>void create()}>{busy?"正在提交…":"创建 MP4 合成任务"}</button>
      </div>
      <p className="account-message">{message}</p>
      <h2>2. 渲染任务</h2>
      <button className="account-submit" onClick={()=>void load()}>刷新任务状态</button>
      {jobs.map(job=><article className="portal-card" key={job.id}>
        <strong>任务 #{job.id} · {job.status}</strong>
        {job.error_message&&<p>{job.error_message}</p>}
        {job.output_asset_id&&<button className="account-submit" onClick={()=>void download(job.output_asset_id!)}>下载合成视频</button>}
      </article>)}
    </div></section>
  </main>;
}
