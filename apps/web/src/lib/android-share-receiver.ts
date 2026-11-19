import { convertFileSrc, registerPlugin } from "@capacitor/core";

type NativeSharedFile = { name: string; mimeType: string; size: number; path: string };
type ShareReceiverPlugin = { getPendingShares(): Promise<{ files: NativeSharedFile[] }> };

const ShareReceiver = registerPlugin<ShareReceiverPlugin>("ShareReceiver");

export async function consumeAndroidSharedFiles(): Promise<File[]> {
  const result = await ShareReceiver.getPendingShares();
  const files: File[] = [];
  for (const item of result.files ?? []) {
    const response = await fetch(convertFileSrc(item.path));
    if (!response.ok) throw new Error(`无法读取分享文件：${item.name}`);
    const blob = await response.blob();
    files.push(new File([blob], item.name, { type: item.mimeType || blob.type || "application/octet-stream", lastModified: Date.now() }));
  }
  return files;
}
