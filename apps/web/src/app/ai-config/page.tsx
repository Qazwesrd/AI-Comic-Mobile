"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Capability = "text" | "image" | "audio";
type Config = { id:number; capability:Capability; provider:string; base_url:string; model:string; enabled:boolean; api_key_configured:boolean };
type Log = { capability:string; provider:string; model:string; action:string; status:string; latency_ms:number|null; error_code:string|null; created_at:string };

const labels:Record<Capability,string> = { text:"文本 AI", image:"图片 AI", audio:"语音 AI" };

export default function AIConfigPage() {
  const [configs,setConfigs]=useState<Config[]>([]);
  const [logs,setLogs]=useState<Log[]>([]);
  const [capability,setCapability]=useState<Capability>("text");
  const [provider,setProvider]=useState("DeepSeek");
  const [baseUrl,setBaseUrl]=useState("https://api.deepseek.com/v1");
  const [apiKey,setApiKey]=useState("");
  const [model,setModel]=useState("deepseek-chat");
  const [enabled,setEnabled]=useState(true);
  const [csrf,setCsrf]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);

  async function load() {
    const [cfg,log,token]=await Promise.all([
      fetch(API+"/api/v1/ai-provider-configs",{credentials:"include"}),
      fetch(API+"/api/v1/ai-provider-configs/usage-logs",{credentials:"include"}),
      fetch(API+"/api/v1/auth/csrf",{credentials:"include"})
    ]);
    if(cfg.status===401){setMessage("请先登录账号，再配置自己的 AI 服务。");return;}
    if(!cfg.ok) throw new Error("读取 AI 配置失败");
    setConfigs((await cfg.json()).configs);
    if(log.ok) setLogs((await log.json()).logs);
    if(token.ok) setCsrf((await token.json()).csrf_token);
  }

  useEffect(()=>{void load().catch(e=>setMessage(e instanceof Error?e.message:"加载失败"));},[]);

  async function save(event:FormEvent) {
    event.preventDefault();setBusy(true);setMessage("");
    try {
      const response=await fetch(API+"/api/v1/ai-provider-configs",{method:"PUT",credentials:"include",
        headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},
        body:JSON.stringify({capability,provider,base_url:baseUrl,api_key:apiKey||null,model,enabled})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"保存失败");
      setApiKey("");setMessage("配置已安全保存。API Key 不会再次显示。");await load();
    } catch(e){setMessage(e instanceof Error?e.message:"保存失败");}
    finally{setBusy(false);}
  }

  async function test() {
    setBusy(true);setMessage("正在测试连接…");
    try {
      const response=await fetch(API+`/api/v1/ai-provider-configs/${capability}/test`,{method:"POST",credentials:"include",headers:{"X-CSRF-Token":csrf}});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"测试失败");
      setMessage(data.message);await load();
    } catch(e){setMessage(e instanceof Error?e.message:"连接测试失败");}
    finally{setBusy(false);}
  }

  async function remove() {
    if(!window.confirm("确定删除当前能力的 AI 服务配置吗？"))return;
    const response=await fetch(API+`/api/v1/ai-provider-configs/${capability}`,{method:"DELETE",credentials:"include",headers:{"X-CSRF-Token":csrf}});
    const data=await response.json();setMessage(response.ok&&data.deleted?"配置已删除。":response.ok?"当前没有已保存配置。":data.detail||"删除失败");await load();
  }

  const current=configs.find(item=>item.capability===capability);
  return <main className="app-shell">
    <div className="ambient ambient-a" aria-hidden="true"/><div className="ambient ambient-b" aria-hidden="true"/>
    <header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">AI PROVIDER SETTINGS</span></header>
    <section className="account-wrap" style={{width:"min(960px,100%)"}}>
      <a className="account-back" href="/ai-tools">← 返回 AI 工具中心</a>
      <div className="account-card">
        <p className="eyebrow">YOUR AI · YOUR API KEYS</p><h1>AI 服务配置中心</h1>
        <p>为文本、图片、语音分别配置兼容 OpenAI API 格式的服务。密钥仅保存在服务器端并加密，不会返回到手机。</p>
        <div className="account-tabs">{(["text","image","audio"] as Capability[]).map(value=><button key={value} type="button" className={capability===value?"active":""} onClick={()=>setCapability(value)}>{labels[value]}</button>)}</div>
        {current&&<p className="account-message">当前已保存：{current.provider} · {current.model} · {current.api_key_configured?"密钥已保存":"未保存密钥"}</p>}
        <form className="account-form" onSubmit={save}>
          <label>服务商名称<input value={provider} onChange={e=>setProvider(e.target.value)} required maxLength={48} placeholder="例如 DeepSeek、OpenAI、豆包"/></label>
          <label>API Base URL<input type="url" value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} required placeholder="https://api.example.com/v1"/></label>
          <label>API Key<input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} autoComplete="new-password" placeholder={current?"已保存密钥；留空表示保持不变":"请输入 API Key"} required={!current}/></label>
          <label>模型名称<input value={model} onChange={e=>setModel(e.target.value)} required maxLength={160} placeholder="例如 deepseek-chat"/></label>
          <label className="checkbox-label"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/> 启用此服务</label>
          <button className="account-submit" disabled={busy}>{busy?"处理中…":"保存配置"}</button>
        </form>
        <p className="account-message">连接测试会向服务商请求模型列表，可能受服务商计费规则影响；请先确认账号额度和收费政策。软件不会自动购买或充值。</p>
        <div className="account-tabs"><button className="account-submit" type="button" disabled={busy||!current} onClick={()=>void test()}>测试当前服务连接</button><button className="account-submit" type="button" disabled={busy||!current} onClick={()=>void remove()}>删除当前配置</button></div>
        <p className="account-message" role="status">{message}</p>
        <h2>最近连接记录</h2>
        {logs.length===0?<p>暂无记录。</p>:logs.map((log,i)=><article className="portal-card" key={i}><strong>{labels[log.capability as Capability]||log.capability} · {log.provider}</strong><p>{log.model} · {log.status==="success"?"连接成功":"连接失败"} · {log.latency_ms??"—"} ms</p><small>{new Date(log.created_at).toLocaleString()}</small></article>)}
      </div>
    </section>
  </main>;
}
