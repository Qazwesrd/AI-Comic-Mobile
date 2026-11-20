const STORAGE_KEY = "ai-comic-api-base-url";

function normalizeBase(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  let parsed: URL;
  try { parsed = new URL(trimmed); } catch { throw new Error("请输入完整地址，例如 https://api.example.com"); }
  if (!["https:", "http:"].includes(parsed.protocol) || !parsed.hostname) {
    throw new Error("服务器地址必须以 https:// 或 http:// 开头");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash || (parsed.pathname !== "/" && parsed.pathname !== "")) {
    throw new Error("请只填写 API 根地址，不要填写账号密码、路径、参数或锚点");
  }
  if (parsed.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(parsed.hostname)) {
    throw new Error("正式手机连接请使用 HTTPS 地址");
  }
  return parsed.origin;
}

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) return normalizeBase(saved);
    } catch { /* storage may be unavailable in restricted WebViews */ }
  }
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL || "";
  try { return normalizeBase(configured); } catch { return ""; }
}

export function setApiBaseUrl(value: string): string {
  const normalized = normalizeBase(value);
  if (!normalized) throw new Error("请先填写服务器地址");
  if (typeof window === "undefined") throw new Error("当前环境无法保存服务器设置");
  window.localStorage.setItem(STORAGE_KEY, normalized);
  return normalized;
}

export function apiUrl(path: string): string {
  if (!path.startsWith("/")) throw new Error("API 路径必须以 / 开头");
  const base = getApiBaseUrl();
  return base ? base + path : path;
}
