"use client";
import { useEffect,useState } from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Product={code:string;name:string;description:string;amount_minor:number;currency:string};
export default function StorePage(){const [items,setItems]=useState<Product[]>([]);const [message,setMessage]=useState("正在加载商品…");
useEffect(()=>{fetch(`${API}/api/v1/store/products`).then(r=>r.json()).then(d=>{setItems(d);setMessage(d.length?"":"目前尚未配置可购买商品。");}).catch(()=>setMessage("暂时无法连接商店"));},[]);
async function buy(code:string){const r=await fetch(`${API}/api/v1/orders`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_code:code})});const d=await r.json();setMessage(r.ok?d.message:d.detail||"请先登录");}
return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><a className="system-pill" href="/account">账号中心</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">PERMANENT LICENSE</p><h1>购买永久授权</h1><p>一次付款，账号永久授权。更换设备后可登录账号恢复。第三方 AI 服务可能另有费用。</p>{items.map(p=><article className="portal-card" key={p.code}><h3>{p.name}</h3><p>{p.description}</p><strong>{(p.amount_minor/100).toFixed(2)} {p.currency}</strong><button className="account-submit" onClick={()=>void buy(p.code)}>创建订单</button></article>)}<p className="account-message">{message}</p><a className="account-back" href="/orders">查询我的订单</a></div></section></main>;
}