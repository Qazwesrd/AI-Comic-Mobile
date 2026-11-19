"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Device = { device_id: string; platform: string; first_seen_at: string; last_seen_at: string };\n\ntype License = {
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
  const [csrfToken, setCsrfToken] = useState("");\n  const [devices, setDevices] = useState<Device[]>([]);
  const [busy, setBusy] = useState(false);

  async function loadDevices() {\n    const response = await fetch(`${API}/api/v1/devices`, { credentials: "include" });\n    if (response.ok) setDevices(await response.json() as Device[]);\n  }\n\n  async function loadLicense(csrf: string) {
    const deviceId = localStorage.getItem("ai-comic-device-id") || crypto.randomUUID();
    localStorage.setItem("ai-comic-device-id", deviceId);
    const platform = /iPhone|iPad|iPod/i.test(navigator.userAgent) ? "ios" :
      /Android/i.test(navigator.userAgent) ? "android" : "web";
    const response = await fetch(`${API}/api/v1/license/activate`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ device_id: deviceId, platform })
    });
    if (!response.ok) throw new Error("设备激活失败，请稍后重试");
    setLicense(await response.json() as License);
  }

  useEffect(() => {
    let cancelled = false;
    async function restoreSession() {
      try {
        const me = await fetch(`${API}/api/v1/auth/me`, { credentials: "include" });
        if (!me.ok) return;
        const csrfResponse = await fetch(`${API}/api/v1/auth/csrf`, { credentials: "include" });
        if (!csrfResponse.ok) return;
        const data = await csrfResponse.json() as { csrf_token: string };
        if (cancelled) return;
        setCsrfToken(data.csrf_token);
        await loadLicense(data.csrf_token);\n        await loadDevices();
      } catch {
        if (!cancelled) setMessage("暂时无法连接账号服务，请检查网络后重试。");
      }
    }
    void restoreSession();
    return () => { cancelled = true; };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setSuccess(false);
    try {
      const response = await fetch(`${API}/api/v1/auth/${mode === "register" ? "register" : "login"}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "操作失败，请检查输入");
      const csrf = String(data.csrf_token || "");
      if (!csrf) throw new Error("安全会话建立失败，请重试");
      setCsrfToken(csrf);
      await loadLicense(csrf);\n      await loadDevices();
      setSuccess(true);
      setMessage("登录成功，账号与试用状态已连接。");
      setPassword("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "网络连接失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeDevice(deviceId: string) {\n    try {\n      const response = await fetch(`${API}/api/v1/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE", credentials: "include", headers: { "X-CSRF-Token": csrfToken } });\n      const data = await response.json();\n      if (!response.ok) throw new Error(data.detail || "解除设备失败");\n      setDevices(items => items.filter(item => item.device_id !== deviceId));\n      setMessage(data.message); setSuccess(true);\n    } catch (error) { setMessage(error instanceof Error ? error.message : "解除设备失败"); setSuccess(false); }\n  }\n\n  async function sendVerification() {
    try {
      const response = await fetch(`${API}/api/v1/auth/email/verify/request`, {
        method: "POST", credentials: "include", headers: { "X-CSRF-Token": csrfToken }
      });
      const data = await response.json();
      setMessage(response.ok ? data.message : data.detail || "发送失败");
      setSuccess(response.ok);
    } catch {
      setMessage("暂时无法发送验证邮件");
      setSuccess(false);
    }
  }

  async function logout() {
    try {
      const response = await fetch(`${API}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken }
      });
      if (!response.ok) throw new Error("退出失败，请重试");
      setLicense(null);
      setCsrfToken("");
      setMessage("已安全退出当前设备登录。");
      setSuccess(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "退出失败，请重试");
      setSuccess(false);
    }
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
              </form>\n              <a className="account-back" href="/forgot-password">忘记密码？点击找回</a>
            </>
          )}
          <p className={`account-message ${success ? "ok" : ""}`}>{message}</p>
          {license && (
            <div className="account-status">
              <strong>{license.message}</strong><br />\n              <h3>已绑定设备（最多3台）</h3>{devices.map(device => <div className="portal-card" key={device.device_id}><strong>{device.platform}</strong><small>{device.device_id}</small><button type="button" className="account-submit" onClick={() => void removeDevice(device.device_id)}>解除此设备</button></div>)}<br />\n              <button type="button" className="account-submit" onClick={() => void sendVerification()}>发送邮箱验证邮件</button><br />
              {license.status === "trial" && `剩余试用时间：${hours}小时 ${minutes}分钟`}
              {license.status === "expired" && "请前往官网购买永久授权。"}
              {license.status === "permanent" && "此账号已获得永久授权。"}
              <br /><button type="button" className="account-submit" onClick={() => void logout()}>退出登录</button>
            </div>
          )}
          <p className="account-message">登录凭据由 HttpOnly Cookie 保存；页面不会读取或保存访问令牌。</p>\n          <a className="account-back" href="/store">购买永久授权</a>　<a className="account-back" href="/orders">订单查询</a>
        </div>
      </section>
    </main>
  );
}
