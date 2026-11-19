import { apiUrl } from "./api-base";

export async function csrfHeaders(): Promise<Record<string, string>> {
  const response = await fetch(apiUrl("/api/v1/auth/csrf"), { credentials: "include" });
  if (!response.ok) throw new Error("请先登录后再操作");
  const data = await response.json() as { csrf_token: string };
  return { "Content-Type": "application/json", "X-CSRF-Token": data.csrf_token };
}
