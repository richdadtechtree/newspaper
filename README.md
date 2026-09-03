# 신문 자동화 프로젝트 (1~2단계: 네이버 카페 신문 이미지 수집 + PDF 생성)

네이버 카페 신문스크랩 게시판에서 매일 올라오는 신문 게시글을 찾아 이미지를
원본 해상도로 다운로드하고, 페이지 순서를 유지해 하나의 PDF로 합치는 자동화.
이후 단계에서 AI 분석, Slack 전송까지 확장 예정.

**1단계**: 카페 접속 → 오늘 날짜 게시글 탐색 → 이미지 추출 → 원본 다운로드 →
날짜별 폴더 저장.
**2단계**: 다운로드된 이미지를 순서대로 하나의 PDF로 병합.
AI 분석/Slack 전송은 아직 구현하지 않는다. (자세한 내용은
`1단계_네이버카페_신문수집_개발계획서.md` 참고)

## 프로젝트 구조

```
newspaper/
├── app/
│   ├── main.py              # 실행 진입점 (--login, --date, --headful)
│   ├── naver_cafe.py        # Playwright로 카페 접속/게시글 탐색/이미지 URL 추출
│   ├── image_downloader.py  # 이미지 다운로드 + 검증 + metadata.json 저장
│   ├── pdf_builder.py       # 다운로드된 이미지를 순서대로 PDF 병합
│   ├── drive_uploader.py    # (선택) rclone으로 구글 드라이브 업로드 + 로컬 정리
│   └── utils.py             # 로거, 안전한 저장 경로 처리
├── browser_profile/         # 네이버 로그인 세션이 저장되는 브라우저 프로필 (git에 커밋되지 않음)
├── data/newspapers/         # 날짜별로 다운로드된 이미지 + metadata.json (git에 커밋되지 않음)
├── logs/                    # 실행 로그 (git에 커밋되지 않음)
├── requirements.txt
└── 1단계_네이버카페_신문수집_개발계획서.md
```

## 준비

1. Python 3.10 이상 설치
2. **Google Chrome 설치 필요** (네이버의 자동화 탐지를 피하기 위해 기본값은
   Playwright 내장 Chromium이 아니라 실제 Chrome 브라우저를 사용합니다.
   Mac, x86_64 리눅스 등에 Chrome을 설치하세요.)
   - **단, ARM 리눅스 서버(예: Oracle Cloud ARM 인스턴스)는 Google Chrome을
     지원하지 않습니다.** 이 경우 Chrome 설치를 건너뛰고, 아래 3번에서
     `playwright install chromium`을 실행한 뒤 `.env`의
     `PLAYWRIGHT_BROWSER_CHANNEL`을 빈 값으로 설정하세요 (Playwright 내장
     Chromium 사용).
     - Playwright 내장 Chromium은 네이버의 자동화 탐지에 걸려 로그인 세션이
       멀쩡해도 게시글 본문이 안 뜨는 경우가 있었습니다. 이 문제가 발생하면
       아래 "ARM 서버에서 게시글 본문이 안 뜨는 경우" 항목을 참고해 시스템
       Chromium을 설치해 대신 사용하세요.
3. 의존성 설치

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Windows는 .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium    # ARM 리눅스 서버는 필수, Chrome을 쓰는 환경은 생략 가능
   ```

## 0) (선택) 저장 폴더를 구글 드라이브로 지정하기

기본값은 프로젝트 안의 `data/newspapers/` 폴더지만, 구글 드라이브 데스크톱 앱을
설치해뒀다면 그 앱이 동기화하는 폴더에 바로 저장되도록 지정할 수 있다.
(다운로드한 이미지와 PDF가 자동으로 구글 드라이브에 업로드되는 효과)

1. `.env.example`을 복사해서 `.env` 파일 생성
   ```bash
   cp .env.example .env
   ```
2. 구글 드라이브가 동기화하는 실제 폴더 경로 확인 (Mac, 최신 "Google Drive for desktop" 기준)
   ```bash
   ls ~/Library/CloudStorage/
   ```
   `GoogleDrive-내이메일@gmail.com` 같은 폴더가 보이면 그 안에 `내 드라이브` 폴더가 있음
3. `.env` 파일을 열어서 `NEWSPAPER_OUTPUT_DIR`에 원하는 하위 폴더 경로를 적기
   (폴더가 미리 없어도 실행 시 자동으로 생성됨)
   ```
   NEWSPAPER_OUTPUT_DIR=/Users/본인이름/Library/CloudStorage/GoogleDrive-내이메일@gmail.com/내 드라이브/신문스크랩
   ```
4. 저장하고 이후 명령어들은 평소처럼 실행하면 됨. `.env`는 `.gitignore`에
   포함되어 있어 GitHub에는 올라가지 않음(개인 경로이므로).

이 설정을 하지 않으면 계속 `data/newspapers/`에 저장된다. 지정한 폴더 밑에는
아래처럼 **월별 폴더 → 날짜별 폴더** 순으로 자동 정리된다:

```
<NEWSPAPER_OUTPUT_DIR>/
└── 2026-08/
    └── 2026-08-30/
        ├── 01.jpg
        ├── 02.jpg
        ├── ...
        ├── 2026-08-30.pdf
        └── metadata.json
