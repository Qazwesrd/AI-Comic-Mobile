"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Notice={id:number;title:string;body:string;created_at:string};
export default function NoticesPage(){const [items,setItems]=useState<Notice[]>([]);useEffect(()=>{fetch(`${API}/api/v1/notices`).then(r=>r.json()).then(setItems).catch(()=>setItems([]));},[]);
return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">SERVICE UPDATES</p><h1>维护公告</h1>{items.length?items.map(n=><article className="portal-card" key={n.id}><h3>{n.title}</h3><p>{n.body}</p><small>{new Date(n.created_at).toLocaleString()}</small></article>):<p>暂无公告。</p>}</div></section></main>;
}