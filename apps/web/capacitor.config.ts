import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.qazwesrd.aicomicmobile",
  appName: "AI 漫剧手机版",
  webDir: "out",
  bundledWebRuntime: false,
  android: { allowMixedContent: false },
  ios: { contentInset: "automatic" }
};

export default config;
