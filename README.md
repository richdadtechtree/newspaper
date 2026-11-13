# newspaper — 네이버 카페 종이신문 자동 수집기

매일 아침 네이버 카페 **신문스크랩 게시판**에 올라오는 그날 종이신문 사진(약 30장)을
찾아 **원본 그대로 내려받고**, 순서대로 **PDF 한 권**으로 묶어 저장하는 프로그램입니다.
(선택) 구글 드라이브에도 올려 둡니다.

> 한 줄 요약: **"카페 → 오늘 신문 글 → 사진 30장 → PDF"** 까지가 이 저장소의 일입니다.
> 요약·웹 화면·슬랙 알림은 이 저장소가 아니라 **openclaw** 쪽이 맡습니다.

---

## 1. 전체 그림 — 이 저장소는 어디에 있나

```
 ┌───────────── 이 저장소 (서버 ~/newspaper) ─────────────┐
 │                                                        │
 │  cron 05:00  scripts/run_daily.sh                      │
 │     └ 07:00 까지 5분마다 app/main.py 재시도              │
 │          ① 네이버 카페 접속 (저장된 로그인 세션)          │
 │          ② 제목 = "오늘 날짜 + 신문스크랩" 글 찾기        │
 │          ③ 사진 원본 01.jpg … 30.jpg 내려받기 + 검증      │
 │          ④ <날짜>.pdf 로 묶기, metadata.json 기록         │
 │          ⑤ (선택) rclone 으로 구글 드라이브 업로드        │
 │                                                        │
 │  결과: data/newspapers/2026-11/2026-11-13/              │
 └────────────────────────────┬───────────────────────────┘
                              │ 파일을 읽기만 함 (심볼릭 링크)
 ┌────────────────────────────▼───────────────────────────┐
 │  openclaw (richdadtechtree/openclaw, 서버 ~/.openclaw)   │
 │   · scripts/news_sync.py   → 웹이 읽을 캐시로 연결        │
 │   · 웹 '신문 요약' 화면     → 지면 사진 뷰어·형광펜         │
 │   · 기사 요약(ChatGPT)·오디오·슬랙                         │
 │   · 관리자 🔁 다운로드/요약 버튼 → app/main.py --force 호출 │
 └────────────────────────────────────────────────────────┘
```

| 하는 일 | 이 저장소 | openclaw |
|---|:---:|:---:|
| 카페에서 신문 사진 받기 · PDF 만들기 | ✅ | |
| 드라이브 백업 | ✅ (rclone, 선택) | |
| 웹 화면에 사진 띄우기 · 형광펜 | | ✅ |
| 기사 요약 · 오디오 · 슬랙 | | ✅ |
| 매일 자동 실행 | ✅ cron(`run_daily.sh`) | 08:00 한 번 더 시도(`paper-retry-0800.sh`) |

---

## 2. 어떤 글을 '오늘 신문'으로 고르나

카페 게시판에는 신문 글 말고도 같은 날짜로 시작하는 글이 올라옵니다.

```
4737  26.11.13 미모            ← 건너뜀 (날짜는 맞지만 '신문스크랩'이 없음)
4736  26.11.13 신문스크랩 [11]  ← ✅ 이 글을 받음
4728  26.11.12 신문스크랩 [7]   ← 건너뜀 (어제 날짜)
```

고르는 규칙 (`app/naver_cafe.py`):

1. 제목에 **오늘 날짜가 정확히** 있어야 함 — `26.11.13` (앞자리 0 없어도 됨).
   `26.11.1` 이 `26.11.13` 안에 들어가는 식의 오인은 막아 둠.
2. 제목에 **`신문스크랩`** 이 있어야 함 (띄어쓰기 무시 — `신문 스크랩` 도 통과).
   → 2026-09-16 에 날짜만 보고 `26.9.16 미모`(사진 6장)를 신문으로 받아
   드라이브까지 덮어쓴 사고가 있어서 넣은 조건입니다.
3. 오늘 글을 못 찾으면 **절대 예전 글로 대신하지 않고** 실패로 끝냄
   → `run_daily.sh` 가 5분 뒤 다시 확인 (신문이 늦게 올라오는 날도 자동 처리).

`.env` 로 조절할 수 있습니다:

