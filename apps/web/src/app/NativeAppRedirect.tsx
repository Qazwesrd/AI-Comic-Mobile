"use client";
import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";

const appOnlyRoutes = [
  "/workspace", "/projects", "/ai-tools", "/ai-config", "/assets",
  "/render", "/video-editing", "/audio", "/publishing", "/admin"
];
const websiteOnlyRoutes = ["/store", "/orders", "/downloads"];

export default function NativeAppRedirect() {
  useEffect(() => {
    const path = window.location.pathname.replace(/\/$/, "") || "/";
    const native = Capacitor.isNativePlatform();
    if (native) {
      if (websiteOnlyRoutes.some((route) => path === route || path.startsWith(route + "/"))) {
        window.location.replace("/account/");
        return;
      }
      if (path === "/") window.location.replace("/workspace/");
      return;
    }
    if (appOnlyRoutes.some((route) => path === route || path.startsWith(route + "/"))) {
      window.location.replace("/");
    }
  }, []);
  return null;
}
