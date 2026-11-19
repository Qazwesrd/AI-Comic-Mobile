from pathlib import Path
import re

config = Path("capacitor.config.ts").read_text(encoding="utf-8")
match = re.search(r'appId:\s*"([^"]+)"', config)
if not match:
    raise SystemExit("Could not determine Capacitor appId")
app_id = match.group(1)
package_path = Path("android/app/src/main/java") / Path(*app_id.split("."))
package_path.mkdir(parents=True, exist_ok=True)

plugin = package_path / "AIAppLauncherPlugin.java"
plugin.write_text("""package APP_PACKAGE;

import android.content.Intent;
import android.content.pm.PackageManager;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

@CapacitorPlugin(name = "AIAppLauncher")
public class AIAppLauncherPlugin extends Plugin {
    private static final Set<String> ALLOWED_PACKAGES = new HashSet<>(Arrays.asList(
        "com.openai.chatgpt",
        "com.deepseek.chat",
        "com.anthropic.claude",
        "com.larus.nova",
        "com.bytedance.dreamina",
        "com.lemon.lvoverseas"
    ));

    @PluginMethod
    public void isInstalled(PluginCall call) {
        String packageName = call.getString("packageName", "");
        if (!ALLOWED_PACKAGES.contains(packageName)) {
            call.reject("Unsupported AI client package");
            return;
        }
        PackageManager manager = getContext().getPackageManager();
        boolean installed;
        try {
            manager.getPackageInfo(packageName, 0);
            installed = true;
        } catch (PackageManager.NameNotFoundException exception) {
            installed = false;
        }
        JSObject result = new JSObject();
        result.put("installed", installed);
        call.resolve(result);
    }

    @PluginMethod
    public void launch(PluginCall call) {
        String packageName = call.getString("packageName", "");
        if (!ALLOWED_PACKAGES.contains(packageName)) {
            call.reject("Unsupported AI client package");
            return;
        }
        Intent launchIntent = getContext().getPackageManager().getLaunchIntentForPackage(packageName);
        if (launchIntent == null) {
            call.reject("AI client is not installed");
            return;
        }
        try {
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getActivity().startActivity(launchIntent);
            call.resolve();
        } catch (Exception exception) {
            call.reject("Unable to launch AI client", exception);
        }
    }
}
""".replace("APP_PACKAGE", app_id), encoding="utf-8")

main_activity = next(Path("android/app/src/main/java").rglob("MainActivity.java"), None)
if main_activity is None:
    raise SystemExit("Generated Android MainActivity.java was not found")
source = main_activity.read_text(encoding="utf-8")
if "AIAppLauncherPlugin.class" not in source:
    if "import android.os.Bundle;" not in source:
        source = source.replace("package " + app_id + ";", "package " + app_id + ";\n\nimport android.os.Bundle;")
    on_create = "public void onCreate(Bundle savedInstanceState) {"
    if on_create in source:
        source = source.replace(on_create, on_create + "\\n        registerPlugin(AIAppLauncherPlugin.class);", 1)
    else:
        marker = "public class MainActivity extends BridgeActivity {"
        if marker not in source:
            raise SystemExit("Unexpected MainActivity.java template")
        if "import android.os.Bundle;" not in source:
            source = source.replace("package " + app_id + ";", "package " + app_id + ";\\n\\nimport android.os.Bundle;")
        source = source.replace(marker, marker + """
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AIAppLauncherPlugin.class);
        super.onCreate(savedInstanceState);
    }
""")
    main_activity.write_text(source, encoding="utf-8")
print("Registered native Android AI app launcher plugin")
