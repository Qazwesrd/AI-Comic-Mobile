from pathlib import Path
import re

root = Path("android")
manifest = root / "app/src/main/AndroidManifest.xml"
main = root / "app/src/main/java/com/qazwesrd/aicomicmobile/MainActivity.kt"
plugin = root / "app/src/main/java/com/qazwesrd/aicomicmobile/ShareReceiverPlugin.kt"

if not manifest.exists() or not main.parent.exists():
    raise SystemExit("Capacitor Android project was not generated")

main.write_text("""package com.qazwesrd.aicomicmobile

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    companion object {
        @Volatile var pendingShareIntent: Intent? = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        registerPlugin(ShareReceiverPlugin::class.java)
        pendingShareIntent = intent
        super.onCreate(savedInstanceState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pendingShareIntent = intent
        bridge?.triggerJSEvent("androidShareReceived", "{}")
    }
}
""", encoding="utf-8")

plugin.write_text("""package com.qazwesrd.aicomicmobile

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import com.getcapacitor.*
import java.io.File
import java.io.FileOutputStream

@CapacitorPlugin(name = "ShareReceiver")
class ShareReceiverPlugin : Plugin() {
    @PluginMethod
    fun getPendingShares(call: PluginCall) {
        val intent = MainActivity.pendingShareIntent ?: activity.intent
        if (intent.action != Intent.ACTION_SEND && intent.action != Intent.ACTION_SEND_MULTIPLE) {
            call.resolve(JSObject().put("files", JSArray()))
            return
        }

        val uris = linkedSetOf<Uri>()
        intent.clipData?.let { clip ->
            for (index in 0 until clip.itemCount) clip.getItemAt(index).uri?.let(uris::add)
        }
        @Suppress("DEPRECATION")
        (intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM))?.let(uris::add)
        @Suppress("DEPRECATION")
        (intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM) ?: arrayListOf()).forEach(uris::add)

        val files = JSArray()
        try {
            for (uri in uris) {
                if (uri.scheme != "content") continue
                val name = queryName(uri)
                val mime = context.contentResolver.getType(uri) ?: "application/octet-stream"
                val target = File(cacheDir, "incoming-share").apply { mkdirs() }
                val safeName = name.replace(Regex("[^A-Za-z0-9._-]"), "_").take(120).ifBlank { "shared-file" }
                val output = File.createTempFile("share-", "-$safeName", target)
                var total = 0L
                context.contentResolver.openInputStream(uri)?.use { input ->
                    FileOutputStream(output).use { out ->
                        val buffer = ByteArray(1024 * 1024)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            total += count
                            if (total > 2L * 1024 * 1024 * 1024) throw IllegalArgumentException("Shared file exceeds 2 GiB")
                            out.write(buffer, 0, count)
                        }
                    }
                } ?: throw IllegalArgumentException("Cannot open shared content")
                files.put(JSObject()
                    .put("name", name)
                    .put("mimeType", mime)
                    .put("size", total)
                    .put("path", output.absolutePath))
            }
            MainActivity.pendingShareIntent = null
            call.resolve(JSObject().put("files", files))
        } catch (error: Exception) {
            call.reject(error.message ?: "Unable to import shared files")
        }
    }

    private fun queryName(uri: Uri): String {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) return cursor.getString(index) ?: "shared-file"
            }
        }
        return "shared-file"
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

print("Android share receiver source and SEND/SEND_MULTIPLE filters configured.")
