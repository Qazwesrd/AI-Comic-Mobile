"use client";
import { useEffect,useState } from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
export default function VerifyEmailPage(){const [token,setToken]=useState("");const [message,setMessage]=useState("正在验证邮箱…");
useEffect(()=>{const value=new URLSearchParams(window.location.search).get("token")||"";setToken(value);if(!value){setMessage("验证链接无效或缺少令牌");return;}fetch(`${API}/api/v1/auth/email/verify/confirm`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:value})}).then(async r=>{const d=await r.json();setMessage(r.ok?d.message:d.detail||"验证失败");}).catch(()=>setMessage("网络连接失败，请稍后重试"));},[]);
return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">EMAIL VERIFICATION</p><h1>邮箱验证</h1><p>{message}</p><a className="account-back" href="/account">返回账号中心</a></div></section></main>;
}