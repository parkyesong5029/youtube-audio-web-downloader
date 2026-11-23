import asyncio
import logging
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from youtube_utils import (
    build_content_disposition,
    extract_video_id,
    format_duration,
    normalize_video_url,
    sanitize_filename,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt_web_downloader")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
WORK_ROOT = Path(os.environ.get("YTWEB_WORK_DIR", "/tmp/yt_web_downloader_jobs"))
WORK_ROOT.mkdir(parents=True, exist_ok=True)
JOB_TTL_SECONDS = 45 * 60


class CancelledError(Exception):
    pass


@dataclass
class DownloadJob:
    job_id: str
    url: str
    video_id: str
    audio_format: str
    quality: str
    status: str = "queued"  # queued | downloading | converting | completed | failed | cancelled
    percent: int = 0
    status_text: str = "다운로드 준비 중..."
    title: str = ""
    file_name: Optional[str] = None
    file_path: Optional[Path] = None
    file_size: int = 0
    mime_type: str = "audio/mpeg"
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "video_id": self.video_id,
            "format": self.audio_format,
            "quality": self.quality,
            "status": self.status,
            "percent": self.percent,
            "status_text": self.status_text,
            "title": self.title,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "error": self.error,
            "download_url": f"/api/jobs/{self.job_id}/file" if self.status == "completed" else None,
            "stream_url": f"/api/jobs/{self.job_id}/stream" if self.status == "completed" else None,
        }


jobs: Dict[str, DownloadJob] = {}
jobs_lock = threading.Lock()


class CreateJobRequest(BaseModel):
    url: str
    format: str = "mp3"  # mp3 | m4a
    quality: str = "192"  # 192 | 320
    title_hint: Optional[str] = None


def cleanup_expired_jobs() -> None:
    now = time.time()
    expired_ids: List[str] = []
    with jobs_lock:
        for jid, job in list(jobs.items()):
            if now - job.created_at > JOB_TTL_SECONDS and job.status in {"completed", "failed", "cancelled"}:
                expired_ids.append(jid)
                jobs.pop(jid, None)
    for jid in expired_ids:
        job_dir = WORK_ROOT / jid
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


def apply_ssl_compat_opts(opts: dict) -> dict:
    """When SSL_CERT_FILE is configured (e.g. corporate/container CA), use system truststore."""
    if os.environ.get("SSL_CERT_FILE"):
        compat = list(opts.get("compat_opts", []))
        if "no-certifi" not in compat:
            compat.append("no-certifi")
        opts["compat_opts"] = compat
    return opts


def run_search_sync(query: str, limit: int) -> dict:
    vid = extract_video_id(query)
    if vid:
        norm_url = f"https://www.youtube.com/watch?v={vid}"
        opts = apply_ssl_compat_opts(
            {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "skip_download": True,
                "extract_flat": False,
            }
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(norm_url, download=False)
            thumb = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            return {
                "is_direct_url": True,
                "items": [
                    {
                        "id": vid,
                        "title": info.get("title") or "YouTube 영상",
                        "channel": info.get("uploader") or info.get("channel") or "",
                        "duration": info.get("duration"),
                        "duration_text": format_duration(info.get("duration")),
                        "thumbnail": thumb,
                        "url": norm_url,
                    }
                ],
            }
        except Exception as exc:
            logger.warning("Direct metadata fetch failed for %s: %s", vid, exc)
            return {
                "is_direct_url": True,
                "items": [
                    {
                        "id": vid,
                        "title": "선택한 YouTube 영상",
                        "channel": "YouTube",
                        "duration": None,
                        "duration_text": "",
                        "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                        "url": norm_url,
                    }
                ],
            }

    search_expr = f"ytsearch{limit}:{query}"
    opts = apply_ssl_compat_opts(
        {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(search_expr, download=False) or {}

    entries = data.get("entries") or []
    items = []
    for entry in entries:
        if not entry:
            continue
        eid = entry.get("id")
        if not eid or len(eid) != 11:
            continue
        thumbs = entry.get("thumbnails") or []
        thumb = (
            thumbs[-1].get("url")
            if thumbs and isinstance(thumbs[-1], dict) and thumbs[-1].get("url")
            else f"https://i.ytimg.com/vi/{eid}/hqdefault.jpg"
        )
        items.append(
            {
                "id": eid,
                "title": entry.get("title") or "제목 없음",
                "channel": entry.get("channel") or entry.get("uploader") or "",
                "duration": entry.get("duration"),
                "duration_text": format_duration(entry.get("duration")),
                "thumbnail": thumb,
                "url": f"https://www.youtube.com/watch?v={eid}",
            }
        )
    return {"is_direct_url": False, "items": items}


def run_download_job(job: DownloadJob) -> None:
    job_dir = WORK_ROOT / job.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    fmt = "m4a" if job.audio_format == "m4a" else "mp3"
    bitrate = "320" if job.quality == "320" else "192"
    mime_type = "audio/mp4" if fmt == "m4a" else "audio/mpeg"

    strategies = [
        None,
        {"youtube": {"player_client": ["android_vr", "android", "web"]}},
    ]

    last_err: Optional[Exception] = None

    for idx, extractor_args in enumerate(strategies):
        if job.cancel_event.is_set():
            job.status = "cancelled"
            job.status_text = "다운로드가 취소되었습니다."
            shutil.rmtree(job_dir, ignore_errors=True)
            return

        for f in job_dir.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)

        job.status = "downloading"
        job.percent = 0
        job.status_text = "유튜브 음원 정보를 분석하는 중..." if idx == 0 else "대체 경로로 음원 추출 재시도 중..."

        def progress_hook(d: dict) -> None:
            if job.cancel_event.is_set():
                raise CancelledError("사용자 요청으로 취소되었습니다.")
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                if total > 0:
                    pct = min(99, max(1, int(downloaded * 100 / total)))
                    job.percent = pct
                eta = d.get("eta")
                if eta:
                    job.status_text = f"음원 다운로드 중... ({job.percent}%, 약 {int(eta)}초 남음)"
                else:
                    job.status_text = f"음원 다운로드 중... ({job.percent}%)"
            elif status == "finished":
                job.status = "converting"
                job.percent = 95
                job.status_text = f"FFmpeg로 {fmt.upper()} 음원 변환 중..."

        def postprocessor_hook(d: dict) -> None:
            if job.cancel_event.is_set():
                raise CancelledError("사용자 요청으로 취소되었습니다.")
            if d.get("status") == "started":
                job.status = "converting"
                job.percent = 97
                job.status_text = f"{fmt.upper()} 메타데이터 정리 및 마무리 중..."

        ydl_opts = apply_ssl_compat_opts(
            {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "outtmpl": str(job_dir / "%(title).85s.%(ext)s"),
                "progress_hooks": [progress_hook],
                "postprocessor_hooks": [postprocessor_hook],
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": fmt,
                        "preferredquality": bitrate,
                    },
                    {
                        "key": "FFmpegMetadata",
                    },
                ],
            }
        )
        if extractor_args:
            ydl_opts["extractor_args"] = extractor_args

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                if info and info.get("title"):
                    job.title = str(info["title"])

            files = [p for p in job_dir.iterdir() if p.is_file() and p.stat().st_size > 0]
            output = next((p for p in files if p.suffix.lower() == f".{fmt}"), None)
            if output is None and files:
                output = max(files, key=lambda p: p.stat().st_size)

            if output is None:
                raise RuntimeError("변환된 음원 파일을 찾을 수 없습니다.")

            base_title = sanitize_filename(job.title or output.stem or "youtube_audio")
            ext = output.suffix.lstrip(".").lower() or fmt
            job.file_name = f"{base_title}.{ext}"
            job.file_path = output
            job.file_size = output.stat().st_size
            job.mime_type = mime_type
            job.percent = 100
            job.status = "completed"
            job.status_text = "변환이 완료되었습니다. 아래 버튼으로 저장하세요."
            return
        except CancelledError:
            job.status = "cancelled"
            job.status_text = "다운로드가 취소되었습니다."
            shutil.rmtree(job_dir, ignore_errors=True)
            return
        except Exception as exc:
            logger.warning("Job %s strategy #%d failed: %s", job.job_id, idx, exc)
            last_err = exc

    job.status = "failed"
    job.error = str(last_err or "음원 추출에 실패했습니다.")
    job.status_text = "음원 추출 중 오류가 발생했습니다."
    shutil.rmtree(job_dir, ignore_errors=True)


