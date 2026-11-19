const modules = [
  { number: "01", title: "小说解析", detail: "拆解章节、人物、关系与剧情脉络", status: "核心创作" },
  { number: "02", title: "角色与资产", detail: "统一管理人物、场景、道具视觉设定", status: "资产中心" },
  { number: "03", title: "剧本与分镜", detail: "改编剧本，规划分集和镜头画面", status: "创作流程" },
  { number: "04", title: "漫剧生成", detail: "组织画面、配音、字幕并导出成片", status: "成片制作" },
  { number: "05", title: "视频发布", detail: "抖音 · 红果短剧 · 快手", status: "发布中心" }
];

export default function HomePage() {
  return (
    <main className="app-shell">
      <div className="ambient ambient-a" aria-hidden="true" />
      <div className="ambient ambient-b" aria-hidden="true" />
      <header className="topbar">
        <a className="brand" href="/" aria-label="AI 漫剧手机版首页">
          <span className="brand-mark">AI</span>
          <span><strong>AI 漫剧</strong><small>MOBILE STUDIO</small></span>
        </a>
        <a className="system-pill" href="/account"><i /> 登录 / 注册</a>
      </header>

      <section className="hero">
        <p className="eyebrow">NEXT-GEN STORY CREATION</p>
        <h1>让故事，<span>变成漫剧。</span></h1>
        <p className="hero-copy">从小说解析到分镜生成，再到漫剧成片与平台发布。<br />把复杂创作流程，装进你的手机。</p>
        <div className="hero-actions">
          <a className="primary-action" href="#modules">进入创作工作台 <span>↗</span></a>
          <span className="platform-note">ANDROID · IPHONE · PWA</span>
        </div>
      </section>

      <section className="workspace" id="modules">
        <div className="section-heading">
          <div><p className="eyebrow">YOUR CREATIVE ENGINE</p><h2>创作中心</h2></div>
          <span className="section-count">05 MODULES</span>
        </div>
        <div className="module-grid">
          {modules.map((module) => (
            <article className="module-card" key={module.number}>
              <span className="module-number">{module.number}</span>
              <div className="module-content">
                <span className="module-status">{module.status}</span>
                <h3>{module.title}</h3>
                <p>{module.detail}</p>
              </div>
              <span className="module-arrow">↗</span>
            </article>
          ))}
        </div>
      </section>

      <footer className="footer">
        <span>AI COMIC MOBILE</span>
        <span>独立项目 · 赛博朋克创作体验</span>
      </footer>
    </main>
  );
}
