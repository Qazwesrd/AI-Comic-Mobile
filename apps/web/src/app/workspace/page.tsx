const modules = [
  { title: "小说与项目", detail: "导入小说、创建项目、管理章节", href: "/projects", icon: "01" },
  { title: "AI 工具中心", detail: "调用 AI 服务或交接到手机 AI 客户端", href: "/ai-tools", icon: "02" },
  { title: "素材资产库", detail: "管理人物、场景、道具和生成素材", href: "/assets", icon: "03" },
  { title: "分镜与合成", detail: "整理镜头、预览并导出视频", href: "/render", icon: "04" },
  { title: "AI 视频剪辑", detail: "独立剪辑项目与时间线工作台", href: "/video-editing", icon: "05" },
  { title: "AI 配音", detail: "管理旁白、配音和音频素材", href: "/audio", icon: "06" },
  { title: "视频发布", detail: "准备抖音、红果短剧和快手发布资料", href: "/publishing", icon: "07" },
  { title: "账号与设备", detail: "查看账号、试用状态和设备", href: "/account", icon: "08" }
];

export default function WorkspacePage() {
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
