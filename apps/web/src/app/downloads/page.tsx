"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Release={platform:string;version:string;download_url:string;notes:string;minimum_supported_version:string};
export default function DownloadsPage(){const [items,setItems]=useState<Release[]>([]);const [message,setMessage]=useState("正在读取版本…");
useEffect(()=>{fetch(`${API}/api/v1/releases`).then(async r=>{if(!r.ok)throw new Error("版本服务暂不可用");const d=await r.json();setItems(d);setMessage(d.length?"":"暂无公开发布版本；目前仍处于开发阶段。");}).catch(e=>setMessage(e instanceof Error?e.message:"读取失败"));},[]);
return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">下载中心</span></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">DOWNLOAD & RELEASES</p><h1>版本下载</h1><p>Android 通过官网获取 APK；iPhone 首期使用 Safari 添加到主屏幕。请只安装本下载中心发布的正式版本。</p>{items.map((r,i)=><article className="portal-card" key={i}><strong>{r.platform.toUpperCase()} · {r.version}</strong><p>{r.notes}</p><small>最低支持版本：{r.minimum_supported_version}</small><a className="primary-action" href={r.download_url} rel="noopener noreferrer">下载 / 打开版本 ↗</a></article>)}<p className="account-message">{message}</p></div></section></main>;
}