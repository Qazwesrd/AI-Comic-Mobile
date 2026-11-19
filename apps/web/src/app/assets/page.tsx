"use client";

import { getApiBaseUrl } from "../../lib/api-base";

import { ChangeEvent, useEffect, useState } from "react";
import { csrfHeaders } from "../../lib/api";
import { AndroidSharedFile, consumeAndroidSharedFiles, readAndroidSharedChunk } from "../../lib/android-share-receiver";

const API = getApiBaseUrl();
const CHUNK_SIZE = 8 * 1024 * 1024;
type AssetType = "video" | "image" | "character" | "scene" | "prop" | "reference" | "audio" | "subtitle" | "text";
type Asset = { id:number; project_id:number|null; asset_type:AssetType; title:string; file_name:string; mime_type:string; size_bytes:number; approved:boolean };
type Project = { id:number; title:string; status:string };
type UploadableFile = File | AndroidSharedFile;
type QueuedFile = { file:UploadableFile; assetType:AssetType };

const typeLabels:Record<AssetType,string> = {
  video:"视频", image:"图片", character:"人物参考图", scene:"场景参考图",
  prop:"道具参考图", reference:"参考资料", audio:"音频", subtitle:"字幕", text:"文本资料"
};

function guessType(file:Pick<UploadableFile, "name" | "type">):AssetType {
  const name=file.name.toLowerCase();
  if (/\\.(srt|vtt)$/.test(name)) return "subtitle";
  if (/\\.(txt|md|markdown|json|csv)$/.test(name)) return "text";
  if (/\\.pdf$/.test(name)) return "reference";
  if (file.type.startsWith("video/") || /\\.(mp4|mov|webm|m4v)$/.test(name)) return "video";
  if (file.type.startsWith("audio/") || /\\.(mp3|wav|m4a|aac|ogg)$/.test(name)) return "audio";
  if (file.type.startsWith("image/") || /\\.(jpg|jpeg|png|webp|gif)$/.test(name)) return "image";
  return "reference";
}

