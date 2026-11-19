import type { Metadata, Viewport } from "next";
import "./globals.css";
import ServiceWorkerRegistration from "./ServiceWorkerRegistration";
import NativeAppRedirect from "./NativeAppRedirect";

export const metadata: Metadata = {
  title: "AI 漫剧大师官方网站",
  description: "AI 漫剧大师官方产品介绍、功能讲解、使用教程、付款与软件下载。",
  applicationName: "AI 漫剧大师",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "AI 漫剧大师"
  }
};

export const viewport: Viewport = {
  themeColor: "#080817",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><ServiceWorkerRegistration /><NativeAppRedirect />{children}</body>
    </html>
  );
}
