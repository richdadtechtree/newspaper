# 신문 자동화 프로젝트 (1단계: 네이버 카페 신문 이미지 수집)

네이버 카페 신문스크랩 게시판에서 매일 올라오는 신문 게시글을 찾아 이미지를
원본 해상도로 다운로드하는 자동화. 이후 단계에서 PDF 생성, AI 분석, Slack
전송까지 확장 예정.

**1단계 범위**: 카페 접속 → 오늘 날짜 게시글 탐색 → 이미지 추출 → 원본
다운로드 → 날짜별 폴더 저장. PDF 생성/AI 분석/Slack 전송은 이번 단계에서
구현하지 않는다. (자세한 내용은 `1단계_네이버카페_신문수집_개발계획서.md` 참고)

## 프로젝트 구조

```
newspaper/
├── app/
│   ├── main.py              # 실행 진입점 (--login, --date, --headful)
│   ├── naver_cafe.py        # Playwright로 카페 접속/게시글 탐색/이미지 URL 추출
│   ├── image_downloader.py  # 이미지 다운로드 + 검증 + metadata.json 저장
│   └── utils.py             # 로거, 안전한 저장 경로 처리
├── browser_profile/         # 네이버 로그인 세션이 저장되는 브라우저 프로필 (git에 커밋되지 않음)
├── data/newspapers/         # 날짜별로 다운로드된 이미지 + metadata.json (git에 커밋되지 않음)
├── logs/                    # 실행 로그 (git에 커밋되지 않음)
├── requirements.txt
└── 1단계_네이버카페_신문수집_개발계획서.md
```

## 준비

1. Python 3.10 이상 설치
2. **Google Chrome 설치 필요** (네이버의 자동화 탐지를 피하기 위해
   Playwright 내장 Chromium이 아니라 실제 Chrome 브라우저를 사용합니다.
   `channel="chrome"` 옵션 때문에 Mac에 Chrome이 설치되어 있어야 합니다.)
3. 의존성 설치

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Windows는 .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

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
  `data/newspapers/<날짜>/01.jpg, 02.jpg, ...` 형태로 저장
- 게시글/다운로드 정보는 같은 폴더의 `metadata.json`에 기록
- 이미 성공적으로 처리한 날짜는 중복 실행 시 건너뜀
- 특정 날짜를 지정하려면: `python app/main.py --date 2026-08-30`
- 브라우저 창을 보면서 실행(디버깅용): `python app/main.py --headful`

## 문제 발생 시

- **로그인 오류**: `python app/main.py --login`을 다시 실행해 세션을 갱신
- **오늘 게시글을 찾지 못함**: 게시판에 아직 게시글이 올라오지 않았거나,
  게시글 제목 패턴이 예상과 다를 수 있음 → `logs/app.log` 확인
- **이미지 개수가 부족함**: 일부 이미지 다운로드가 실패한 경우, 프로그램을
  다시 실행하면 이미 받은 이미지는 건너뛰고 누락분만 재시도함
- 실행 로그는 항상 `logs/app.log`에 누적됨

## 다음 단계 (구현 예정)

1. 이미지 30장을 순서대로 PDF로 병합
2. OpenAI API로 기사별 요약
3. 부동산/정책 핵심 뉴스 TOP 5 추출
4. 매일 아침 자동 실행 스케줄링
5. Slack/Telegram/이메일로 브리핑 전송
