const features = [
  ["小说智能解析", "识别章节、人物、人物关系、场景、道具、事件与故事时间线。"],
  ["角色与场景资产", "建立统一角色和场景资料，管理形象设定及可复用素材。"],
  ["AI 剧本与分镜", "将小说内容整理为漫剧剧本，规划镜头并支持后续调整。"],
  ["漫剧画面与合成", "整理生成画面、字幕和音频，制作可导出的漫剧视频。"],
  ["独立视频剪辑", "通过文字描述剪辑目标，辅助分析素材并规划时间线。"],
  ["视频发布准备", "为抖音、红果短剧和快手整理标题、封面及发布素材。"]
];

export default function HomePage() {
  return (
    <main className="app-shell official-site">
      <div className="ambient ambient-a" aria-hidden="true" />
      <div className="ambient ambient-b" aria-hidden="true" />
      <header className="topbar">
        <a className="brand" href="/"><span className="brand-mark">AI</span><span><strong>AI 漫剧大师</strong><small>OFFICIAL WEBSITE</small></span></a>
        <nav className="site-nav"><a href="/features/">功能介绍</a><a href="/guide/">使用教程</a><a href="/faq/">常见问题</a><a className="system-pill" href="/store/">付款与授权</a></nav>
      </header>
      <section className="site-hero">
        <p className="eyebrow">AI STORY-TO-COMIC CREATION</p>
        <h1>让小说故事，<span>成为精彩漫剧。</span></h1>
        <p className="site-lead">AI 漫剧大师是一款面向手机用户的 AI 漫剧创作软件。围绕小说解析、人物与场景资产、剧本分镜、画面合成和视频发布准备，打造完整的移动创作流程。</p>
        <div className="hero-actions"><a className="primary-action" href="/features/">了解软件功能 <span>↗</span></a><a className="secondary-action" href="/guide/">查看使用教程</a></div>
        <p className="site-meta">ANDROID · iOS PLANNED · 48-HOUR TRIAL · ¥30 LIFETIME LICENSE</p>
      </section>
      <section className="site-section">
        <div className="section-heading"><div><p className="eyebrow">WHAT YOU CAN CREATE</p><h2>软件核心功能</h2></div><a className="section-link" href="/features/">查看全部功能 ↗</a></div>
        <div className="site-feature-grid">{features.map(([title, detail], index) => <article className="site-feature" key={title}><span>{String(index + 1).padStart(2, "0")}</span><h3>{title}</h3><p>{detail}</p></article>)}</div>
      </section>
      <section className="site-section site-flow">
        <p className="eyebrow">SIMPLE CREATION FLOW</p><h2>从文字到漫剧，四步完成创作</h2>
        <div className="flow-grid"><article><b>01</b><h3>导入小说</h3><p>创建项目并导入文本，整理章节内容。</p></article><article><b>02</b><h3>AI 解析</h3><p>识别人物、场景、道具和关键剧情。</p></article><article><b>03</b><h3>剧本分镜</h3><p>生成剧本与分镜，检查并调整创作结果。</p></article><article><b>04</b><h3>制作输出</h3><p>整理画面、音频和字幕，合成视频成果。</p></article></div>
      </section>
      <section className="site-cta"><div><p className="eyebrow">START YOUR CREATION</p><h2>先了解，再开始创作。</h2><p>首次激活提供连续 48 小时试用。试用结束后，可在官网完成付款并获取正式版下载资格。</p></div><div className="site-cta-actions"><a className="primary-action" href="/guide/">阅读使用教程 ↗</a><a className="secondary-action" href="/store/">付款与授权说明</a></div></section>
      <footer className="site-footer"><div><strong>AI 漫剧大师</strong><p>官方产品介绍、功能说明、使用教程与下载服务。</p></div><nav><a href="/features/">功能介绍</a><a href="/guide/">使用教程</a><a href="/store/">付款与授权</a><a href="/downloads/">下载中心</a><a href="/privacy/">隐私政策</a><a href="/terms/">用户协议</a></nav><small>© AI 漫剧大师 · 以实际发布版本功能为准</small></footer>
    </main>
  );
}