```

## 0-2) (선택, 화면 없는 서버 전용) 구글 드라이브에 업로드 후 서버 로컬 파일 자동 삭제

오라클 클라우드 같은 화면 없는(headless) 서버에는 구글 드라이브 데스크톱 앱을
설치할 수 없다. 대신 [rclone](https://rclone.org)으로 구글 드라이브에 업로드한
뒤, 업로드가 끝나면 서버에 남은 로컬 파일을 자동으로 삭제해서 서버 디스크
용량을 아낀다.

1. rclone 설치
   ```bash
   curl https://rclone.org/install.sh | sudo bash
   ```
2. 구글 드라이브 계정 연결 (최초 1회, 대화형 설정)
   ```bash
   rclone config
   ```
   - `n` (New remote) → 이름은 예: `gdrive`
   - Storage 종류: `Google Drive` (`drive`) 선택
   - `client_id`, `client_secret`: 비워두고 Enter (rclone 공용 client_id 사용).
     단, 공용 client_id는 2026년 중 지원 종료 예정이라는 안내가 나온다 — 매일
     자동 실행하는 운영 단계에서는 [전용 client_id를 직접
     만드는 것](https://rclone.org/drive/#making-your-own-client-id)을 권장
   - scope: `3` (`drive.file`, rclone이 만든 파일에만 접근하는 최소 권한)
   - `service_account_file`: 비워두고 Enter
   - `Edit advanced config?`: `n`
   - `Use auto config?`: 서버에 브라우저가 없으므로 `n`
   - 화면에 나오는 `rclone authorize "drive" "..."` 명령어를 **브라우저가
     있는 다른 컴퓨터(예: Mac)에 rclone을 설치해서 그대로 실행** → 구글
     로그인/허용 → 출력된 토큰을 복사해서 서버의 `config_token>`에 붙여넣기
   - `Configure this as a Shared Drive?`: `n`
   - 이후 `y` → `q`로 설정 종료
3. 연결 확인
   ```bash
   rclone lsd gdrive:
   ```
4. `.env`에 사용할 remote와 드라이브 안 폴더 경로 설정
   ```
   RCLONE_REMOTE=gdrive:신문스크랩
   ```

설정해두면, PDF 생성까지 끝난 뒤 자동으로 `RCLONE_REMOTE`에 지정한 구글
드라이브 폴더로 업로드하고 (`<년-월>/<날짜>/` 구조 동일하게 유지), 업로드가
성공하면 서버의 로컬 파일(이미지/PDF)은 바로 삭제한다. `metadata.json`만
가벼운 완료 기록으로 남아서, 재실행해도 중복 다운로드/중복 업로드하지 않는다.

`RCLONE_REMOTE`를 비워두면 이 업로드 단계는 건너뛰고 항상 로컬(서버 디스크)에
남는다. rclone이 설치되어 있지 않거나 업로드가 실패하면 로컬 파일을 삭제하지
않고 그대로 보존한다.

## 1) 최초 로그인 (아이디/비밀번호는 저장하지 않습니다)

```bash
python app/main.py --login
```

- 브라우저 창이 열리면 **직접** 네이버 아이디/비밀번호로 로그인 (2단계 인증 포함)
- 로그인 완료 후 터미널로 돌아와 Enter 입력
- 로그인 세션은 `browser_profile/` 폴더에 저장되어 다음 실행부터 재사용됨
  (아이디/비밀번호 자체는 어디에도 저장되지 않음)

## 2) 오늘 신문 수집 실행

```bash
python app/main.py
```

- 오늘 날짜의 "YY.M.D 신문스크랩" 게시글을 찾아 이미지들을
  `<저장 폴더>/<년-월>/<날짜>/01.jpg, 02.jpg, ...` 형태로 저장
  (예: `data/newspapers/2026-08/2026-08-30/01.jpg`)
- 이미지 다운로드가 모두 끝나면 같은 폴더에 `<날짜>.pdf`로 자동 병합
  (예: `data/newspapers/2026-08/2026-08-30/2026-08-30.pdf`)
- 게시글/다운로드/PDF 정보는 같은 폴더의 `metadata.json`에 기록
- 이미 성공적으로 처리한 날짜는 재실행해도 다시 다운로드하지 않고, PDF가
  없으면 PDF만 새로 만듦
- 특정 날짜를 지정하려면: `python app/main.py --date 2026-08-30`
- 브라우저 창을 보면서 실행(디버깅용): `python app/main.py --headful`
- 이미 다운로드된 이미지로 PDF만 (다시) 만들려면:
  `python app/main.py --pdf-only --date 2026-08-30`

## 3) (화면 없는 서버 전용) 매일 아침 자동 실행 — cron

`scripts/run_daily.sh`는 성공(오늘 신문 수집 완료)할 때까지, 또는 07:00이
지날 때까지 5분 간격으로 `python app/main.py`를 재시도한 뒤 스스로
종료하는 스크립트다. 게시글이 몇 시에 올라올지 정확히 알 수 없을 때
유용하다. 한 번 성공하면(또는 컷오프 시각이 지나면) 바로 종료하므로,
cron에는 하루 한 번(05:30)만 등록하면 된다.

1. 스크립트 실행 권한 확인 (git에서 이미 실행 권한이 붙어서 오지만, 안 붙어
   있다면)
   ```bash
   chmod +x scripts/run_daily.sh
   ```
2. crontab 등록
   ```bash
   crontab -e
   ```
   맨 아래에 이 줄 추가 (경로는 실제 프로젝트 위치에 맞게 수정):
   ```
   30 5 * * * /home/ubuntu/newspaper/scripts/run_daily.sh >> /home/ubuntu/newspaper/logs/cron.log 2>&1
   ```
3. 저장하고 종료. 등록 확인:
   ```bash
   crontab -l
   ```

컷오프 시각(기본 07:00)이나 재시도 간격(기본 5분)을 바꾸려면
`scripts/run_daily.sh` 안의 `CUTOFF`, `INTERVAL_SECONDS` 값을 수정하면 된다.

## 문제 발생 시

- **로그인 오류**: `python app/main.py --login`을 다시 실행해 세션을 갱신
- **오늘 게시글을 찾지 못함**: 게시판에 아직 게시글이 올라오지 않았거나,
  게시글 제목 패턴이 예상과 다를 수 있음 → `logs/app.log` 확인
- **이미지 개수가 부족함**: 일부 이미지 다운로드가 실패한 경우, 프로그램을
  다시 실행하면 이미 받은 이미지는 건너뛰고 누락분만 재시도함
- **ARM 서버에서 게시글 본문이 안 뜨는 경우**: 로그인 세션은 정상인데(다른
  PC에서는 잘 됨) ARM 서버에서만 계속 게시글 본문 로딩이 타임아웃되면,
  Playwright 내장 Chromium이 네이버 봇 탐지에 걸리는 것일 수 있습니다. apt로
  시스템 Chromium을 설치해 대신 사용하세요:
  ```bash
  sudo apt update
  sudo apt install -y chromium-browser || sudo apt install -y chromium
  which chromium-browser || which chromium
  ```
  위 `which` 명령이 출력한 경로를 `.env`의 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`에
  적어주세요 (설정하면 `PLAYWRIGHT_BROWSER_CHANNEL`은 자동으로 무시됩니다):
  ```
  PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium-browser
  ```
  Ubuntu 22.04 이상은 apt로 `chromium-browser`가 아니라 snap 패키지로만
  제공될 수도 있습니다. 그런 경우 `apt install`이 안내하는 대로 snap을
  이용하거나 `sudo snap install chromium`을 실행한 뒤,
  `which chromium`(보통 `/snap/bin/chromium`)으로 경로를 확인하세요.
- 실행 로그는 항상 `logs/app.log`에 누적됨

## 다음 단계 (구현 예정)

1. OpenAI API로 기사별 요약
2. 부동산/정책 핵심 뉴스 TOP 5 추출
3. Slack/Telegram/이메일로 브리핑 전송
