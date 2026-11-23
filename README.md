# YouTube 음원 다운로더 — iPhone · 웹 버전 (PWA)

아이폰(iOS Safari), 아이패드, 안드로이드, PC 브라우저 어디서나 별도 앱 설치 없이 유튜브를 검색하고 미리 들어본 뒤 **MP3(192k/320k) 또는 M4A** 음원으로 바로 저장할 수 있는 웹 앱입니다.

## 아이폰(iOS) 최적화 기능
- **인라인 검색 & 미리듣기**: 웹 앱 안에서 유튜브 곡명·가수를 검색하거나 링크를 붙여넣고, `playsinline` 임베드 플레이어로 전체화면 전환 없이 바로 들어볼 수 있습니다.
- **iOS Safari '파일' 앱 저장**: RFC 5987 UTF-8 한글 파일명 헤더로 깨짐 없이 아이폰 **파일 앱 → 다운로드**에 저장됩니다.
- **iPhone 공유 시트(Web Share API) 지원**: 완료 창에서 **iPhone 공유 시트** 버튼을 누르면 아이폰에 연결된 **USB-C / 라이트닝 USB 드라이브**나 iCloud Drive로 바로 복사할 수 있습니다.
- **홈 화면에 추가 (PWA)**: Safari 하단 `공유 → 홈 화면에 추가`를 누르면 앱처럼 전체 화면 아이콘으로 실행됩니다.

## 실행 및 아이폰 접속을 위한 배포 방법

### 1. 클라우드 무료 배포 (아이폰에서 HTTPS로 바로 접속 — 권장)
이 프로젝트에는 [`Dockerfile`](Dockerfile)과 [`render.yaml`](render.yaml)이 포함되어 있습니다.
- **Render / Railway / Fly.io**에 이 폴더(또는 GitHub 저장소)를 연결하면 Docker 이미지(`Python 3.11 + FFmpeg + yt-dlp`)로 자동 배포되며, 발급된 `https://...` 주소를 아이폰 Safari에서 열어 바로 사용할 수 있습니다.

### 2. 내 PC / Mac / NAS에서 직접 실행 (같은 Wi-Fi 아이폰 접속)
```bash
pip install -r requirements.txt
# FFmpeg 설치 필요 (macOS: brew install ffmpeg / Windows: winget install Gyan.FFmpeg)
uvicorn server:app --host 0.0.0.0 --port 8787
```
같은 Wi-Fi에 연결된 아이폰 Safari에서 `http://<PC의 내부 IP>:8787`로 접속해 사용할 수 있습니다.