| 설정 | 기본값 | 뜻 |
|---|---|---|
| `NEWSPAPER_TITLE_KEYWORD` | `신문스크랩` | 제목에 꼭 있어야 하는 말. 빈 값이면 조건을 끔(날짜만 봄, 비추천) |
| `NEWSPAPER_TITLE_EXCLUDE` | (없음) | 이 말이 있으면 건너뜀. 쉼표로 여러 개 (예: `공지,테스트`) |

---

## 3. 실행 방법 한눈에 보기

| 명령 | 하는 일 |
|---|---|
| `python app/main.py --login` | (처음 한 번) 브라우저를 띄워 **직접** 네이버 로그인 → 세션 저장 |
| `python app/main.py` | 오늘 신문 받기. **이미 받은 날이면 다시 받지 않음** (PDF 만 없으면 PDF 만 생성) |
| `python app/main.py --force` | 이미 받은 날이어도 **카페에서 새로 받기** (아래 4장 참고) |
| `python app/main.py --date 2026-11-13` | 특정 날짜 받기 (다른 옵션과 함께 쓸 수 있음) |
| `python app/main.py --pdf-only --date …` | 카페에 안 가고, 받아 둔 사진으로 PDF 만 다시 만들기 |
| `python app/main.py --headful` | 브라우저 창을 보면서 실행 (문제 찾기용) |
| `scripts/run_daily.sh` | 성공하거나 07:00 이 지날 때까지 5분마다 `app/main.py` 재시도 (cron 용) |

끝나면 결과가 이렇게 남습니다:

```
data/newspapers/            (.env 의 NEWSPAPER_OUTPUT_DIR 로 바꿀 수 있음)
└── 2026-11/
    └── 2026-11-13/
        ├── 01.jpg … 30.jpg   신문 지면 사진 (원본)
        ├── 2026-11-13.pdf    사진을 순서대로 묶은 PDF
        └── metadata.json     어느 글에서 받았는지(제목·주소·글번호)·장수·상태
```

종료 코드: `0` = 성공(또는 이미 받음) / `1` = 실패 (글 없음·로그인 풀림·사진 누락 등).

---

## 4. `--force` (새로 받기) — 어떻게 안전하게 바꾸나

잘못된 글을 받았거나 사진이 바뀐 날, 웹의 **🔁 다운로드/요약 버튼**(openclaw)이 이 옵션으로 수집기를 부릅니다.

1. 먼저 카페에서 **오늘 신문 글과 사진 주소를 찾는다.**
   못 찾으면 여기서 끝 → 예전 파일은 **그대로**.
2. 찾았으면 예전 날짜 폴더를 숨은 백업 `.2026-11-13.replaced-<시각>` 으로 옮긴다.
   (점으로 시작해서 openclaw 등 다른 프로그램이 날짜 폴더로 착각하지 않음)
3. 새로 받는다.
   - 성공 → 백업 삭제, 새 사진·PDF 사용
   - 실패(사진 누락·오류) → 백업을 **원래 자리로 되돌림**

즉 어떤 경우에도 "그날 신문이 아예 없는 상태"는 남지 않습니다.

---

## 5. 폴더 구조

```
newspaper/
├── app/
│   ├── main.py              # 실행 진입점: 옵션 처리, 중복 확인, --force 백업/복구
│   ├── naver_cafe.py        # Playwright 로 카페 접속 → 오늘 '신문스크랩' 글 찾기 → 사진 주소 뽑기
│   ├── image_downloader.py  # 사진 원본 받기 + 검증 + metadata.json 저장 (누락분만 재시도)
│   ├── pdf_builder.py       # 사진을 순서대로 PDF 한 권으로
│   ├── drive_uploader.py    # (선택) rclone 으로 구글 드라이브 업로드 + 로컬 정리
│   └── utils.py             # 로그, 안전한 저장 경로(날짜 형식 검사)
├── scripts/
│   ├── run_daily.sh         # 리눅스 서버 cron 용 재시도 스크립트
│   └── run_daily.ps1        # 윈도우 PC 작업 스케줄러 용 (같은 동작)
├── tests/
│   └── test_title_and_force.py  # 제목 고르기·--force 검사 (인터넷·브라우저 없이 실행)
├── browser_profile/         # 네이버 로그인 세션 (git 에 안 올라감 — 절대 공유 금지)
├── data/newspapers/         # 받은 사진·PDF (git 에 안 올라감)
├── logs/app.log             # 실행 기록 (git 에 안 올라감)
├── .env.example             # 설정 예시 → .env 로 복사해서 사용
└── 1단계_네이버카페_신문수집_개발계획서.md
```

