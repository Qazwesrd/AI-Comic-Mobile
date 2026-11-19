const modules = [
  { number: "01", title: "小说导入", detail: "创建项目、导入文本并自动拆分章节", status: "已接入", href: "/projects" },
  { number: "02", title: "项目工作区", detail: "查看和管理你的小说漫剧项目", status: "创作流程", href: "/projects" },
  { number: "03", title: "发布中心", detail: "准备抖音、红果短剧和快手发布资料", status: "官方授权优先", href: "/publishing" },
  { number: "04", title: "永久授权", detail: "购买永久使用授权与查询订单", status: "账号服务", href: "/store" },
  { number: "05", title: "服务公告", detail: "查看版本更新和维护通知", status: "服务信息", href: "/notices" }
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
            <a className="module-card" key={module.number} href={module.href}>
              <span className="module-number">{module.number}</span>
              <div className="module-content">
                <span className="module-status">{module.status}</span>
                <h3>{module.title}</h3>
                <p>{module.detail}</p>
              </div>
              <span className="module-arrow">↗</span>
            </a>
          ))}
        </div>
      </section>

      <nav className="portal-nav"><a href="/projects">创作项目</a><a href="/assets">素材库</a><a href="/publishing">视频发布</a><a href="/store">购买授权</a><a href="/orders">订单查询</a><a href="/notices">维护公告</a><a href="/downloads">版本下载</a><a href="/admin">管理后台</a></nav>
      <footer className="footer">
        <span>AI COMIC MOBILE</span>
        <span>独立项目 · 赛博朋克创作体验</span>
      </footer>
    </main>
  );
}
