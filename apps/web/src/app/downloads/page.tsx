"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Release={release_id:number;platform:string;version:string;notes:string;minimum_supported_version:string};
export default function DownloadsPage(){
 const [items,setItems]=useState<Release[]>([]);
 const [message,setMessage]=useState("正在读取版本…");
 useEffect(()=>{
  fetch(`${API}/api/v1/releases`).then(async r=>{
   if(!r.ok)throw new Error("版本服务暂不可用");
   const d=await r.json() as Release[];
   setItems(d);setMessage(d.length?"正式版下载仅对已获得永久授权的账号开放。":"暂无公开发布版本；目前仍处于开发阶段。");
  }).catch(e=>setMessage(e instanceof Error?e.message:"读取失败"));
 },[]);
 return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">下载中心</span></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">DOWNLOAD & RELEASES</p><h1>版本下载</h1><p>正式版下载需要登录已获得永久授权的账号。系统会在每次下载时重新核验授权，未授权账号无法通过下载接口取得安装包。</p>{items.map(r=><article className="portal-card" key={r.release_id}><strong>{r.platform.toUpperCase()} · {r.version}</strong><p>{r.notes}</p><small>最低支持版本：{r.minimum_supported_version}</small><a className="primary-action" href={`${API}/api/v1/releases/${r.release_id}/download`} rel="noopener noreferrer">验证授权并下载 ↗</a></article>)}<p className="account-message">{message}</p><a className="account-back" href="/store">购买永久授权</a></div></section></main>;
}