export default function AssetsPage() {
  const [queue,setQueue]=useState<QueuedFile[]>([]);
  const [items,setItems]=useState<Asset[]>([]);
  const [projects,setProjects]=useState<Project[]>([]);
  const [projectId,setProjectId]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [progress,setProgress]=useState(0);
  const [filter,setFilter]=useState("all");

  async function load() {
    try {
      const [assetResponse,projectResponse]=await Promise.all([
        fetch(`${API}/api/v1/assets`,{credentials:"include"}),
        fetch(`${API}/api/v1/projects`,{credentials:"include"})
      ]);
      if(assetResponse.ok)setItems(await assetResponse.json());
      if(projectResponse.ok)setProjects(await projectResponse.json());
    } catch { setMessage("无法读取素材库，请检查登录和网络"); }
  }
  useEffect(()=>{
    void load();
    const receiveSharedFiles = async () => {
      try {
        const files = await consumeAndroidSharedFiles();
        if (files.length) {
          setQueue(rows => [...rows, ...files.map(file => ({ file, assetType: guessType(file) }))]);
          setMessage("已从 Android 系统分享接收 " + files.length + " 个文件，请确认分类和项目后导入。");
        }
      } catch {
        // PWA/browser mode or no pending Android share: keep the normal file-picker workflow.
      }
    };
    const onNativeShare = () => { void receiveSharedFiles(); };
    window.addEventListener("androidShareReceived", onNativeShare);
    void receiveSharedFiles();
    return () => window.removeEventListener("androidShareReceived", onNativeShare);
  },[]);

  function chooseFiles(e:ChangeEvent<HTMLInputElement>) {
    const chosen=Array.from(e.target.files||[]);
    setQueue(rows=>[...rows,...chosen.map(file=>({file,assetType:guessType(file)}))]);
    e.target.value="";
  }

  function changeQueuedType(index:number,assetType:AssetType) {
    setQueue(rows=>rows.map((row,i)=>i===index?{...row,assetType}:row));
  }

  async function uploadOne(row:QueuedFile) {
    const {file,assetType}=row;
    if(file.size>2*1024*1024*1024)throw new Error(`${file.name} 超过2GB单文件上限`);
    const headers=await csrfHeaders();
    const init=await fetch(`${API}/api/v1/uploads/init`,{method:"POST",credentials:"include",headers,body:JSON.stringify({
      file_name:file.name,mime_type:file.type||"application/octet-stream",asset_type:assetType,
      size_bytes:file.size,chunk_size:CHUNK_SIZE,project_id:projectId?Number(projectId):null
    })});
    const data=await init.json();if(!init.ok)throw new Error(data.detail||`${file.name} 初始化上传失败`);
    for(let index=0;index<data.total_chunks;index++){
      const start=index*data.chunk_size;
      const end=Math.min(file.size,(index+1)*data.chunk_size);
      const part="path" in file ? await readAndroidSharedChunk(file,start,end-start) : file.slice(start,end);
      const response=await fetch(`${API}/api/v1/uploads/${data.upload_id}/chunks/${index}`,{
        method:"PUT",credentials:"include",
        headers:{"X-CSRF-Token":headers["X-CSRF-Token"],"Content-Type":"application/octet-stream"},
        body:part
      });
      if(!response.ok){const error=await response.json();throw new Error(error.detail||`${file.name} 第${index+1}个分片上传失败`);}
      setProgress(Math.round(((index+1)/data.total_chunks)*100));
    }
    const completed=await fetch(`${API}/api/v1/uploads/${data.upload_id}/complete`,{
      method:"POST",credentials:"include",headers:{"X-CSRF-Token":headers["X-CSRF-Token"]}
    });
    const result=await completed.json();if(!completed.ok)throw new Error(result.detail||`${file.name} 文件合并失败`);
    return result;
  }

  async function uploadAll() {
    if(!queue.length)return;
    setBusy(true);setProgress(0);let succeeded=0;const failures:string[]=[];
    for(let i=0;i<queue.length;i++){
      const row=queue[i];setMessage(`正在导入第 ${i+1}/${queue.length} 个文件：${row.file.name}`);setProgress(0);
      try{await uploadOne(row);succeeded++;}
      catch(error){failures.push(error instanceof Error?error.message:"上传失败");}
    }
    setQueue([]);await load();setBusy(false);setProgress(100);
    setMessage(`导入结束：成功 ${succeeded} 个，失败 ${failures.length} 个。${failures.length? " "+failures.join("；"):""}`);
  }

  async function updateAsset(asset:Asset,changes:Record<string,unknown>) {
    try{
      const headers=await csrfHeaders();
      const response=await fetch(`${API}/api/v1/assets/${asset.id}`,{method:"PATCH",credentials:"include",headers,body:JSON.stringify(changes)});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"更新素材失败");
      setItems(rows=>rows.map(row=>row.id===asset.id?{...row,...data}:row));
      setMessage("素材信息已更新。");
    }catch(error){setMessage(error instanceof Error?error.message:"更新素材失败");}
  }

  async function download(asset:Asset) {
    try {
      const r=await fetch(`${API}/api/v1/assets/${asset.id}/download`,{credentials:"include"});
      if(!r.ok)throw new Error("下载失败");
      const url=URL.createObjectURL(await r.blob());const a=document.createElement("a");a.href=url;a.download=asset.file_name;a.click();URL.revokeObjectURL(url);
    } catch(error) { setMessage(error instanceof Error?error.message:"下载失败"); }
  }

  async function remove(asset:Asset) {
    try {
      const headers=await csrfHeaders();
      const r=await fetch(`${API}/api/v1/assets/${asset.id}`,{method:"DELETE",credentials:"include",headers});
      const d=await r.json();if(!r.ok)throw new Error(d.detail||"删除失败");
      setItems(rows=>rows.filter(item=>item.id!==asset.id));setMessage(d.message);
    } catch(error) { setMessage(error instanceof Error?error.message:"删除失败"); }
  }

  const visibleItems=items.filter(item=>filter==="all"||item.asset_type===filter);

  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">安卓素材交接中心</span></header>
    <section className="account-wrap" style={{width:"min(900px,100%)"}}><div className="account-card">
      <p className="eyebrow">ANDROID MEDIA HANDOFF</p><h1>素材交接中心</h1>
      <p>从手机上已安装的 AI 应用保存生成结果，再一次选择多个文件导入。系统会按扩展名和 MIME 类型预判素材类别，你可以在上传前修改，并关联到漫剧项目；独立视频剪辑项目可先将素材导入素材库，再在剪辑工作台中选择。</p>
      <div className="account-form">
        <label>关联项目（可选）<select value={projectId} onChange={e=>setProjectId(e.target.value)}>
          <option value="">暂不关联项目</option>{projects.map(project=><option key={project.id} value={project.id}>{project.title}</option>)}
        </select></label>
        <label>从手机选择文件（支持多选）<input type="file" multiple accept="image/*,video/*,audio/*,.srt,.vtt,.txt,.md,.markdown,.json,.csv,.pdf" onChange={chooseFiles}/></label>
        <p>支持图片、视频、音频、SRT/VTT 字幕、TXT/Markdown/JSON/CSV 文本和 PDF。单文件最大2GB，采用8MB分片上传。</p>
      </div>
      {queue.length>0&&<><h2>待导入文件（{queue.length}）</h2>{queue.map((row,index)=><article className="portal-card" key={row.file.name+("lastModified" in row.file?row.file.lastModified:row.file.path)+index}>
        <strong>{row.file.name}</strong><p>{(row.file.size/1024/1024).toFixed(2)} MB · 自动识别为：{typeLabels[row.assetType]}</p>
        <label>素材分类<select value={row.assetType} onChange={e=>changeQueuedType(index,e.target.value as AssetType)}>
          {Object.entries(typeLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}
        </select></label>
        <button type="button" className="account-submit" disabled={busy} onClick={()=>setQueue(rows=>rows.filter((_,i)=>i!==index))}>移除此文件</button>
      </article>)}
      <button className="account-submit" type="button" disabled={busy||!queue.length} onClick={()=>void uploadAll()}>{busy?"正在批量导入…":`开始导入 ${queue.length} 个文件`}</button>
      {busy&&<div className="upload-progress"><div style={{width:`${progress}%`}}/></div>}</>}
      <p className="account-message" role="status">{message}</p>
      <h2>我的素材（{items.length}）</h2>
      <div className="account-form"><label>筛选素材<select value={filter} onChange={e=>setFilter(e.target.value)}>
        <option value="all">全部素材</option>{Object.entries(typeLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}
      </select></label></div>
      {visibleItems.map(asset=><article className="portal-card" key={asset.id}>
        <strong>{asset.title}</strong><p>{typeLabels[asset.asset_type]||asset.asset_type} · {asset.file_name} · {(asset.size_bytes/1024/1024).toFixed(2)} MB</p>
        <label>所属项目<select value={asset.project_id??""} onChange={e=>void updateAsset(asset,{project_id:e.target.value?Number(e.target.value):null})}>
          <option value="">未关联项目</option>{projects.map(project=><option key={project.id} value={project.id}>{project.title}</option>)}
        </select></label>
        <p>{asset.approved?"已确认":"待确认"}</p>
        <div className="asset-actions">
          <button type="button" className="account-submit" onClick={()=>void updateAsset(asset,{approved:!asset.approved})}>{asset.approved?"取消确认":"确认素材"}</button>
          <button type="button" className="account-submit" onClick={()=>void download(asset)}>下载</button>
          <button type="button" className="account-submit" onClick={()=>void remove(asset)}>删除</button>
        </div>
      </article>)}
    </div></section>
  </main>;
}
