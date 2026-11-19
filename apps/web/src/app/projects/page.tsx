"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { csrfHeaders } from "../../lib/api";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Project = { id: number; title: string; description: string; status: string };
type NovelSummary = { id: number; title: string; analysis_status: string; chapter_count: number; analyzed_chapter_count: number };
type CreativeArtifact = { id: number; type: "script" | "storyboard" | string; title: string; content: Record<string, unknown>; created_at: string | null };
type Entity = {
  id: number;
  type: string;
  name: string;
  description: string;
  approved: boolean;
  visual_asset_id: number | null;
};
type Step = 1 | 2 | 3 | 4;

const stepNames = [
  { id: 1 as Step, title: "项目", description: "创建或选择创作项目" },
  { id: 2 as Step, title: "小说", description: "导入 TXT 小说文本" },
  { id: 3 as Step, title: "解析审核", description: "AI 识别并确认素材" },
  { id: 4 as Step, title: "剧本分镜", description: "生成剧本和镜头规划" },
];

const entityNames: Record<string, string> = {
  character: "人物",
  scene: "场景",
  prop: "道具",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [novelTitle, setNovelTitle] = useState("我的小说");
  const [selected, setSelected] = useState<number | null>(null);
  const [selectedTitle, setSelectedTitle] = useState("");
  const [novelId, setNovelId] = useState<number | null>(null);
  const [chapterCount, setChapterCount] = useState(0);
  const [chapterNo, setChapterNo] = useState(1);
  const [analysisOffset, setAnalysisOffset] = useState(0);
  const [processedChapters, setProcessedChapters] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [artifact, setArtifact] = useState("");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [artifacts, setArtifacts] = useState<CreativeArtifact[]>([]);
  const [visualPreview, setVisualPreview] = useState<{ assetId: number; url: string } | null>(null);
  const [imageStyle, setImageStyle] = useState("3d_anime");
  const [imagePrompt, setImagePrompt] = useState("");
  const [step, setStep] = useState<Step>(1);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const response = await fetch(`${API}/api/v1/projects`, { credentials: "include" });
      if (response.ok) setProjects(await response.json());
    } catch {
      setMessage("暂时无法读取项目，请检查网络连接。");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/v1/projects`, {
        method: "POST",
        credentials: "include",
        headers: await csrfHeaders(),
        body: JSON.stringify({ title: title.trim(), description: "手机端漫剧项目" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "创建项目失败");
      setSelected(data.id);
      setSelectedTitle(data.title || title.trim());
      setTitle("");
      setStep(2);
      setMessage("项目已创建。下一步请导入小说。");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建项目失败");
    } finally {
      setBusy(false);
    }
  }

  async function loadNovels(projectId: number) {
    try {
      const response = await fetch(`${API}/api/v1/projects/${projectId}/novels`, { credentials: "include" });
      if (response.ok) setNovels(await response.json());
      else setNovels([]);
    } catch { setNovels([]); }
  }

  async function loadArtifacts(projectId: number, targetNovelId: number) {
    try {
      const response = await fetch(`${API}/api/v1/projects/${projectId}/novels/${targetNovelId}/artifacts`, { credentials: "include" });
      if (response.ok) setArtifacts(await response.json());
      else setArtifacts([]);
    } catch { setArtifacts([]); }
  }

  async function selectNovel(novel: NovelSummary) {
    setNovelId(novel.id);
    setNovelTitle(novel.title);
    setChapterCount(novel.chapter_count);
    setAnalysisOffset(novel.analyzed_chapter_count || 0);
    setProcessedChapters(novel.analyzed_chapter_count || 0);
    setHasMore(novel.analysis_status !== "analyzed");
    setEntities([]);
    setArtifacts([]);
    setArtifact("");
    setStep(3);
    if (selected) void loadArtifacts(selected, novel.id);
    try {
      const response = await fetch(`${API}/api/v1/projects/${selected}/novels/${novel.id}/entities`, { credentials: "include" });
      if (response.ok) setEntities(await response.json());
    } catch { /* Existing novel can still be opened when analysis access is unavailable. */ }
    setMessage(`已打开小说：${novel.title}。可以继续解析或查看素材审核。`);
  }

  function selectProject(project: Project) {
    setSelected(project.id);
    setSelectedTitle(project.title);
    setNovelId(null);
    setChapterCount(0);
    setEntities([]);
    setArtifact("");
    setProcessedChapters(0);
    setStep(2);
    setMessage("已选择项目。可以导入小说，或导出该项目的数据。");
  }

  async function chooseNovelFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".txt")) {
      setMessage("目前支持 TXT 格式小说，请选择 .txt 文件。");
      event.target.value = "";
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setMessage("单个 TXT 文件暂时不能超过 5 MB。");
      event.target.value = "";
      return;
    }
    try {
      const buffer = await file.arrayBuffer();
      let value: string;
      try {
        value = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
      } catch {
        value = new TextDecoder("gb18030").decode(buffer);
      }
      setText(value);
      setNovelTitle(file.name.replace(/\.txt$/i, "") || "我的小说");
      setMessage(`已读取文件：${file.name}，共 ${value.length.toLocaleString()} 个字符。请确认后导入。`);
    } catch {
      setMessage("读取 TXT 文件失败，请尝试使用 UTF-8 编码另存后再导入。");
    }
    event.target.value = "";
  }

  async function importNovel(event: FormEvent) {
    event.preventDefault();
    if (!selected || !text.trim()) return;
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/v1/projects/${selected}/novels`, {
        method: "POST",
        credentials: "include",
        headers: await csrfHeaders(),
        body: JSON.stringify({ title: novelTitle.trim(), text }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "小说导入失败");
      setNovelId(data.novel_id);
      setChapterCount(data.chapter_count || 0);
      setAnalysisOffset(0);
      setProcessedChapters(0);
      setHasMore(true);
      setText("");
      setEntities([]);
      setArtifacts([]);
      setArtifact("");
      setStep(3);
      setMessage(`小说导入成功，已拆分为 ${data.chapter_count} 章。下一步进行 AI 解析。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "小说导入失败");
    } finally {
      setBusy(false);
    }
  }

  async function exportProject() {
    if (!selected) return;
    try {
      const response = await fetch(`${API}/api/v1/projects/${selected}/export`, { credentials: "include" });
      if (!response.ok) throw new Error("导出失败，请重新登录后再试");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `ai-comic-project-${selected}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("项目数据已导出。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出失败");
    }
  }

  async function approveEntity(entity: Entity) {
    if (!selected || !novelId) return;
    try {
      const response = await fetch(`${API}/api/v1/projects/${selected}/novels/${novelId}/entities/${entity.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: await csrfHeaders(),
        body: JSON.stringify({ approved: !entity.approved }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "审核状态更新失败");
      setEntities(items => items.map(item => item.id === entity.id ? { ...item, approved: data.approved } : item));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "审核失败");
    }
  }

  async function generateEntityImage(entity: Entity) {
    if (!selected || !novelId || !entity.approved) return;
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/v1/projects/${selected}/novels/${novelId}/entities/${entity.id}/generate-image`, {
        method: "POST",
        credentials: "include",
        headers: await csrfHeaders(),
        body: JSON.stringify({ style: imageStyle, extra_prompt: imagePrompt.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "图片生成失败");
      setEntities(items => items.map(item => item.id === entity.id ? { ...item, visual_asset_id: data.asset_id } : item));
      setMessage(`${entity.name} 的参考图已生成并保存到素材库。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "图片服务暂不可用");
    } finally {
      setBusy(false);
    }
  }

  async function previewVisual(assetId: number) {
    try {
      const response = await fetch(`${API}/api/v1/assets/${assetId}/download`, { credentials: "include" });
      if (!response.ok) throw new Error("图片读取失败");
      const url = URL.createObjectURL(await response.blob());
      setVisualPreview(current => {
        if (current) URL.revokeObjectURL(current.url);
        return { assetId, url };
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法预览图片");
    }
  }

  async function downloadVisual(assetId: number) {
    const response = await fetch(`${API}/api/v1/assets/${assetId}/download`, { credentials: "include" });
    if (!response.ok) {
      setMessage("图片下载失败。");
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `visual-reference-${assetId}.png`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function generate(kind: "analyze" | "script" | "storyboard") {
    if (!selected || !novelId) return;
    setBusy(true);
    try {
      const headers = await csrfHeaders();
      const path = kind === "analyze"
        ? `/api/v1/projects/${selected}/novels/${novelId}/analyze?limit=10&offset=${analysisOffset}`
        : `/api/v1/projects/${selected}/novels/${novelId}/${kind}`;
      const response = await fetch(`${API}${path}`, {
        method: "POST",
        credentials: "include",
        headers: kind === "analyze" ? { "X-CSRF-Token": headers["X-CSRF-Token"] } : headers,
        body: kind === "analyze" ? undefined : JSON.stringify({
          chapter_no: chapterNo,
          instructions: "请保留原作主线，适合手机横屏漫剧；镜头表达清晰，人物设定前后一致。",
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "AI 任务执行失败");
      setArtifact(JSON.stringify(data, null, 2));
      if (kind === "analyze") {
        setAnalysisOffset(data.next_offset);
        setProcessedChapters(value => value + (data.processed_chapters || 0));
        setHasMore(data.has_more);
        const entityResponse = await fetch(`${API}/api/v1/projects/${selected}/novels/${novelId}/entities`, { credentials: "include" });
        if (entityResponse.ok) setEntities(await entityResponse.json());
        setMessage(`本批解析完成：${data.processed_chapters} 章，新增识别素材 ${data.entities_created} 项。`);
      } else {
        await loadArtifacts(selected, novelId);
        setStep(4);
        setMessage(kind === "script" ? "漫剧剧本已生成，请检查内容。" : "分镜规划已生成，请检查镜头内容。");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "AI 服务暂不可用，请检查模型配置。");
    } finally {
      setBusy(false);
    }
  }

  const approvedCount = useMemo(() => entities.filter(item => item.approved).length, [entities]);
  const characterCount = entities.filter(item => item.type === "character").length;
  const sceneCount = entities.filter(item => item.type === "scene").length;
  const propCount = entities.filter(item => item.type === "prop").length;

  return (
    <main className="app-shell project-studio">
      <header className="topbar">
        <a className="brand" href="/workspace/">AI 漫剧大师</a>
        <span className="system-pill">创作项目</span>
      </header>

      <section className="account-wrap project-wrap">
        <div className="account-card project-card">
          <p className="eyebrow">STORY WORKSPACE · MOBILE</p>
          <h1>小说漫剧创作</h1>
          <p>按照步骤完成小说导入、AI 解析、素材审核和分镜规划。每一步都可以单独保存和检查。</p>

          <div className="project-stepper" aria-label="创作步骤">
            {stepNames.map(item => (
              <button type="button" key={item.id} className={`project-step ${step === item.id ? "active" : ""} ${step > item.id ? "done" : ""}`} onClick={() => {
                if (item.id === 1 || (item.id === 2 && selected) || (item.id === 3 && novelId) || (item.id === 4 && artifact)) setStep(item.id);
              }}>
                <span>{step > item.id ? "✓" : item.id}</span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </button>
            ))}
          </div>

          {step === 1 && (
            <section className="project-stage">
              <div className="project-stage-heading"><span>STEP 01</span><h2>创建或选择项目</h2></div>
              <form className="account-form" onSubmit={create}>
                <label>新项目名称<input required maxLength={120} value={title} onChange={event => setTitle(event.target.value)} placeholder="例如：我的第一部漫剧" /></label>
                <button className="account-submit" disabled={busy}>{busy ? "正在创建…" : "创建新项目"}</button>
              </form>
              <div className="project-list-heading"><h3>已有项目</h3><span>{projects.length} 个项目</span></div>
              {projects.length ? projects.map(project => (
                <button type="button" key={project.id} className={`portal-card project-select ${selected === project.id ? "selected" : ""}`} onClick={() => selectProject(project)}>
                  <strong>{project.title}</strong><p>{project.description || "暂无项目说明"}</p><small>状态：{project.status || "进行中"} · 点击继续创作</small>
                </button>
              )) : <p className="project-empty">还没有项目。先创建一个项目即可开始。</p>}
            </section>
          )}

          {step === 2 && (
            <section className="project-stage">
              <div className="project-stage-heading"><span>STEP 02</span><h2>导入小说</h2></div>
              <div className="project-current"><small>当前项目</small><strong>{selectedTitle}</strong><button type="button" onClick={() => setStep(1)}>切换项目</button></div>
              {novels.length > 0 && <div className="project-existing-novels"><div className="project-list-heading"><h3>继续之前的小说</h3><span>{novels.length} 部</span></div>{novels.map(novel => <button type="button" className="portal-card project-select" key={novel.id} onClick={() => void selectNovel(novel)}><strong>{novel.title}</strong><p>{novel.chapter_count} 章 · 已解析 {novel.analyzed_chapter_count || 0} 章 · {novel.analysis_status === "analyzed" ? "解析完成" : novel.analysis_status === "partially_analyzed" ? "部分解析" : "等待解析"}</p><small>点击继续处理</small></button>)}</div>}
              <form className="account-form" onSubmit={importNovel}>
                <label>小说名称<input required maxLength={200} value={novelTitle} onChange={event => setNovelTitle(event.target.value)} /></label>
                <label className="project-file-picker">选择 TXT 小说文件<input type="file" accept=".txt,text/plain" onChange={event => void chooseNovelFile(event)} /><small>支持 .txt，单文件最大 5 MB。也可以直接粘贴正文。</small></label>
                <label>小说正文<textarea required rows={9} maxLength={5000000} value={text} onChange={event => setText(event.target.value)} placeholder="将小说正文粘贴到这里，系统会自动识别常见章节标题…" /></label>
                <div className="project-text-meta">{text.length.toLocaleString()} / 5,000,000 字符</div>
                <button className="account-submit" disabled={busy || !text.trim()}>{busy ? "正在导入并拆分章节…" : "导入小说并拆分章节"}</button>
              </form>
              <p className="project-tip">提示：导入后会自动识别“第X章”“Chapter X”等常见章节标题。</p>
            </section>
          )}

          {step === 3 && novelId && (
            <section className="project-stage">
              <div className="project-stage-heading"><span>STEP 03</span><h2>AI 解析与素材审核</h2></div>
              <div className="project-stats">
                <div><strong>{chapterCount}</strong><span>小说章节</span></div>
                <div><strong>{processedChapters}</strong><span>已解析章节</span></div>
                <div><strong>{entities.length}</strong><span>识别素材</span></div>
                <div><strong>{approvedCount}</strong><span>已确认素材</span></div>
              </div>
              <button type="button" className="account-submit" disabled={busy || !hasMore} onClick={() => void generate("analyze")}>
                {busy ? "AI 正在解析，请稍候…" : hasMore ? `解析下一批章节（最多 10 章）` : "全部章节已完成解析"}
              </button>
              <p className="project-tip">AI 解析需要先在 AI 配置中心启用文本模型。每批最多解析 10 章，避免一次处理过多内容。</p>

              <div className="project-list-heading"><h3>识别素材审核</h3><span>人物 {characterCount} · 场景 {sceneCount} · 道具 {propCount}</span></div>
              {entities.length > 0 ? (
                <>
                  <label className="project-style-select">参考图风格<select value={imageStyle} onChange={event => setImageStyle(event.target.value)}>
                    <option value="realistic">真人电影风格</option>
                    <option value="3d_anime">3D 动漫电影风格</option>
                    <option value="2d_anime">2D 动漫风格</option>
                    <option value="guofeng">国风漫画风格</option>
                    <option value="ink">水墨动画风格</option>
                  </select></label>
                  <label className="project-style-select">视觉设计补充要求（可选）<textarea rows={3} maxLength={1000} value={imagePrompt} onChange={event => setImagePrompt(event.target.value)} placeholder="例如：采用冷色电影光影、细腻材质、统一服装配色；描述希望保持的视觉风格特征。" /></label>
                  {entities.map(entity => (
                    <article className="project-entity" key={entity.id}>
                      <div className="project-entity-top"><span>{entityNames[entity.type] || entity.type}</span><strong>{entity.name}</strong><em className={entity.approved ? "approved" : ""}>{entity.approved ? "已确认" : "待审核"}</em></div>
                      <p>{entity.description || "暂无详细描述，可结合原文核对。"}</p>
                      <div className="project-entity-actions">
                        <button type="button" className="account-submit" onClick={() => void approveEntity(entity)}>{entity.approved ? "取消确认" : "确认此素材"}</button>
                        <button type="button" className="account-submit" disabled={!entity.approved || busy} onClick={() => void generateEntityImage(entity)}>{entity.visual_asset_id ? "重新生成参考图" : "生成三视图 / 场景图"}</button>
                        {entity.visual_asset_id && <button type="button" className="account-submit secondary" onClick={() => void previewVisual(entity.visual_asset_id!)}>预览参考图</button>}
                        {entity.visual_asset_id && <button type="button" className="account-submit secondary" onClick={() => void downloadVisual(entity.visual_asset_id!)}>下载图片</button>}
                      </div>
                      {visualPreview?.assetId === entity.visual_asset_id && <div className="project-visual-preview"><img src={visualPreview.url} alt={`${entity.name}视觉参考图`} /><button type="button" className="account-submit secondary" onClick={() => setVisualPreview(current => { if (current) URL.revokeObjectURL(current.url); return null; })}>关闭预览</button></div>}
                    </article>
                  ))}
                </>
              ) : <p className="project-empty">尚未识别到素材。请先点击上方按钮运行 AI 章节解析。</p>}
              <button type="button" className="account-submit project-next" disabled={hasMore || processedChapters === 0} onClick={() => setStep(4)}>进入剧本与分镜制作 →</button>
            </section>
          )}

          {step === 4 && novelId && (
            <section className="project-stage">
              <div className="project-stage-heading"><span>STEP 04</span><h2>剧本与分镜规划</h2></div>
              <label className="project-style-select">目标章节<input type="number" min={1} max={Math.max(chapterCount, 1)} value={chapterNo} onChange={event => setChapterNo(Math.max(1, Number(event.target.value) || 1))} /></label>
              <p className="project-tip">建议先生成剧本，检查人物行为和剧情，再生成分镜规划。目标画面按手机横屏漫剧设计。</p>
              <div className="project-generation-actions">
                <button type="button" className="account-submit" disabled={busy} onClick={() => void generate("script")}>{busy ? "正在生成…" : "生成漫剧剧本"}</button>
                <button type="button" className="account-submit" disabled={busy} onClick={() => void generate("storyboard")}>{busy ? "正在生成…" : "生成分镜规划"}</button>
              </div>
              {artifacts.length > 0 && <div className="project-artifact-history"><div className="project-list-heading"><h3>已保存的生成成果</h3><span>{artifacts.length} 份</span></div>{artifacts.map(item => <details className="project-result" key={item.id}><summary>{item.type === "script" ? "漫剧剧本" : item.type === "storyboard" ? "分镜规划" : item.type} · {item.title}</summary><pre className="artifact-output">{JSON.stringify(item.content, null, 2)}</pre><small className="project-artifact-date">{item.created_at ? new Date(item.created_at).toLocaleString() : "已保存"}</small></details>)}</div>}{artifact && <details className="project-result"><summary>查看最近一次任务响应</summary><pre className="artifact-output">{artifact}</pre></details>}
              <button type="button" className="account-submit secondary" onClick={() => setStep(3)}>← 返回素材审核</button>
            </section>
          )}

          {selected && <button type="button" className="project-export" onClick={() => void exportProject()}>导出项目备份</button>}
          {message && <p className="account-message" role="status">{message}</p>}
        </div>
      </section>
    </main>
  );
}
