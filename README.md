# YouTube 음원 다운로더 — iPhone · 웹 버전 (PWA)

아이폰(iOS Safari), 아이패드, 안드로이드, PC 브라우저 어디서나 별도 앱 설치 없이 유튜브를 검색하고 미리 들어본 뒤 **MP3(192k/320k) 또는 M4A** 음원으로 바로 저장할 수 있는 웹 앱입니다.

## 아이폰(iOS) 최적화 기능
- **인라인 검색 & 미리듣기**: 웹 앱 안에서 유튜브 곡명·가수를 검색하거나 링크를 붙여넣고, `playsinline` 임베드 플레이어로 전체화면 전환 없이 바로 들어볼 수 있습니다.
- **iOS Safari '파일' 앱 저장**: RFC 5987 UTF-8 한글 파일명 헤더로 깨짐 없이 아이폰 **파일 앱 → 다운로드**에 저장됩니다.
- **iPhone 공유 시트(Web Share API) 지원**: 완료 창에서 **iPhone 공유 시트** 버튼을 누르면 아이폰에 연결된 **USB-C / 라이트닝 USB 드라이브**나 iCloud Drive로 바로 복사할 수 있습니다.
- **홈 화면에 추가 (PWA)**: Safari 하단 `공유 → 홈 화면에 추가`를 누르면 앱처럼 전체 화면 아이콘으로 실행됩니다.

## Render 클라우드 배포 시 YouTube 인증 쿠키(`cookies.txt`) 설정
클라우드(Render 등) 데이터센터 IP에서는 유튜브가 로그인 인증을 요구할 수 있습니다. 본인이 로그인한 쿠키를 Render에 등록하면 서버가 자동으로 불러옵니다.

1. PC 크롬(시크릿 창 권장)에서 YouTube에 로그인(보조 구글 계정 권장)한 뒤 Netscape 형식 `cookies.txt`를 내보냅니다.
2. Render 대시보드 → `youtube-audio-web-downloader` → **Environment** → **Secret Files** → **Add Secret File**:
   - **Filename**: `cookies.txt` *(자동으로 `/etc/secrets/cookies.txt`에 마운트되어 서버가 즉시 인식합니다)*
   - **Contents**: `cookies.txt` 내용 전체 붙여넣기 → **Save Changes**
3. 배포 완료 후 `https://<내 앱 주소>/api/health` 를 열었을 때 `"cookies_configured": true` 가 표시되면 정상 적용 완료입니다.
   - *(대안: 환경변수 `YT_COOKIES_TXT` 또는 `YT_COOKIES_B64`, `YT_COOKIES_FILE`도 지원합니다.)*
