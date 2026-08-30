# 신문 자동화 프로젝트 (1단계: 네이버 카페 접근 + 진단)

네이버 카페 신문스크랩 게시판에서 이미지를 다운로드해 PDF로 만들고,
이후 AI 분석/Slack 전송까지 확장하기 위한 자동화 프로젝트입니다.

**현재 단계(1단계)에서 구현된 것**
- Playwright 기반 네이버 로그인 및 세션(storage_state) 저장/재사용
- 게시판(`https://cafe.naver.com/f-e/cafes/31064119/menus/10?viewType=L`)의
  실제 HTML 구조를 확인하기 위한 진단 도구

**아직 구현하지 않은 것** (다음 단계)
- 날짜별 게시글("YY.M.D 신문스크랩") 자동 검색
- 신문 이미지 원본 다운로드 및 페이지 순서 유지 PDF 생성
- AI 분석, Slack 전송

## 프로젝트 구조

```
newspaper/
├── newspaper_bot/
│   ├── config.py     # 게시판 URL, 경로 등 설정
│   ├── auth.py       # 로그인/세션(storage_state) 관리
│   ├── login.py       # 최초 1회 로그인용 실행 스크립트
│   └── diagnose.py    # 게시판 HTML 구조 진단 스크립트
├── auth/               # 로그인 세션 저장 위치 (git에 커밋되지 않음)
├── output/             # 다운로드한 이미지/PDF 저장 위치 (다음 단계에서 사용)
├── diagnostics/        # 진단 결과(HTML, 스크린샷, JSON) 저장 위치
├── requirements.txt
└── README.md
```

## 준비

1. Python 3.10 이상 설치
2. 의존성 설치

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows는 .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

## 1) 최초 로그인 (아이디/비밀번호는 저장하지 않습니다)

아래 명령을 실행하면 브라우저 창이 열립니다. 그 창에서 **직접** 네이버
아이디/비밀번호로 로그인하세요. 아이디/비밀번호는 코드/저장소 어디에도
저장되지 않고, 로그인 완료 후의 세션 쿠키만 로컬 파일
(`auth/storage_state.json`)에 저장되어 다음 실행부터 재사용됩니다.

```bash
python -m newspaper_bot.login
```

1. 브라우저 창에서 로그인(2단계 인증이 있다면 함께 완료)
2. 터미널로 돌아와 안내에 따라 Enter 키 입력
3. `auth/storage_state.json` 파일이 생성되면 성공

> `auth/` 폴더는 `.gitignore`에 포함되어 있어 GitHub에 절대 올라가지
> 않습니다.

> 참고: 네이버는 자동화된 브라우저 접속을 감지해 로그인을 막을 수
> 있습니다. 로그인이 계속 실패한다면 headless 서버가 아닌 GUI가 있는
> 로컬 PC(직접 화면을 볼 수 있는 환경)에서 실행하세요.

## 2) 게시판 HTML 구조 진단

실제 게시판이 어떤 구조(SPA, iframe 여부, 게시글 목록 마크업 등)로
되어 있는지 확인하기 위한 진단 스크립트입니다. 다음 단계(게시글 자동
검색, 이미지 다운로드)를 구현하기 전에 실제 데이터를 보고 셀렉터를
정하기 위해 사용합니다.

```bash
python -m newspaper_bot.diagnose
```

브라우저 화면을 직접 보면서 실행하려면:

```bash
python -m newspaper_bot.diagnose --headed
```

실행하면 `diagnostics/` 폴더에 다음 파일들이 생성됩니다.

- `board_<시각>.html` — 게시판 페이지의 전체 HTML
- `board_<시각>.png` — 게시판 페이지 스크린샷(전체 페이지)
- `frames_<시각>.json` — 페이지 내 iframe 목록(이름/URL)
- `candidates_<시각>.json` — 텍스트에 "스크랩"이 포함된 링크 후보 목록

이 파일들을 확인해 게시글 목록/제목/게시글 링크가 어떤 태그와
속성으로 구성되어 있는지 파악한 뒤, 다음 단계(자동 검색/다운로드
로직)를 구현합니다.

세션이 만료되어 로그인 페이지로 리다이렉트되면 진단 스크립트가
콘솔에 경고를 출력합니다. 이 경우 `python -m newspaper_bot.login`을
다시 실행해 세션을 갱신하세요.

> `diagnostics/` 폴더에는 카페의 실제 페이지 내용(개인정보 포함
> 가능성)이 저장될 수 있으므로 `.gitignore`에 포함되어 있으며 GitHub에
> 올라가지 않습니다.

## 다음 단계 (구현 예정)

1. 진단 결과를 바탕으로 게시글 목록에서 오늘 날짜의
   "YY.M.D 신문스크랩" 게시글을 찾는 로직 구현
2. 게시글 본문의 신문 이미지를 원본 해상도로 다운로드
3. 다운로드한 이미지를 페이지 순서대로 PDF로 병합
4. (이후 단계) AI 분석 및 Slack 전송 연동
