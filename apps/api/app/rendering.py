from __future__ import annotations

from datetime import timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from .config import settings
from .database import SessionLocal
from .models import MediaAsset, RenderJob, utc_now


def run_render_job(job_id: int) -> None:
    db = SessionLocal()
    temporary_files: list[Path] = []
    output_path: Path | None = None
    try:
        job = db.get(RenderJob, job_id)
        if job is None or job.status not in {"queued", "running"}:
            return
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("服务器未安装 FFmpeg")
        job.status = "running"
        job.started_at = utc_now()
        db.commit()

        timeline = json.loads(job.timeline_json)
        shots = timeline["shots"]
        assets = []
        for shot in shots:
            asset = db.get(MediaAsset, int(shot["asset_id"]))
            if asset is None or asset.user_id != job.user_id or asset.asset_type not in {"image", "character", "scene", "prop"}:
                raise RuntimeError("分镜图片素材不存在或无权访问")
            path = Path(asset.storage_path).resolve()
            if not path.is_file():
                raise RuntimeError(f"图片素材文件丢失：{asset.file_name}")
            assets.append((path, float(shot["duration_seconds"])))

        audio_path = None
        audio_id = timeline.get("audio_asset_id")
        if audio_id is not None:
            audio = db.get(MediaAsset, int(audio_id))
            if audio is None or audio.user_id != job.user_id or audio.asset_type != "audio":
                raise RuntimeError("配音或背景音素材不存在或无权访问")
            audio_path = Path(audio.storage_path).resolve()
            if not audio_path.is_file():
                raise RuntimeError("音频文件不存在")

        root = Path(settings.media_root).expanduser().resolve()
        output_dir = root / "renders" / str(job.user_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        render_uuid = str(uuid4())
        output_path = output_dir / f"{render_uuid}.mp4"
        concat_path = output_dir / f"{render_uuid}.txt"
        temporary_files.append(concat_path)

        lines = []
        for path, duration in assets:
            escaped = path.as_posix().replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
            lines.append(f"duration {duration:.3f}")
        # Repeat the last frame so its requested duration is retained by the concat demuxer.
        escaped_last = assets[-1][0].as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped_last}'")
        concat_path.write_text("\n".join(lines), encoding="utf-8")

        width, height = timeline["resolution"].split("x")
        scale_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
        ]
        if audio_path:
            command.extend(["-stream_loop", "-1", "-i", str(audio_path)])
        command.extend([
            "-vf", scale_filter, "-r", str(timeline["fps"]),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ])
        if audio_path:
            command.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-shortest"])
        else:
            command.append("-an")
        command.append(str(output_path))
        result = subprocess.run(command, capture_output=True, text=True, timeout=3600, check=False)
        if result.returncode != 0 or not output_path.is_file():
            detail = (result.stderr or "FFmpeg 渲染失败")[-2500:]
            raise RuntimeError(detail)

        checksum = sha256()
        size = 0
        with output_path.open("rb") as file:
            while True:
                block = file.read(1024 * 1024)
                if not block:
                    break
                checksum.update(block)
                size += len(block)
        media = MediaAsset(
            asset_uuid=render_uuid, user_id=job.user_id, project_id=job.project_id,
            asset_type="video", title=f"分镜合成预览-{job.id}",
            file_name=f"storyboard-preview-{job.id}.mp4", mime_type="video/mp4",
            size_bytes=size, sha256=checksum.hexdigest(), storage_path=str(output_path),
            approved=False,
        )
        db.add(media)
        db.flush()
        job.output_asset_id = media.id
        job.status = "completed"
        job.completed_at = utc_now()
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(RenderJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)[-3000:]
            job.completed_at = utc_now()
            db.commit()
        if output_path:
            output_path.unlink(missing_ok=True)
    finally:
        for path in temporary_files:
            path.unlink(missing_ok=True)
        db.close()
