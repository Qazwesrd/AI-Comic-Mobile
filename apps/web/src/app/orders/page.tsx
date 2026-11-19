"use client";
import { useEffect,useState } from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Order={order_no:string;status:string;amount_minor:number;currency:string;created_at:string};
export default function OrdersPage(){const [orders,setOrders]=useState<Order[]>([]);const [message,setMessage]=useState("正在读取订单…");
useEffect(()=>{fetch(`${API}/api/v1/orders`,{credentials:"include"}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.detail||"请先登录");setOrders(d);setMessage(d.length?"":"暂无订单");}).catch(e=>setMessage(e instanceof Error?e.message:"读取失败"));},[]);
return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">ORDER HISTORY</p><h1>我的订单</h1>{orders.map(o=><article className="portal-card" key={o.order_no}><strong>{o.order_no}</strong><p>{o.status} · {(o.amount_minor/100).toFixed(2)} {o.currency}</p></article>)}<p className="account-message">{message}</p><a className="account-back" href="/store">返回商店</a></div></section></main>;
}