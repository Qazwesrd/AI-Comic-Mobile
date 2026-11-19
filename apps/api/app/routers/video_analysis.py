from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import MediaAsset, VideoEditProject, VideoEditSource, VideoEditTimeline
from ..security_services import audit
from .platform import require_active_license

router = APIRouter(prefix="/api/v1/video-editing", tags=["video-editing-analysis"])


def _owned_project(db: Session, project_id: int, user_id: int):
    project = db.scalar(select(VideoEditProject).where(
        VideoEditProject.id == project_id, VideoEditProject.user_id == user_id
    ))
    if project is None:
        raise HTTPException(status_code=404, detail="剪辑项目不存在")
    return project


@router.post("/projects/{project_id}/sources/{source_id}/keyframes")
def extract_keyframes(
    project_id: int, source_id: int,
    interval_seconds: int = Query(default=5, ge=1, le=30),
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    """Extract reviewable still frames; this does not claim AI has understood them."""
    project = _owned_project(db, project_id, user.id)
    source = db.scalar(select(VideoEditSource).where(
        VideoEditSource.id == source_id, VideoEditSource.project_id == project.id,
        VideoEditSource.user_id == user.id,
    ))
    if source is None:
        raise HTTPException(status_code=404, detail="视频素材不存在")
    asset = db.scalar(select(MediaAsset).where(
        MediaAsset.id == source.asset_id, MediaAsset.user_id == user.id,
        MediaAsset.asset_type == "video",
    ))
    if asset is None:
        raise HTTPException(status_code=404, detail="源视频不存在")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(status_code=503, detail="服务器未安装 FFmpeg，无法提取关键帧")
    video_path = Path(asset.storage_path).resolve()
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="源视频文件不存在")
    duration_ms = source.duration_ms
    if not duration_ms:
        raise HTTPException(status_code=422, detail="视频时长尚未探测，请重新添加或检查视频文件")
    timestamps = list(range(0, duration_ms, interval_seconds * 1000))[:24]
    root = Path(settings.media_root).expanduser().resolve()
    output_dir = root / "video-keyframes" / str(user.id) / str(project.id) / str(source.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for timestamp_ms in timestamps:
        frame_uuid = str(uuid4())
        output_path = output_dir / f"{frame_uuid}.jpg"
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{timestamp_ms / 1000:.3f}", "-i", str(video_path),
             "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "3", str(output_path)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if result.returncode != 0 or not output_path.is_file():
            continue
        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        size = output_path.stat().st_size
        frame_asset = MediaAsset(
            asset_uuid=frame_uuid, user_id=user.id, project_id=None,
            asset_type="image", title=f"{asset.title} - {timestamp_ms // 1000}s关键帧",
            file_name=f"keyframe-{timestamp_ms // 1000}s.jpg", mime_type="image/jpeg",
            size_bytes=size, sha256=digest, storage_path=str(output_path), approved=False,
        )
        db.add(frame_asset)
        db.flush()
        frames.append({"asset_id": frame_asset.id, "timestamp_ms": timestamp_ms,
                       "file_name": frame_asset.file_name, "approved": False})
    if not frames:
        db.rollback()
        raise HTTPException(status_code=422, detail="没有成功提取关键帧，请检查视频编码")
    db.commit()
    audit(db, "video_keyframes_extracted", "video_edit_source", str(source.id), user.id)
    return {
        "project_id": project.id, "source_id": source.id, "interval_seconds": interval_seconds,
        "frames": frames, "count": len(frames), "requires_user_review": True,
        "note": "关键帧已作为待审核图片素材保存；本接口只提取画面，不代表已完成 AI 视觉理解。",
    }


class ExportRequest(BaseModel):
    resolution: str = Field(default="1920x1080", pattern=r"^(1280x720|1920x1080|1080x1920|1080x1080)$")
    fps: int = Field(default=30, ge=24, le=60)
    music_asset_id: int | None = None


@router.post("/projects/{project_id}/export")
def export_video(
    project_id: int, payload: ExportRequest,
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    """Render the approved video track to MP4 using FFmpeg; source files remain untouched."""
    project = _owned_project(db, project_id, user.id)
    timeline = db.scalar(select(VideoEditTimeline).where(
        VideoEditTimeline.project_id == project.id, VideoEditTimeline.user_id == user.id
    ).order_by(desc(VideoEditTimeline.revision)).limit(1))
    if timeline is None:
        raise HTTPException(status_code=422, detail="请先保存时间线")
    tracks = json.loads(timeline.timeline_json).get("tracks", [])
    video_track = next((track for track in tracks if track.get("type") == "video"), None)
    clips = (video_track or {}).get("clips", [])
    if not clips:
        raise HTTPException(status_code=422, detail="视频轨道没有可导出的片段")
    if len(clips) > 100:
        raise HTTPException(status_code=422, detail="单次最多导出100个视频片段")
    ordered = sorted(clips, key=lambda item: int(item.get("position_ms", 0)))
    cursor_ms = 0
    for clip in ordered:
        position_ms = int(clip.get("position_ms", 0))
        duration_ms = int(clip["end_ms"]) - int(clip["start_ms"])
        if position_ms < cursor_ms:
            raise HTTPException(status_code=422, detail="当前导出不支持视频片段重叠，请调整时间线位置")
        cursor_ms = position_ms + duration_ms
    total_ms = cursor_ms
    if total_ms <= 0 or total_ms > 600_000:
        raise HTTPException(status_code=422, detail="导出总时长必须在10分钟以内")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(status_code=503, detail="服务器未安装 FFmpeg，暂时不能导出视频")

    source_rows = db.scalars(select(VideoEditSource).where(
        VideoEditSource.project_id == project.id, VideoEditSource.user_id == user.id
    )).all()
    source_map = {row.id: row for row in source_rows}
    inputs: list[str] = []
    filters: list[str] = []
    segment_labels: list[str] = []
    cursor_ms = 0
    gap_index = 0
    width, height = payload.resolution.split("x")
    for index, clip in enumerate(ordered):
        source = source_map.get(int(clip.get("source_id") or 0))
        if source is None:
            raise HTTPException(status_code=422, detail="时间线引用了不属于当前项目的素材")
        asset = db.scalar(select(MediaAsset).where(
            MediaAsset.id == source.asset_id, MediaAsset.user_id == user.id,
        ))
        if asset is None:
            raise HTTPException(status_code=404, detail="时间线源素材不存在")
        path = Path(asset.storage_path).resolve()
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"源视频文件不存在：{asset.file_name}")
        start_ms, end_ms = int(clip["start_ms"]), int(clip["end_ms"])
        if start_ms < 0 or end_ms <= start_ms or (source.duration_ms and end_ms > source.duration_ms):
            raise HTTPException(status_code=422, detail="时间线包含超出源视频范围的片段")
        position_ms = int(clip.get("position_ms", 0))
        if position_ms > cursor_ms:
            gap_label = f"gap{gap_index}"
            gap_duration = (position_ms - cursor_ms) / 1000
            filters.append(f"color=c=black:s={width}x{height}:r={payload.fps}:d={gap_duration:.3f},format=yuv420p,setpts=PTS-STARTPTS[{gap_label}]")
            segment_labels.append(f"[{gap_label}]")
            gap_index += 1
        inputs.extend(["-ss", f"{start_ms / 1000:.3f}", "-t", f"{(end_ms - start_ms) / 1000:.3f}", "-i", str(path)])
        duration_seconds = (end_ms - start_ms) / 1000
        fade_duration = min(0.35, duration_seconds / 2) if clip.get("transition") == "fade" else 0
        fade_filters = (
            f",fade=t=in:st=0:d={fade_duration:.3f},"
            f"fade=t=out:st={max(0, duration_seconds - fade_duration):.3f}:d={fade_duration:.3f}"
            if fade_duration else ""
        )
        filters.append(
            f"[{index}:v:0]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={payload.fps},"
            f"format=yuv420p,setpts=PTS-STARTPTS{fade_filters}[v{index}]"
        )
        segment_labels.append(f"[v{index}]")
        cursor_ms = position_ms + end_ms - start_ms
    concat_inputs = "".join(segment_labels)
    filters.append(f"{concat_inputs}concat=n={len(segment_labels)}:v=1:a=0[outv]")

    music_path = None
    if payload.music_asset_id is not None:
        music = db.scalar(select(MediaAsset).where(
            MediaAsset.id == payload.music_asset_id, MediaAsset.user_id == user.id,
            MediaAsset.asset_type == "audio",
        ))
        if music is None:
            raise HTTPException(status_code=404, detail="背景音乐素材不存在或无权访问")
        music_path = Path(music.storage_path).resolve()
        if not music_path.is_file():
            raise HTTPException(status_code=404, detail="背景音乐文件不存在")

    root = Path(settings.media_root).expanduser().resolve()
    output_dir = root / "video-edits" / str(user.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_uuid = str(uuid4())
    output_path = output_dir / f"{output_uuid}.mp4"
    subtitle_asset = None
    subtitle_track = next((track for track in tracks if track.get("type") == "subtitle"), None)
    subtitle_clips = (subtitle_track or {}).get("clips", [])
    if subtitle_clips:
        def srt_time(milliseconds: int) -> str:
            hours, remainder = divmod(milliseconds, 3_600_000)
            minutes, remainder = divmod(remainder, 60_000)
            seconds, millis = divmod(remainder, 1000)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
        subtitle_lines = []
        for number, item in enumerate(sorted(subtitle_clips, key=lambda x: int(x.get("start_ms", 0))), 1):
            start_ms, end_ms = int(item.get("start_ms", 0)), int(item.get("end_ms", 0))
            text = str(item.get("text") or "").strip()
            if not text or start_ms < 0 or end_ms <= start_ms or end_ms > total_ms:
                raise HTTPException(status_code=422, detail="字幕内容或时间范围无效，字幕必须位于成片时长内")
            subtitle_lines.extend([str(number), f"{srt_time(start_ms)} --> {srt_time(end_ms)}", text, ""])
        subtitle_path = output_dir / f"{output_uuid}.srt"
        subtitle_path.write_text("\n".join(subtitle_lines), encoding="utf-8-sig")
        subtitle_bytes = subtitle_path.read_bytes()
        subtitle_asset = MediaAsset(
            asset_uuid=str(uuid4()), user_id=user.id, project_id=None,
            asset_type="subtitle", title=f"{project.title} - 字幕文件",
            file_name=f"{project.title[:70]}-subtitles.srt", mime_type="application/x-subrip",
            size_bytes=len(subtitle_bytes), sha256=hashlib.sha256(subtitle_bytes).hexdigest(),
            storage_path=str(subtitle_path), approved=False,
        )
        db.add(subtitle_asset)
        db.flush()
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *inputs]
    if music_path:
        command.extend(["-stream_loop", "-1", "-i", str(music_path)])
    command.extend([
        "-filter_complex", ";".join(filters), "-map", "[outv]",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ])
    if music_path:
        music_input_index = len(ordered)
        command.extend(["-map", f"{music_input_index}:a:0", "-c:a", "aac", "-shortest"])
    else:
        command.append("-an")
    command.append(str(output_path))
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3600, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=f"视频导出执行失败：{str(exc)[:500]}")
    if result.returncode != 0 or not output_path.is_file():
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=(result.stderr or "FFmpeg 视频导出失败")[-1500:])
    digest = hashlib.sha256()
    size = 0
    with output_path.open("rb") as file:
        while True:
            block = file.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            size += len(block)
    output = MediaAsset(
        asset_uuid=output_uuid, user_id=user.id, project_id=None,
        asset_type="video", title=f"{project.title} - 剪辑成片",
        file_name=f"{project.title[:80]}-edited.mp4", mime_type="video/mp4",
        size_bytes=size, sha256=digest.hexdigest(), storage_path=str(output_path), approved=False,
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    audit(db, "video_edit_export_completed", "media_asset", str(output.id), user.id)
    return {
        "asset_id": output.id, "file_name": output.file_name, "size_bytes": size,
        "resolution": payload.resolution, "fps": payload.fps, "duration_ms": total_ms,
        "status": "completed", "approved": False,
        "subtitle_asset_id": subtitle_asset.id if subtitle_asset else None,
        "note": "成片已保存到素材库；支持视频轨道剪辑、可选循环背景音乐和独立 SRT 字幕文件，原始素材不会覆盖。字幕文件可导入剪辑软件继续调整。",
    }
