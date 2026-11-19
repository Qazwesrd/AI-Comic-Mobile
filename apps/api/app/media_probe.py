from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def probe_video(path: str) -> dict | None:
    """Read trusted local media metadata with ffprobe; never executes user text."""
    executable = shutil.which("ffprobe")
    media_path = Path(path).resolve()
    if not executable or not media_path.is_file():
        return None
    try:
        result = subprocess.run(
            [
                executable, "-v", "error",
                "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate",
                "-of", "json", str(media_path),
            ],
            capture_output=True, text=True, timeout=20, check=True,
        )
        payload = json.loads(result.stdout)
        duration = float(payload.get("format", {}).get("duration", 0))
        video = next((s for s in payload.get("streams", []) if s.get("codec_type") == "video"), {})
        if duration <= 0 or not video:
            return None
        fps = video.get("avg_frame_rate")
        try:
            fps_value = str(float(Fraction(fps))) if fps and fps != "0/0" else None
        except (ValueError, ZeroDivisionError):
            fps_value = None
        return {
            "duration_ms": int(duration * 1000),
            "width": int(video["width"]) if video.get("width") else None,
            "height": int(video["height"]) if video.get("height") else None,
            "fps": fps_value,
        }
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None
