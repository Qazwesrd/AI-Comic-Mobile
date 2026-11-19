const modules = [
  { number: "01", title: "小说导入", detail: "创建项目、导入文本并自动拆分章节", status: "已接入", href: "/projects" },
  { number: "02", title: "项目工作区", detail: "查看和管理你的小说漫剧项目", status: "创作流程", href: "/projects" },
  { number: "03", title: "AI 工具中心", detail: "内置 AI API 或启动手机已安装的 AI 客户端", status: "双模式接入", href: "/ai-tools" },
  { number: "04", title: "AI 视频剪辑", detail: "上传原视频，通过文字指令规划和编辑时间线", status: "独立剪辑工作台", href: "/video-editing" },
  { number: "05", title: "发布中心", detail: "准备抖音、红果短剧和快手发布资料", status: "官方授权优先", href: "/publishing" },
  { number: "06", title: "永久授权", detail: "购买永久使用授权与查询订单", status: "账号服务", href: "/store" },
  { number: "07", title: "素材交接中心", detail: "从手机批量导入 AI 生成的图片、视频、音频和文本", status: "安卓素材管理", href: "/assets" },
  { number: "08", title: "服务公告", detail: "查看版本更新和维护通知", status: "服务信息", href: "/notices" }
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
        <p className="hero-copy">从小说解析、人物场景资产，到分镜漫剧与 AI 视频剪辑。<br />两天免费试用，30 元一次购买，账号永久授权。</p>
        <div className="hero-actions">
          <a className="primary-action" href="#modules">进入创作工作台 <span>↗</span></a>
          <span className="platform-note">ANDROID FIRST · 48H TRIAL · ¥30 LIFETIME</span>
        </div>
      </section>

      <section className="workspace" id="modules">
        <div className="section-heading">
          <div><p className="eyebrow">YOUR CREATIVE ENGINE</p><h2>创作中心</h2></div>
          <span className="section-count">08 MODULES</span>
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

      <section className="portal-card"><h2>简单透明的授权方式</h2><p>首次激活可免费体验 48 小时。试用结束后，支付人民币 30 元即可获得账号永久授权。第三方 AI 服务/API 费用由对应服务商收取，不包含在软件授权内。</p><a className="primary-action" href="/store">查看购买方式 ↗</a></section>
      <nav className="portal-nav"><a href="/projects">创作项目</a><a href="/assets">素材交接中心</a><a href="/render">分镜合成</a><a href="/ai-tools">AI工具中心</a><a href="/video-editing">AI视频剪辑</a><a href="/audio">AI配音</a><a href="/publishing">视频发布</a><a href="/store">购买授权</a><a href="/orders">订单查询</a><a href="/notices">维护公告</a><a href="/downloads">版本下载</a><a href="/admin">管理后台</a></nav>
      <footer className="footer">
        <span>AI COMIC MOBILE</span>
        <span>独立项目 · 赛博朋克创作体验</span>
      </footer>
    </main>
  );
}
