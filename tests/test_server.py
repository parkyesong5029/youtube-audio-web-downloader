import base64
from pathlib import Path

from fastapi.testclient import TestClient

from server import app, resolve_cookiefile
from youtube_utils import (
    build_content_disposition,
    extract_video_id,
    format_duration,
    normalize_video_url,
    sanitize_filename,
)

client = TestClient(app)


def test_extract_video_id_and_normalize():
    assert extract_video_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=12") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/abcDEF12345?si=test") == "abcDEF12345"
    assert extract_video_id("https://www.youtube.com/shorts/xyz12345678") == "xyz12345678"
    assert extract_video_id("그냥 노래 제목") is None
    assert normalize_video_url("https://youtu.be/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_sanitize_filename_and_ios_content_disposition():
    safe = sanitize_filename('아이유(IU) : 밤편지 / *Official*?')
    assert "아이유(IU)" in safe
    assert ":" not in safe and "/" not in safe and "*" not in safe

    header = build_content_disposition("아이유 - 밤편지.mp3", "attachment")
    assert header.startswith("attachment;")
    assert "filename*=UTF-8''" in header
    assert "%EC%95%84%EC%9D%B4%EC%9C%A0" in header


def test_format_duration():
    assert format_duration(215) == "3:35"
    assert format_duration(3665) == "1:01:05"
    assert format_duration(None) == ""


def test_health_and_static_routes():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["ffmpeg"] is True
    assert "cookies_configured" in body

    root = client.get("/")
    assert root.status_code == 200
    assert "YouTube 음원 다운로더" in root.text
    assert 'id="errorModal"' in root.text

    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"


def test_resolve_cookiefile_from_file_and_env(tmp_path, monkeypatch):
    monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
    monkeypatch.delenv("YT_COOKIES_B64", raising=False)
    monkeypatch.delenv("YT_COOKIES_TXT", raising=False)

    sample = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\t123\n"
    cookie_src = tmp_path / "cookies.txt"
    cookie_src.write_text(sample, encoding="utf-8")

    monkeypatch.setenv("YT_COOKIES_FILE", str(cookie_src))
    resolved = resolve_cookiefile()
    assert resolved is not None
    assert Path(resolved).read_text(encoding="utf-8") == sample

    monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
    monkeypatch.setenv("YT_COOKIES_B64", base64.b64encode(sample.encode("utf-8")).decode("ascii"))
    resolved_b64 = resolve_cookiefile()
    assert resolved_b64 is not None
    assert "TEST\t123" in Path(resolved_b64).read_text(encoding="utf-8")


def test_invalid_job_url_returns_400():
    res = client.post("/api/jobs", json={"url": "https://example.com/not-youtube", "format": "mp3"})
    assert res.status_code == 400
