"use client";
import { FormEvent,useState } from "react";
import { useSearchParams } from "next/navigation";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://127.0.0.1:8000";
export default function ResetPasswordPage(){const params=useSearchParams();const token=params.get("token")||"";const [password,setPassword]=useState("");const [message,setMessage]=useState("");
async function submit(e:FormEvent){e.preventDefault();const r=await fetch(`${API}/api/v1/auth/password/reset`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token,new_password:password})});const d=await r.json();setMessage(r.ok?d.message:d.detail||"重置失败");}
return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">SECURE RESET</p><h1>设置新密码</h1>{!token?<p>链接缺少安全令牌，请从重置邮件重新打开。</p>:<form className="account-form" onSubmit={submit}><label>新密码（至少10位）<input type="password" minLength={10} maxLength={128} required value={password} onChange={e=>setPassword(e.target.value)}/></label><button className="account-submit">确认重置密码</button></form>}<p className="account-message">{message}</p><a className="account-back" href="/account">返回登录</a></div></section></main>;
}