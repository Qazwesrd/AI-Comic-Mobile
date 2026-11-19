"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
type Release = { release_id: number; platform: string; version: string; notes: string; minimum_supported_version: string };
type Gate = "loading" | "login" | "not_activated" | "trial" | "expired" | "permanent" | "error";

export default function DownloadsPage() {
  const [items, setItems] = useState<Release[]>([]);
  const [gate, setGate] = useState<Gate>("loading");
  const [message, setMessage] = useState("正在核验账号和永久授权…");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const me = await fetch(`${API}/api/v1/auth/me`, { credentials: "include" });
        if (!me.ok) {
          if (!cancelled) { setGate("login"); setMessage("请先登录官网账号。"); }
          return;
        }
        const licenseResponse = await fetch(`${API}/api/v1/license/status`, { credentials: "include" });
        if (!licenseResponse.ok) throw new Error("暂时无法核验授权状态");
        const license = await licenseResponse.json() as { status: Gate };
        if (license.status !== "permanent") {
          if (!cancelled) {
            setGate(license.status === "trial" || license.status === "expired" || license.status === "not_activated" ? license.status : "error");
            setMessage(license.status === "trial" ? "试用期间暂不开放正式版下载。试用结束后，请在官网完成付款。" :
              license.status === "expired" ? "48小时试用已结束。完成永久授权付款并经核实后，正式版下载链接才会显示。" :
              "账号尚未完成设备激活或永久授权。请先完成账号激活或付款。");
          }
          return;
        }
        const releases = await fetch(`${API}/api/v1/releases`);
        if (!releases.ok) throw new Error("版本服务暂不可用");
        const data = await releases.json() as Release[];
        if (!cancelled) {
          setItems(data);
          setGate("permanent");
          setMessage(data.length ? "永久授权已核验，以下为当前可下载版本。" : "永久授权已核验，但目前还没有发布可下载版本。");
        }
      } catch (error) {
        if (!cancelled) { setGate("error"); setMessage(error instanceof Error ? error.message : "读取失败"); }
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar"><a className="brand" href="/">AI 漫剧大师官网</a><span className="system-pill">正式版下载中心</span></header>
      <section className="account-wrap"><div className="account-card">
        <p className="eyebrow">AUTHORIZED DOWNLOADS</p><h1>正式版下载</h1>
        <p>正式版下载链接只会在服务器确认账号已获得永久授权后显示。试用期间或未付款账号不会显示下载地址。</p>
        <p className="account-message">{message}</p>
        {#if gate === "login"}
          <a className="primary-action" href="/account/">登录官网账号 ↗</a>
        {:else if gate === "trial" || gate === "expired" || gate === "not_activated"}
          <a className="primary-action" href="/store/">前往官网付款与授权 ↗</a>
          <a className="account-back" href="/account/">账号中心 / 激活设备</a>
        {:else if gate === "permanent"}
          {items.map((release) => (
            <article className="portal-card" key={release.release_id}>
              <strong>{release.platform.toUpperCase()} · {release.version}</strong>
              <p>{release.notes}</p><small>最低支持版本：{release.minimum_supported_version}</small>
              <a className="primary-action" href={`${API}/api/v1/releases/${release.release_id}/download`} rel="noopener noreferrer">下载正式版 ↗</a>
            </article>
          ))}
        {/if}
        <a className="account-back" href="/">返回官网首页</a>
      </div></section>
    </main>
  );
}
