"use client";
import { useEffect,useState } from "react";
import { csrfHeaders } from "../../lib/api";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
type Product={code:string;name:string;description:string;amount_minor:number;currency:string};
type Order={order_no:string;status:string;message?:string};
export default function StorePage(){
 const [items,setItems]=useState<Product[]>([]);
 const [message,setMessage]=useState("正在加载商品…");
 const [order,setOrder]=useState<Order|null>(null);
 useEffect(()=>{fetch(`${API}/api/v1/store/products`).then(r=>r.json()).then(d=>{setItems(d);setMessage(d.length?"":"目前尚未配置可购买商品。");}).catch(()=>setMessage("暂时无法连接商店"));},[]);
 async function buy(code:string){
  try{
   const r=await fetch(`${API}/api/v1/orders`,{method:"POST",credentials:"include",headers:await csrfHeaders(),body:JSON.stringify({product_code:code})});
   const d=await r.json();if(!r.ok)throw new Error(d.detail||"请先登录");
   setOrder(d);setMessage(d.message||"订单已创建，请按页面指引付款并等待核验。");
  }catch(e){setMessage(e instanceof Error?e.message:"创建订单失败");}
 }
 return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><a className="system-pill" href="/account">账号中心</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">PERMANENT LICENSE</p><h1>购买永久授权</h1><p>人民币 30 元，一次付款，账号永久授权。更换设备后可登录账号恢复。第三方 AI 服务/API 费用另计。</p><div className="portal-card"><strong>¥30.00 CNY</strong><p>付款后请保留微信支付凭证。只有管理员核实收款账户实际到账后，才会发放永久授权。</p></div><div className="portal-card"><h2>微信扫码付款</h2><img src="/wechat-payment.svg" alt="微信收款二维码" style={{display:"block",width:"min(100%,360px)",height:"auto",margin:"16px auto",background:"#fff",padding:12,borderRadius:12}}/><p>请使用微信扫描上方收款码，按页面显示金额支付 ¥30.00。付款后保留支付凭证和订单号，等待管理员核实实际到账后开通永久授权。</p><p>请确认收款方信息与付款金额无误后再支付。</p></div>{items.map(p=><article className="portal-card" key={p.code}><h3>{p.name}</h3><p>{p.description}</p><strong>{(p.amount_minor/100).toFixed(2)} {p.currency}</strong><button className="account-submit" onClick={()=>void buy(p.code)}>创建付款订单</button></article>)}{order&&<section className="portal-card"><h2>订单已创建</h2><strong>{order.order_no}</strong><p>金额：¥30.00</p><p>当前状态：待付款 / 待核验</p><p>请联系网站管理员核对微信实际到账。请勿重复付款；订单核验成功后，账号将自动获得永久授权。</p><a className="primary-action" href="/orders">查看订单状态 ↗</a></section>}<p className="account-message">{message}</p><a className="account-back" href="/orders">查询我的订单</a></div></section></main>;
}