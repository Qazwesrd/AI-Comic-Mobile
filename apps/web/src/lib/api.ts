const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export async function csrfHeaders(): Promise<Record<string, string>> {
  const response = await fetch(`${API_BASE}/api/v1/auth/csrf`, { credentials: "include" });
  if (!response.ok) throw new Error("请先登录后再操作");
  const data = await response.json() as { csrf_token: string };
  return { "Content-Type": "application/json", "X-CSRF-Token": data.csrf_token };
}
