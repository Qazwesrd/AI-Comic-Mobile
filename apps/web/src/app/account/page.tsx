"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type License = {
  status: string;
  permanent: boolean;
  trial_expires_at: string | null;
  remaining_seconds: number;
  message: string;
};

export default function AccountPage() {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const [license, setLicense] = useState<License | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadLicense(token: string) {
    const deviceId = localStorage.getItem("ai-comic-device-id") || crypto.randomUUID();
    localStorage.setItem("ai-comic-device-id", deviceId);
    const platform = /iPhone|iPad|iPod/i.test(navigator.userAgent) ? "ios" :
      /Android/i.test(navigator.userAgent) ? "android" : "web";
    const response = await fetch(`${API}/api/v1/license/activate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ device_id: deviceId, platform })
    });
    if (!response.ok) throw new Error("设备激活失败，请稍后重试");
    setLicense(await response.json() as License);
  }

  useEffect(() => {
    const token = sessionStorage.getItem("ai-comic-access-token");
    if (token) void loadLicense(token).catch(() => sessionStorage.removeItem("ai-comic-access-token"));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setSuccess(false);
    try {
      const response = await fetch(`${API}/api/v1/auth/${mode === "register" ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "操作失败，请检查输入");
      sessionStorage.setItem("ai-comic-access-token", data.access_token);
      await loadLicense(data.access_token);
      setSuccess(true);
      setMessage("登录成功，账号与试用状态已连接。");
      setPassword("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "网络连接失败");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    sessionStorage.removeItem("ai-comic-access-token");
    setLicense(null);
    setMessage("已退出当前设备登录。");
    setSuccess(true);
  }

  const hours = license ? Math.floor(license.remaining_seconds / 3600) : 0;
  const minutes = license ? Math.floor((license.remaining_seconds % 3600) / 60) : 0;

  return (
    <main className="app-shell">
      <div className="ambient ambient-a" aria-hidden="true" />
      <div className="ambient ambient-b" aria-hidden="true" />
      <header className="topbar">
        <a className="brand" href="/"><span className="brand-mark">AI</span><span><strong>AI 漫剧</strong><small>MOBILE STUDIO</small></span></a>
        <span className="system-pill"><i /> 账号中心</span>
      </header>
      <section className="account-wrap">
        <a className="account-back" href="/">← 返回创作首页</a>
        <div className="account-card">
          <p className="eyebrow">IDENTITY & LICENSE</p>
          <h1>账号中心</h1>
          <p>注册或登录账号，激活设备并查看免费试用状态。</p>
          {!license && (
            <>
              <div className="account-tabs">
                <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>创建账号</button>
                <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>登录账号</button>
              </div>
              <form className="account-form" onSubmit={submit}>
                <label>邮箱地址<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" /></label>
                <label>密码（至少10位）<input type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} minLength={10} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} placeholder="请输入至少10位密码" /></label>
                <button className="account-submit" disabled={busy}>{busy ? "正在连接…" : mode === "register" ? "注册并开始试用" : "登录并查看授权"}</button>
              </form>
            </>
          )}
          <p className={`account-message ${success ? "ok" : ""}`}>{message}</p>
          {license && (
            <div className="account-status">
              <strong>{license.message}</strong><br />
              {license.status === "trial" && `剩余试用时间：${hours}小时 ${minutes}分钟`}
              {license.status === "expired" && "请前往官网购买永久授权。"}
              {license.status === "permanent" && "此账号已获得永久授权。"}
              <br /><button type="button" className="account-submit" onClick={logout}>退出登录</button>
            </div>
          )}
          <p className="account-message">提示：当前为开发联调界面，正式上线前会补充邮箱验证、找回密码和安全会话管理。</p>
        </div>
      </section>
    </main>
  );
}
