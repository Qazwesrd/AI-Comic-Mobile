"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { csrfHeaders } from "../../lib/api";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const CHUNK_SIZE = 8 * 1024 * 1024;
type Asset = { id:number; asset_type:string; title:string; file_name:string; mime_type:string; size_bytes:number; approved:boolean };

export default function AssetsPage() {
  const [assetType,setAssetType]=useState("video");
  const [file,setFile]=useState<File|null>(null);
  const [items,setItems]=useState<Asset[]>([]);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [progress,setProgress]=useState(0);

  async function load() {
    try { const r=await fetch(`${API}/api/v1/assets`,{credentials:"include"}); if(r.ok)setItems(await r.json()); }
    catch { setMessage("无法读取素材库，请检查登录和网络"); }
  }
  useEffect(()=>{void load();},[]);

  function chooseFile(e:ChangeEvent<HTMLInputElement>) { setFile(e.target.files?.[0]||null); }

  async function upload() {
    if(!file)return;
    if(file.size>2*1024*1024*1024){setMessage("单个文件不能超过2GB");return;}
    setBusy(true);setProgress(0);setMessage("正在初始化分片上传…");
    try {
      const headers=await csrfHeaders();
      const init=await fetch(`${API}/api/v1/uploads/init`,{method:"POST",credentials:"include",headers,body:JSON.stringify({
        file_name:file.name,mime_type:file.type||"application/octet-stream",asset_type:assetType,size_bytes:file.size,chunk_size:CHUNK_SIZE
      })});
      const data=await init.json();if(!init.ok)throw new Error(data.detail||"初始化上传失败");
      for(let index=0;index<data.total_chunks;index++){
        const part=file.slice(index*data.chunk_size,Math.min(file.size,(index+1)*data.chunk_size));
        const response=await fetch(`${API}/api/v1/uploads/${data.upload_id}/chunks/${index}`,{
          method:"PUT",credentials:"include",
          headers:{"X-CSRF-Token":headers["X-CSRF-Token"],"Content-Type":"application/octet-stream"},
          body:part
        });
        if(!response.ok){const error=await response.json();throw new Error(error.detail||`第${index+1}个分片上传失败`);}
        setProgress(Math.round(((index+1)/data.total_chunks)*100));
      }
      const completed=await fetch(`${API}/api/v1/uploads/${data.upload_id}/complete`,{
        method:"POST",credentials:"include",headers:{"X-CSRF-Token":headers["X-CSRF-Token"]}
      });
      const result=await completed.json();if(!completed.ok)throw new Error(result.detail||"文件合并失败");
      setMessage("上传完成，素材已安全保存。");setFile(null);setProgress(100);await load();
    } catch(error) { setMessage(error instanceof Error?error.message:"上传失败，请重试"); }
    finally { setBusy(false); }
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

  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">素材库</span></header>
    <section className="account-wrap"><div className="account-card">
      <p className="eyebrow">PRIVATE MEDIA LIBRARY</p><h1>素材库</h1>
      <p>支持图片、人物/场景/道具参考图、视频、音频和字幕。文件采用8MB分片上传，单文件上限2GB；素材默认仅当前账号可访问。</p>
      <div className="account-form">
        <label>素材类型<select value={assetType} onChange={e=>setAssetType(e.target.value)}>
          <option value="video">视频</option><option value="image">图片</option><option value="character">人物参考图</option>
          <option value="scene">场景参考图</option><option value="prop">道具参考图</option><option value="reference">参考资料（图片/PDF）</option>
          <option value="audio">音频</option><option value="subtitle">字幕（SRT/VTT）</option>
        </select></label>
        <label>选择文件<input type="file" onChange={chooseFile}/></label>
        {file&&<p>{file.name} · {(file.size/1024/1024).toFixed(2)} MB</p>}
        <button className="account-submit" type="button" disabled={!file||busy} onClick={()=>void upload()}>{busy?"正在上传…":"开始分片上传"}</button>
        {busy&&<div className="upload-progress"><div style={{width:`${progress}%`}}/></div>}
        <p className="account-message">{message}</p>
      </div>
      <h2>我的素材（{items.length}）</h2>
      {items.map(asset=><article className="portal-card" key={asset.id}>
        <strong>{asset.title}</strong><p>{asset.asset_type} · {asset.file_name} · {(asset.size_bytes/1024/1024).toFixed(2)} MB</p>
        <p>{asset.approved?"已确认":"待确认"}</p>
        <div className="asset-actions"><button type="button" className="account-submit" onClick={()=>void download(asset)}>下载</button><button type="button" className="account-submit" onClick={()=>void remove(asset)}>删除</button></div>
      </article>)}
    </div></section>
  </main>;
}
