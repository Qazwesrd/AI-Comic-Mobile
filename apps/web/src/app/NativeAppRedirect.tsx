"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { Capacitor } from "@capacitor/core";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const appOnlyRoutes = [
  "/workspace", "/projects", "/ai-tools", "/ai-config", "/assets",
  "/render", "/video-editing", "/audio", "/publishing", "/admin"
];
const websiteOnlyRoutes = ["/store", "/orders", "/downloads"];
const nativePublicRoutes = ["/account", "/forgot-password", "/reset-password", "/verify-email"];

export default function NativeAppRedirect() {
  const pathname = usePathname();

  useEffect(() => {
    const path = pathname.replace(/\/$/, "") || "/";
    const native = Capacitor.isNativePlatform();

    if (!native) {
      if (appOnlyRoutes.some((route) => path === route || path.startsWith(route + "/"))) {
        window.location.replace("/");
      }
      return;
    }

    if (websiteOnlyRoutes.some((route) => path === route || path.startsWith(route + "/"))) {
      window.location.replace("/account/");
      return;
    }
    if (path === "/") {
      window.location.replace("/workspace/");
      return;
    }
    if (nativePublicRoutes.some((route) => path === route || path.startsWith(route + "/"))) return;

    let cancelled = false;
    async function enforceNativeLicense() {
      try {
        const session = await fetch(`${API}/api/v1/auth/me`, { credentials: "include" });
        if (!session.ok) {
          if (!cancelled) window.location.replace("/account/");
          return;
        }
        const response = await fetch(`${API}/api/v1/license/status`, { credentials: "include" });
        if (!response.ok) {
          if (!cancelled) window.location.replace("/account/");
          return;
        }
        const license = await response.json() as { status: string };
        if (!cancelled && license.status !== "trial" && license.status !== "permanent") {
          window.location.replace("/account/");
        }
      } catch {
        // Keep the current screen during a temporary network interruption.
      }
    }
    void enforceNativeLicense();
    return () => { cancelled = true; };
  }, [pathname]);

  return null;
}
