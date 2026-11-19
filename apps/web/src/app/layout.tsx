import type { Metadata, Viewport } from "next";
import "./globals.css";
import ServiceWorkerRegistration from "./ServiceWorkerRegistration";

export const metadata: Metadata = {
  title: "AI 漫剧手机版",
  description: "把小说变成漫剧的移动端 AI 创作工作台。",
  applicationName: "AI 漫剧手机版",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "AI 漫剧"
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
      <body><ServiceWorkerRegistration />{children}</body>
    </html>
  );
}
