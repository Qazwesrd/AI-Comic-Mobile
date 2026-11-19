from pathlib import Path
import re

manifest = Path("android/app/src/main/AndroidManifest.xml")
java_dir = Path("android/app/src/main/java/com/qazwesrd/aicomicmobile")
main = java_dir / "MainActivity.java"
plugin = java_dir / "ShareReceiverPlugin.java"

if not manifest.exists() or not main.exists():
    raise SystemExit("Capacitor Android project was not generated or MainActivity.java is missing")

main.write_text("""package com.qazwesrd.aicomicmobile;

import android.content.Intent;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    public static volatile Intent pendingShareIntent;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(ShareReceiverPlugin.class);
        pendingShareIntent = getIntent();
        super.onCreate(savedInstanceState);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        pendingShareIntent = intent;
        if (getBridge() != null) {
            getBridge().triggerJSEvent("androidShareReceived", "{}");
        }
    }
}
""", encoding="utf-8")

plugin.write_text("""package com.qazwesrd.aicomicmobile;

import android.content.ClipData;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import com.getcapacitor.*;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.Set;

@CapacitorPlugin(name = "ShareReceiver")
public class ShareReceiverPlugin extends Plugin {
    @PluginMethod
    public void getPendingShares(PluginCall call) {
        Intent intent = MainActivity.pendingShareIntent != null
            ? MainActivity.pendingShareIntent : getActivity().getIntent();
        if (intent == null || (!Intent.ACTION_SEND.equals(intent.getAction())
            && !Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction()))) {
            JSObject empty = new JSObject();
            empty.put("files", new JSArray());
            call.resolve(empty);
            return;
        }

        Set<Uri> uris = new LinkedHashSet<>();
        ClipData clip = intent.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++) {
                Uri uri = clip.getItemAt(i).getUri();
                if (uri != null) uris.add(uri);
            }
        }
        if (Intent.ACTION_SEND.equals(intent.getAction())) {
            Uri single = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (single != null) uris.add(single);
        } else {
            ArrayList<Uri> multiple = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (multiple != null) uris.addAll(multiple);
        }

        JSArray files = new JSArray();
        try {
            File folder = new File(getContext().getCacheDir(), "incoming-share");
            if (!folder.exists() && !folder.mkdirs()) throw new IllegalStateException("Cannot create share cache");
            for (Uri uri : uris) {
                if (!"content".equals(uri.getScheme())) continue;
                String name = queryName(uri);
                String mime = getContext().getContentResolver().getType(uri);
                if (mime == null) mime = "application/octet-stream";
                String safeName = name.replaceAll("[^A-Za-z0-9._-]", "_");
                if (safeName.length() > 120) safeName = safeName.substring(0, 120);
                File output = File.createTempFile("share-", "-" + safeName, folder);
                long total = 0;
                try (InputStream input = getContext().getContentResolver().openInputStream(uri);
                     FileOutputStream out = new FileOutputStream(output)) {
                    if (input == null) throw new IllegalArgumentException("Cannot open shared content");
                    byte[] buffer = new byte[1024 * 1024];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        total += count;
                        if (total > 2L * 1024 * 1024 * 1024) {
                            output.delete();
                            throw new IllegalArgumentException("Shared file exceeds 2 GiB");
                        }
                        out.write(buffer, 0, count);
                    }
                }
                JSObject item = new JSObject();
                item.put("name", name);
                item.put("mimeType", mime);
                item.put("size", total);
                item.put("path", output.getAbsolutePath());
                files.put(item);
            }
            MainActivity.pendingShareIntent = null;
            getActivity().setIntent(new android.content.Intent());
            JSObject result = new JSObject();
            result.put("files", files);
            call.resolve(result);
        } catch (Exception error) {
            call.reject(error.getMessage() == null ? "Unable to import shared files" : error.getMessage(), error);
        }
    }

    @PluginMethod
    public void readChunk(PluginCall call) {
        String path = call.getString("path");
        Integer offset = call.getInt("offset");
        Integer length = call.getInt("length");
        if (path == null || offset == null || length == null || offset < 0 || length < 1 || length > 8 * 1024 * 1024) {
            call.reject("Invalid shared-file chunk request");
            return;
        }
        try {
            File allowedFolder = new File(getContext().getCacheDir(), "incoming-share").getCanonicalFile();
            File file = new File(path).getCanonicalFile();
            if (!file.getPath().startsWith(allowedFolder.getPath() + File.separator) || !file.isFile()
                || (long) offset + length > file.length()) {
                call.reject("Shared-file path or chunk is invalid");
                return;
            }
            try (java.io.RandomAccessFile input = new java.io.RandomAccessFile(file, "r")) {
                byte[] bytes = new byte[length];
                input.seek(offset);
                input.readFully(bytes);
                JSObject result = new JSObject();
                result.put("data", android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP));
                call.resolve(result);
            }
        } catch (Exception error) {
            call.reject(error.getMessage() == null ? "Unable to read shared-file chunk" : error.getMessage(), error);
        }
    }

    private String queryName(Uri uri) {
        try (Cursor cursor = getContext().getContentResolver().query(
            uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0 && cursor.getString(index) != null) return cursor.getString(index);
            }
        } catch (Exception ignored) { }
        return "shared-file";
    }
}
""", encoding="utf-8")

text = manifest.read_text(encoding="utf-8")
if "android.intent.action.SEND" not in text:
    filters = """
            <intent-filter>
                <action android:name="android.intent.action.SEND" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:mimeType="image/*" />
                <data android:mimeType="video/*" />
                <data android:mimeType="audio/*" />
                <data android:mimeType="text/*" />
                <data android:mimeType="application/pdf" />
            </intent-filter>
            <intent-filter>
                <action android:name="android.intent.action.SEND_MULTIPLE" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:mimeType="image/*" />
                <data android:mimeType="video/*" />
                <data android:mimeType="audio/*" />
                <data android:mimeType="text/*" />
                <data android:mimeType="application/pdf" />
            </intent-filter>
"""
    match = re.search(r'(<activity[^>]*android:name="[^"]*MainActivity"[^>]*>)(.*?)(</activity>)', text, re.S)
    if not match:
        raise SystemExit("MainActivity declaration not found in AndroidManifest.xml")
    text = text[:match.start()] + match.group(1) + match.group(2) + filters + match.group(3) + text[match.end():]
    manifest.write_text(text, encoding="utf-8")

print("Android share receiver configured.")
