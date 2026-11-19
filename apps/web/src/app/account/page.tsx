"use client";

import { FormEvent, useEffect, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { AppLauncher } from "@capacitor/app-launcher";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Device = { device_id: string; platform: string; first_seen_at: string; last_seen_at: string };

type License = {
  status: string;
  permanent: boolean;
  trial_expires_at: string | null;
  remaining_seconds: number;
  message: string;
};

export default function AccountPage() {
  async function openOfficialPayment() {
    const url = "https://ai-comic-mobile.pages.dev/store/";
    if (isNativeApp) {
      try { await AppLauncher.openUrl({ url }); }
      catch { window.open(url, "_blank", "noopener,noreferrer"); }
    } else window.location.href = url;
  }
  const [isNativeApp, setIsNativeApp] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [registerMethod, setRegisterMethod] = useState<"email" | "phone">("email");
  const [loginMethod, setLoginMethod] = useState<"email" | "phone">("email");
  const [password, setPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const [license, setLicense] = useState<License | null>(null);
  const [csrfToken, setCsrfToken] = useState("");
  const [devices, setDevices] = useState<Device[]>([]);
  const [busy, setBusy] = useState(false);

  async function loadDevices() {
    const response = await fetch(`${API}/api/v1/devices`, { credentials: "include" });
    if (response.ok) setDevices(await response.json() as Device[]);
  }

  async function loadLicense(csrf: string) {
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
    setIsNativeApp(Capacitor.isNativePlatform());
    async function restoreSession() {
      try {
        const me = await fetch(`${API}/api/v1/auth/me`, { credentials: "include" });
        if (!me.ok) return;
        const csrfResponse = await fetch(`${API}/api/v1/auth/csrf`, { credentials: "include" });
        if (!csrfResponse.ok) return;
        const data = await csrfResponse.json() as { csrf_token: string };
        if (cancelled) return;
        setCsrfToken(data.csrf_token);
        await loadLicense(data.csrf_token);
        await loadDevices();
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
    const method = mode === "register" ? registerMethod : loginMethod;
    try {
      const endpoint = mode === "login"
        ? method === "phone" ? "/api/v1/auth/login/phone" : "/api/v1/auth/login"
        : method === "phone"
          ? codeSent ? "/api/v1/auth/register/phone/verify" : "/api/v1/auth/register/phone/send-code"
          : codeSent ? "/api/v1/auth/register/verify" : "/api/v1/auth/register";
      const body = mode === "login"
        ? method === "phone" ? { phone, password } : { email, password }
        : method === "phone"
          ? codeSent ? { phone, code: verificationCode, password } : { phone }
          : codeSent ? { email, code: verificationCode } : { email, password };
      const response = await fetch(`${API}${endpoint}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await response.json() as { detail?: string; message?: string; csrf_token?: string };
      if (!response.ok) throw new Error(data.detail || "操作失败，请检查输入");

      if (mode === "register" && !codeSent) {
        setCodeSent(true);
        setMessage(data.message || (method === "phone" ? "短信验证码已发送，请查收手机短信。" : "验证码已发送，请查收邮箱。"));
        setSuccess(true);
        return;
      }

      const csrf = String(data.csrf_token || "");
      if (!csrf) throw new Error("安全会话建立失败，请重试");
      setCsrfToken(csrf);
      await loadLicense(csrf);
      await loadDevices();
      setSuccess(true);
      setMessage(mode === "register" ? (method === "phone" ? "手机号验证成功，账号创建完成。" : "邮箱验证成功，账号创建完成。") : "登录成功，账号与试用状态已连接。");
      setPassword("");
      setVerificationCode("");
      setCodeSent(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "网络连接失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeDevice(deviceId: string) {
    try {
      const response = await fetch(`${API}/api/v1/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE", credentials: "include", headers: { "X-CSRF-Token": csrfToken } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "解除设备失败");
      setDevices(items => items.filter(item => item.device_id !== deviceId));
      setMessage(data.message); setSuccess(true);
    } catch (error) { setMessage(error instanceof Error ? error.message : "解除设备失败"); setSuccess(false); }
  }

  async function resendRegistrationCode() {
    setBusy(true);
    setMessage("");
    setSuccess(false);
    try {
      const endpoint = registerMethod === "phone"
        ? "/api/v1/auth/register/phone/send-code"
        : "/api/v1/auth/register/resend-code";
      const body = registerMethod === "phone" ? { phone } : { email, password };
      const response = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await response.json() as { detail?: string; message?: string };
      if (!response.ok) throw new Error(data.detail || "验证码发送失败");
      setMessage(data.message || "新的验证码已发送。");
      setSuccess(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "验证码发送失败");
      setSuccess(false);
    } finally {
      setBusy(false);
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
      setDevices([]);
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
        <a className="account-back" href={isNativeApp ? "/workspace/" : "/"}>← 返回{Capacitor.isNativePlatform() ? "软件工作台" : "官网首页"}</a>
        <div className="account-card">
          <p className="eyebrow">IDENTITY & LICENSE</p>
          <h1>账号中心</h1>
          <p>注册或登录账号，激活设备并查看免费试用状态。</p>
          {!license && (
            <>
              <div className="account-tabs">
                <button type="button" className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setCodeSent(false); setVerificationCode(""); setMessage(""); }}>创建账号</button>
                <button type="button" className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setCodeSent(false); setVerificationCode(""); setMessage(""); }}>登录账号</button>
              </div>
              <div className="account-tabs account-method-tabs">
                <button type="button" className={(mode === "register" ? registerMethod : loginMethod) === "email" ? "active" : ""} onClick={() => { if (mode === "register") setRegisterMethod("email"); else setLoginMethod("email"); setCodeSent(false); setVerificationCode(""); setMessage(""); }}>邮箱方式</button>
                <button type="button" className={(mode === "register" ? registerMethod : loginMethod) === "phone" ? "active" : ""} onClick={() => { if (mode === "register") setRegisterMethod("phone"); else setLoginMethod("phone"); setCodeSent(false); setVerificationCode(""); setMessage(""); }}>手机号方式</button>
              </div>
              <form className="account-form" onSubmit={submit}>
                {(mode === "register" ? registerMethod : loginMethod) === "phone"
                  ? <label>中国大陆手机号<input type="tel" inputMode="numeric" autoComplete="tel-national" pattern="1[3-9][0-9]{9}" maxLength={11} required value={phone} disabled={mode === "register" && codeSent} onChange={e => setPhone(e.target.value.replace(/\D/g, "").slice(0, 11))} placeholder="请输入11位手机号" /></label>
                  : <label>邮箱地址<input type="email" autoComplete="email" required value={email} disabled={mode === "register" && codeSent} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" /></label>}
                <label>密码（至少10位）<input type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} minLength={10} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} placeholder="请输入至少10位密码" /></label>
                {mode === "register" && codeSent && (
                  <label>{registerMethod === "phone" ? "短信验证码" : "邮箱验证码"}<input type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={verificationCode} onChange={e => setVerificationCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder={registerMethod === "phone" ? "请输入手机收到的6位数字验证码" : "请输入邮箱收到的6位数字验证码"} /></label>
                )}
                <button className="account-submit" disabled={busy}>{busy ? "正在处理…" : mode === "register" ? codeSent ? "验证并创建账号" : (registerMethod === "phone" ? "获取短信验证码" : "获取邮箱验证码") : "登录并查看授权"}</button>
                {mode === "register" && codeSent && (
                  <button type="button" className="account-submit" disabled={busy} onClick={() => void resendRegistrationCode()}>重新发送验证码</button>
                )}
              </form>
              <a className="account-back" href="/forgot-password">忘记密码？点击找回</a>
            </>
          )}
          <p className={`account-message ${success ? "ok" : ""}`}>{message}</p>
          {license && (
            <div className="account-status">
              <strong>{license.message}</strong><br />
              <h3>已绑定设备（最多3台）</h3>{devices.map(device => <div className="portal-card" key={device.device_id}><strong>{device.platform}</strong><small>{device.device_id}</small><button type="button" className="account-submit" onClick={() => void removeDevice(device.device_id)}>解除此设备</button></div>)}<br />
              {license.status === "trial" && `剩余试用时间：${hours}小时 ${minutes}分钟`}
              {license.status === "expired" && "48小时试用已结束。请前往官方网站完成付款，付款核实后即可恢复软件全部功能。"}
              {license.status === "permanent" && "此账号已获得永久授权。"}
              <br />{license.status === "expired" && <button type="button" className="account-submit" onClick={() => void openOfficialPayment()}>前往官网付款</button>}<button type="button" className="account-submit" onClick={() => void logout()}>退出登录</button>
            </div>
          )}
          <p className="account-message">登录凭据由 HttpOnly Cookie 保存；页面不会读取或保存访问令牌。</p>
          
        </div>
      </section>
    </main>
  );
}
