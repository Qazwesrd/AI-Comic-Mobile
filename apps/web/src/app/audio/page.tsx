"use client";

import { getApiBaseUrl } from "../../lib/api-base";

import { FormEvent,useState } from "react";
import { csrfHeaders } from "../../lib/api";

const API = getApiBaseUrl();
export default function AudioPage(){
  const [text,setText]=useState("");const [voice,setVoice]=useState("alloy");
  const [message,setMessage]=useState("");const [assetId,setAssetId]=useState<number|null>(null);const [subtitleId,setSubtitleId]=useState<number|null>(null);
  const [busy,setBusy]=useState(false);
  async function generate(e:FormEvent){e.preventDefault();setBusy(true);setMessage("");setAssetId(null);try{
    const headers=await csrfHeaders();
    const r=await fetch(`${API}/api/v1/audio/speech`,{method:"POST",credentials:"include",headers,body:JSON.stringify({text,voice})});
    const d=await r.json();if(!r.ok)throw new Error(d.detail||"语音生成失败");
    setAssetId(d.asset_id);setMessage("配音已生成并保存到素材库。");
  }catch(e){setMessage(e instanceof Error?e.message:"语音服务不可用");}finally{setBusy(false);}}
  async function generateSubtitle(){if(!text.trim())return;setBusy(true);setMessage("");setSubtitleId(null);try{const headers=await csrfHeaders();const r=await fetch(`${API}/api/v1/audio/subtitles`,{method:"POST",credentials:"include",headers,body:JSON.stringify({text})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"字幕生成失败");setSubtitleId(d.asset_id);setMessage(`字幕生成完成，共${d.segments}条。`);}catch(e){setMessage(e instanceof Error?e.message:"字幕服务不可用");}finally{setBusy(false);}}
  async function downloadAsset(id:number,name:string){const r=await fetch(`${API}/api/v1/assets/${id}/download`,{credentials:"include"});if(!r.ok){setMessage("下载失败");return;}const url=URL.createObjectURL(await r.blob());const a=document.createElement("a");a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
  return <main className="app-shell"><header className="topbar"><a className="brand" href="/">AI 漫剧手机版</a><span className="system-pill">AI配音</span></header><section className="account-wrap"><div className="account-card"><p className="eyebrow">AI VOICE GENERATION</p><h1>AI配音生成</h1><p>输入旁白或角色台词，调用你配置的兼容语音服务生成 MP3，并自动存入素材库。</p><form className="account-form" onSubmit={generate}><label>配音文本<textarea required rows={8} maxLength={20000} value={text} onChange={e=>setText(e.target.value)} placeholder="输入旁白、角色对白或解说词…"/></label><label>声音<select value={voice} onChange={e=>setVoice(e.target.value)}><option value="alloy">Alloy</option><option value="echo">Echo</option><option value="fable">Fable</option><option value="onyx">Onyx</option><option value="nova">Nova</option><option value="shimmer">Shimmer</option></select></label><button className="account-submit" disabled={busy||!text.trim()}>{busy?"正在生成…":"生成配音"}</button></form><p className="account-message">{message}</p>{assetId&&<button className="account-submit" onClick={()=>void downloadAsset(assetId,"ai-voiceover.mp3")}>下载 MP3</button>}<button className="account-submit" disabled={busy||!text.trim()} onClick={()=>void generateSubtitle()}>根据文本生成 SRT 字幕</button>{subtitleId&&<button className="account-submit" onClick={()=>void downloadAsset(subtitleId,"ai-subtitles.srt")}>下载 SRT 字幕</button>}<a className="account-back" href="/assets">打开素材库</a></div></section></main>;
}
