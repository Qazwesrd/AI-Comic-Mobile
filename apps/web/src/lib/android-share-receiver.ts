import { registerPlugin } from "@capacitor/core";

export type AndroidSharedFile = {
  name: string;
  mimeType: string;
  size: number;
  path: string;
  type: string;
};

type ShareReceiverPlugin = {
  getPendingShares(): Promise<{ files: Array<Omit<AndroidSharedFile, "type">> }>;
  readChunk(options: { path: string; offset: number; length: number }): Promise<{ data: string }>;
};

const ShareReceiver = registerPlugin<ShareReceiverPlugin>("ShareReceiver");

export async function consumeAndroidSharedFiles(): Promise<AndroidSharedFile[]> {
  const result = await ShareReceiver.getPendingShares();
  return (result.files ?? []).map(file => ({ ...file, type: file.mimeType || "application/octet-stream" }));
}

export async function readAndroidSharedChunk(file: AndroidSharedFile, offset: number, length: number): Promise<Blob> {
  const result = await ShareReceiver.readChunk({ path: file.path, offset, length });
  const binary = atob(result.data);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: file.type });
}
