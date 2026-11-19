"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Project = { id: number; title: string; description: string; status: string; updated_at?: string | null };

const modules = [
  { title: "小说与项目", detail: "导入小说、创建项目、管理章节", href: "/projects", icon: "01" },
  { title: "AI 工具中心", detail: "调用 AI 服务或交接到手机 AI 客户端", href: "/ai-tools", icon: "02" },
  { title: "素材资产库", detail: "管理人物、场景、道具和生成素材", href: "/assets", icon: "03" },
  { title: "分镜与合成", detail: "整理镜头、预览并导出视频", href: "/render", icon: "04" },
  { title: "AI 视频剪辑", detail: "独立剪辑项目与时间线工作台", href: "/video-editing", icon: "05" },
  { title: "AI 配音", detail: "管理旁白、配音和音频素材", href: "/audio", icon: "06" },
  { title: "视频发布", detail: "准备短视频发布资料", href: "/publishing", icon: "07" },
  { title: "账号与设备", detail: "查看账号、试用状态和设备", href: "/account", icon: "08" }
];

export default function WorkspacePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [signedIn, setSignedIn] = useState(true);

  useEffect(() => {
    let active = true;
    fetch(API + "/api/v1/projects", { credentials: "include" })
      .then(async response => {
        if (response.status === 401) {
          if (active) setSignedIn(false);
          return [];
        }
        if (!response.ok) throw new Error("读取项目失败");
        return await response.json() as Project[];
      })
      .then(rows => { if (active) setProjects(rows.slice(0, 4)); })
      .catch(() => { if (active) setProjects([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <main className="app-shell mobile-workspace">
      <header className="topbar">
        <a className="brand" href="/workspace/"><span className="brand-mark">AI</span><span><strong>漫剧大师</strong><small>MOBILE CREATIVE STUDIO</small></span></a>
        <a className="system-pill" href="/account/">账号中心</a>
      </header>
      <section className="workspace-hero">
        <p className="eyebrow">YOUR STORY · YOUR STUDIO</p>
        <h1>把灵感，<span>制作成漫剧。</span></h1>
        <p>从小说解析到人物资产、分镜制作和视频输出，在一个创作空间完成工作。</p>
        <div className="workspace-quick-actions">
          <a className="primary-action" href="/projects/">开始新创作 <span>↗</span></a>
          <a className="secondary-action" href="/assets/">打开素材库</a>
        </div>
      </section>

      <section className="workspace workspace-resume" aria-label="继续创作">
        <div className="section-heading"><div><p className="eyebrow">PICK UP WHERE YOU LEFT OFF</p><h2>继续上次创作</h2></div><a className="section-link" href="/projects/">全部项目 ↗</a></div>
        {!signedIn ? <article className="workspace-empty"><strong>登录后即可同步你的项目</strong><p>登录后会显示最近创作的项目，可从上次进度继续。</p><a href="/login/">前往登录 →</a></article>
          : loading ? <p className="workspace-loading">正在读取最近项目…</p>
          : projects.length ? <div className="workspace-recent-grid">{projects.map(project => <a className="workspace-recent-card" href={`/projects?project=${project.id}`} key={project.id}><span>项目 #{project.id}</span><strong>{project.title}</strong><small>{project.status || "进行中"} · 点击继续</small></a>)}</div>
          : <article className="workspace-empty"><strong>还没有创作项目</strong><p>创建第一个项目并导入 TXT 小说，AI 将帮助你拆分章节、识别素材并生成剧本与分镜。</p><a href="/projects/">创建第一个项目 →</a></article>}
      </section>

      <section className="workspace" aria-label="软件功能">
        <div className="section-heading"><div><p className="eyebrow">CREATION TOOLS</p><h2>创作工作台</h2></div><span className="section-count">TOOLS</span></div>
        <div className="module-grid">
          {modules.map((item) => (
            <a className="module-card" key={item.icon} href={item.href}>
              <span className="module-number">{item.icon}</span>
              <div className="module-content"><span className="module-status">打开功能</span><h3>{item.title}</h3><p>{item.detail}</p></div>
              <span className="module-arrow">↗</span>
            </a>
          ))}
        </div>
      </section>
      <footer className="footer"><span>AI COMIC MOBILE APP</span><span>独立创作工作台 · 云端同步</span></footer>
    </main>
  );
}