검사 실행: `python3 tests/test_title_and_force.py` → 마지막 줄 `OK` 면 정상.

---

## 6. 서버 운영 메모 (openclaw 와 함께 쓸 때)

- **서버 위치**: `/home/ubuntu/newspaper`. 실행은 venv 파이썬 `.venv/bin/python`.
- **자동 실행**: cron 이 `scripts/run_daily.sh` 를 부름 (openclaw 의
  `scripts/set-newspaper-schedule.sh` 로 시작 시각을 05:00 으로 맞춰 둠 → 05:00~07:00 5분마다 확인).
  07:00 까지 실패하면 openclaw 의 `paper-retry-0800.sh` 가 08:00 에 한 번 더.
- **서버 반영은 자동**(2026-11-13~): openclaw 의 `git-auto-pull.sh`(1분마다)가
  `scripts/newspaper_auto_pull.py` 로 **5분에 한 번** 이 저장소를 확인해 새 커밋을 받습니다.
  - 기본 브랜치 이름이 `main` 이 아니라 `claude/naver-cafe-newspaper-download-caonzo` 입니다 — 여기에 올리면 반영.
  - 수집기가 돌고 있으면 기다렸다가, 끝난 뒤 받습니다.
  - 앞으로 감기만 하고, 서버에서 고친 파일과 겹치거나 받은 코드가 문법 검사에서 깨지면
    **받지 않고/되돌리고** 로그만 남깁니다 (서버 `~/.openclaw/scripts/auto-pull.log` 의 `[newspaper-pull]` 줄).
  - 받았는지 확인: 웹 🔁 다운로드 결과에 "수집기가 예전 버전" 경고가 없으면 새 버전.
    서버에서는 `python3 ~/.openclaw/scripts/newspaper_auto_pull.py --status`.
  - 손으로 받고 싶으면: `cd ~/newspaper && git pull origin claude/naver-cafe-newspaper-download-caonzo`
- **서버에서 덧댄 수정(openclaw 패치)**
  - 제목 필터(`patch-newspaper-title-filter.sh`) — **이제 이 저장소에 들어 있어 필요 없음.**
    예전 패치가 서버 파일에 남아 있으면 자동 받기가 백업(`.bak-autopull-시각`)을 남기고 지웁니다.
  - 오늘치 로컬 보관(`patch-newspaper-keep-local.sh`) — `drive_uploader.py` 가 업로드 뒤
    폴더를 통째로 지우지 않고 **오늘치는 남기게** 함 (웹 화면이 사진을 읽어야 해서).
    아직 이 저장소엔 없으므로 서버 패치를 유지하세요.

---

# 설치·설정 가이드

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

- 오늘 날짜의 "YY.M.D 신문스크랩" 게시글을 찾아(고르는 규칙은 위 2장) 이미지들을
  `<저장 폴더>/<년-월>/<날짜>/01.jpg, 02.jpg, ...` 형태로 저장
  (예: `data/newspapers/2026-08/2026-08-30/01.jpg`)
- 이미지 다운로드가 모두 끝나면 같은 폴더에 `<날짜>.pdf`로 자동 병합
  (예: `data/newspapers/2026-08/2026-08-30/2026-08-30.pdf`)
- 게시글/다운로드/PDF 정보는 같은 폴더의 `metadata.json`에 기록
- 이미 성공적으로 처리한 날짜는 재실행해도 다시 다운로드하지 않고, PDF가
  없으면 PDF만 새로 만듦
- 이미 받은 날이어도 카페에서 **새로 받으려면**: `python app/main.py --force` (위 4장)
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

## 3-2) (Windows PC 전용) 매일 아침 자동 실행 — 작업 스케줄러

