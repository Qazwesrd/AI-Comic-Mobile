"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Capacitor } from "@capacitor/core";
import { AppLauncher } from "@capacitor/app-launcher";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const OFFICIAL_SITE = "https://ai-comic-mobile.pages.dev/store/";
type License = {
  status: "not_activated" | "trial" | "expired" | "permanent";
  remaining_seconds: number;
  message: string;
};

const tabs = [
  { label: "创作", href: "/workspace/", symbol: "✦" },
  { label: "项目", href: "/projects/", symbol: "▤" },
  { label: "素材", href: "/assets/", symbol: "▧" },
  { label: "AI工具", href: "/ai-tools/", symbol: "◇" },
  { label: "账号", href: "/account/", symbol: "◎" },
];

function formatRemaining(seconds: number) {
  const safe = Math.max(0, seconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export default function NativeAppChrome() {
  const pathname = usePathname();
  const [native, setNative] = useState(false);
  const [license, setLicense] = useState<License | null>(null);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    const enabled = Capacitor.isNativePlatform();
    setNative(enabled);
    if (!enabled) return;
    document.body.classList.add("native-app");

    let cancelled = false;
    let countdown: number | undefined;
    async function refreshLicense() {
      try {
        const response = await fetch(`${API}/api/v1/license/status`, { credentials: "include" });
        if (!response.ok) return;
        const data = await response.json() as License;
        if (cancelled) return;
        setLicense(data);
        setRemaining(data.remaining_seconds || 0);
      } catch {
        // The server remains the authority; keep the last known status during short outages.
      }
    }
    void refreshLicense();
    const refresh = window.setInterval(() => { void refreshLicense(); }, 30000);
    countdown = window.setInterval(() => setRemaining(value => Math.max(0, value - 1)), 1000);
    return () => {
      cancelled = true;
      window.clearInterval(refresh);
      if (countdown) window.clearInterval(countdown);
      document.body.classList.remove("native-app");
    };
  }, []);

  if (!native) return null;

  async function openPayment() {
    try {
      await AppLauncher.openUrl({ url: OFFICIAL_SITE });
    } catch {
      window.open(OFFICIAL_SITE, "_blank", "noopener,noreferrer");
    }
  }

  const statusLabel = license?.status === "permanent"
    ? "永久授权"
    : license?.status === "trial"
      ? `试用剩余 ${formatRemaining(remaining)}`
      : license?.status === "expired"
        ? "试用已结束"
        : "尚未激活";

  return (
    <>
      <header className="native-app-header">
        <Link href="/workspace/" className="native-app-brand"><span className="native-app-logo">AI</span><span>漫剧大师</span></Link>
        <span className={`native-license-pill ${license?.status === "permanent" ? "is-permanent" : license?.status === "expired" ? "is-expired" : ""}`}>{statusLabel}</span>
      </header>
      {license?.status === "expired" && (
        <div className="native-expired-banner">
          <span>48小时试用已结束，创作功能已锁定。</span>
          <button type="button" onClick={() => void openPayment()}>前往官网付款</button>
        </div>
      )}
      <nav className="native-bottom-nav" aria-label="软件主导航">
        {tabs.map(tab => {
          const active = pathname === tab.href || pathname === tab.href.slice(0, -1) || (tab.href !== "/workspace/" && pathname.startsWith(tab.href));
          return (
            <Link href={tab.href} key={tab.href} className={active ? "active" : ""} aria-current={active ? "page" : undefined}>
              <span className="native-nav-symbol">{tab.symbol}</span><span>{tab.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
