"use client";
import { FormEvent, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
export default function ForgotPasswordPage() {
  const [email,setEmail]=useState(""); const [message,setMessage]=useState(""); const [busy,setBusy]=useState(false);
  async function submit(e:FormEvent){e.preventDefault();setBusy(true);setMessage("");try{
    const r=await fetch(`${API}/api/v1/auth/password/forgot`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email})});
    const d=await r.json();if(!r.ok)throw new Error(d.detail||"请求失败");setMessage(d.message);
  }catch(e){setMessage(e instanceof Error?e.message:"网络错误");}finally{setBusy(false);}}
  return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">ACCOUNT RECOVERY</p><h1>找回密码</h1><p>输入注册邮箱。如果账号存在且邮件服务已配置，我们会发送一次性重置链接。</p><form className="account-form" onSubmit={submit}><label>邮箱地址<input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><button className="account-submit" disabled={busy}>{busy?"正在发送…":"发送重置邮件"}</button></form><p className="account-message">{message}</p><a className="account-back" href="/account">返回登录</a></div></section></main>;
}