오라클 클라우드 같은 서버는 IP 자체가 자동화 탐지에 걸려 게시글 본문을 못
가져오는 경우가 있습니다. 이 경우 가정용 인터넷(PC)에서 실행하는 게 훨씬
안정적입니다. `scripts/run_daily.ps1`은 `scripts/run_daily.sh`와 동일하게,
성공하거나 07:00이 지날 때까지 5분 간격으로 재시도한 뒤 스스로 종료합니다.

1. (선택) 구글 드라이브 데스크톱 앱이 설치되어 있다면, 위 "0) 저장 폴더를
   구글 드라이브로 지정하기"를 참고해 `.env`의 `NEWSPAPER_OUTPUT_DIR`을 그
   동기화 폴더로 지정해두면 결과물이 자동으로 구글 드라이브에도 올라갑니다.
2. PowerShell을 **관리자 권한으로** 열고 작업 스케줄러에 등록 (경로는 실제
   프로젝트 위치에 맞게 수정):
   ```powershell
   schtasks /Create /TN "NewspaperScrap" /TR "powershell.exe -ExecutionPolicy Bypass -File C:\Users\본인이름\Documents\newspaper-win\scripts\run_daily.ps1" /SC DAILY /ST 05:30
   ```
3. 등록 확인:
   ```powershell
   schtasks /Query /TN "NewspaperScrap"
   ```
4. PC가 잠자기 모드일 때도 실행되게 하려면, 작업 스케줄러 앱(`taskschd.msc`)을
   열어 "NewspaperScrap" 작업 → 속성 → "조건" 탭에서 "작업을 실행하기 위해
   컴퓨터를 절전 모드에서 해제" 체크박스를 켜주세요.
5. 로그를 파일로 남기고 싶다면 위 `schtasks` 명령의 `-File ...` 뒤에
   `*>> C:\...\logs\cron.log`처럼 리다이렉션을 추가하거나, 작업 스케줄러
   GUI에서 동작(Action)에 로그 리다이렉션을 설정할 수 있습니다.

컷오프 시각이나 재시도 간격을 바꾸려면 `scripts/run_daily.ps1` 안의
`$Cutoff`, `$IntervalSeconds` 값을 수정하면 됩니다.

## 문제 발생 시

- **로그인 오류**: `python app/main.py --login`을 다시 실행해 세션을 갱신
- **오늘 게시글을 찾지 못함**: 게시판에 아직 게시글이 올라오지 않았거나,
  게시글 제목 패턴이 예상과 다를 수 있음 → `logs/app.log` 확인
  (`[filter] 제목에 '신문스크랩' 가 없어 건너뜀: …` 줄이 보이면 제목 규칙 때문에 건너뛴 것 — 위 2장)
- **이미지 개수가 부족함**: 일부 이미지 다운로드가 실패한 경우, 프로그램을
  다시 실행하면 이미 받은 이미지는 건너뛰고 누락분만 재시도함
- **ARM 서버에서 게시글 본문이 안 뜨는 경우**: 로그인 세션은 정상인데(다른
  PC에서는 잘 됨) 서버에서만 계속 게시글 본문 로딩이 타임아웃되면,
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

  이걸 해도 안 된다면, 브라우저 종류가 아니라 **headless(화면 없는) 모드
  자체**가 감지되는 것일 수 있습니다. 이 경우 서버에 가상 디스플레이(Xvfb)를
  설치해서 "화면이 있는 척" 띄우면 해결될 수 있습니다:
  ```bash
  sudo apt install -y xvfb
  ```
  `.env`에 다음 줄을 추가:
  ```
  FORCE_HEADFUL=1
  ```
  `scripts/run_daily.sh`는 `xvfb-run`이 설치되어 있으면 자동으로 그걸로
  감싸서 실행하므로 cron 설정은 그대로 두면 됩니다. 직접 테스트하려면:
  ```bash
  xvfb-run -a python app/main.py
  ```
- 실행 로그는 항상 `logs/app.log`에 누적됨

## 요약·알림은 어디서?

처음 계획(개발계획서)의 "기사 요약 → 핵심 뉴스 → 슬랙 전송" 단계는 이 저장소가 아니라
**openclaw** 에서 구현돼 있습니다: 웹 '신문 요약' 화면, ChatGPT 요약 요청, NotebookLM 오디오,
관리자 🔁 다운로드/요약 버튼. 이 저장소는 **신문 원본을 정확하게 받아 두는 일**에만 집중합니다.
