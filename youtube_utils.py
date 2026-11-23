import re
from typing import Optional
from urllib.parse import quote

URL_EXTRACT_RE = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)
WATCH_V_RE = re.compile(r"""[?&]v=([a-zA-Z0-9_-]{11})""")
SHORT_LINK_RE = re.compile(r"""https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})""", re.IGNORECASE)
SHORTS_RE = re.compile(
    r"""https?://(?:(?:www|m|music)\.)?youtube\.com/(?:shorts|live|embed)/([a-zA-Z0-9_-]{11})""",
    re.IGNORECASE,
)
YT_HOST_RE = re.compile(r"""^https?://(?:(?:www|m|music)\.)?youtube\.com/""", re.IGNORECASE)
ILLEGAL_FILENAME_RE = re.compile(r"""[\\/:*?"<>|\r\n\t\x00-\x1f]""")


def extract_video_id(text: Optional[str]) -> Optional[str]:
    if not text or not text.strip():
        return None
    match = URL_EXTRACT_RE.search(text)
    url = match.group(0) if match else text.strip()

    m = SHORT_LINK_RE.search(url)
    if m:
        return m.group(1)

    m = SHORTS_RE.search(url)
    if m:
        return m.group(1)

    if YT_HOST_RE.search(url):
        m = WATCH_V_RE.search(url)
        if m:
            return m.group(1)

    return None


def normalize_video_url(text: Optional[str]) -> Optional[str]:
    vid = extract_video_id(text)
    if not vid:
        return None
    return f"https://www.youtube.com/watch?v={vid}"


def sanitize_filename(raw_name: str, max_length: int = 90) -> str:
    cleaned = ILLEGAL_FILENAME_RE.sub(" ", raw_name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(". ")
    safe = cleaned or "youtube_audio"
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip(". ")
    return safe


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds <= 0:
        return ""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_content_disposition(filename: str, disposition: str = "attachment") -> str:
    """Builds RFC 5987 UTF-8 Content-Disposition header compatible with iOS Safari and all browsers."""
    ascii_fallback = re.sub(r"[^\x20-\x7e]", "_", filename).replace('"', "").replace("\\", "")
    if not ascii_fallback.strip("._ "):
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp3"
        ascii_fallback = f"youtube_audio.{ext}"
    encoded = quote(filename, safe="")
    return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