app = FastAPI(title="YouTube 음원 다운로더 (iOS / Web)", version="1.0.0")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "yt_dlp_version": yt_dlp.version.__version__,
    }


@app.get("/api/search")
async def search_youtube(
    q: str = Query(..., min_length=1, max_length=300),
    limit: int = Query(10, ge=1, le=20),
):
    cleanup_expired_jobs()
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="검색어 또는 유튜브 링크를 입력해 주세요.")
    try:
        result = await asyncio.to_thread(run_search_sync, query, limit)
        return result
    except Exception as exc:
        logger.exception("Search failed for query=%s", query)
        raise HTTPException(status_code=502, detail=f"유튜브 검색 중 오류가 발생했습니다: {exc}") from exc


@app.post("/api/jobs")
async def create_download_job(payload: CreateJobRequest):
    cleanup_expired_jobs()
    norm_url = normalize_video_url(payload.url)
    vid = extract_video_id(payload.url)
    if not norm_url or not vid:
        raise HTTPException(status_code=400, detail="유효한 유튜브 영상 링크가 아닙니다.")

    fmt = "m4a" if payload.format.lower() == "m4a" else "mp3"
    quality = "320" if str(payload.quality) == "320" else "192"

    job_id = uuid.uuid4().hex[:12]
    job = DownloadJob(
        job_id=job_id,
        url=norm_url,
        video_id=vid,
        audio_format=fmt,
        quality=quality,
        title=payload.title_hint or "",
    )
    with jobs_lock:
        jobs[job_id] = job

    worker = threading.Thread(target=run_download_job, args=(job,), daemon=True)
    worker.start()

    return job.to_dict()


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="다운로드 작업을 찾을 수 없거나 만료되었습니다.")
    return job.to_dict()


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return JSONResponse({"ok": True})
    job.cancel_event.set()
    return {"ok": True, "job_id": job_id}


@app.get("/api/jobs/{job_id}/file")
async def download_job_file(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job or job.status != "completed" or not job.file_path or not job.file_path.exists():
        raise HTTPException(status_code=404, detail="다운로드할 음원 파일이 없거나 만료되었습니다.")

    headers = {
        "Content-Disposition": build_content_disposition(job.file_name or "youtube_audio.mp3", "attachment"),
        "Cache-Control": "no-store",
    }
    return FileResponse(path=job.file_path, media_type=job.mime_type, headers=headers)


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_file(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job or job.status != "completed" or not job.file_path or not job.file_path.exists():
        raise HTTPException(status_code=404, detail="미리듣기 파일이 없거나 만료되었습니다.")

    headers = {
        "Content-Disposition": build_content_disposition(job.file_name or "youtube_audio.mp3", "inline"),
        "Cache-Control": "no-store",
    }
    return FileResponse(path=job.file_path, media_type=job.mime_type, headers=headers)


# Serve PWA static files and SPA root
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.api_route("/manifest.webmanifest", methods=["GET", "HEAD"])
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.api_route("/", methods=["GET", "HEAD"])
async def index():
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")
