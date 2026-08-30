"""네이버 로그인 및 Playwright storage_state 관리.

아이디/비밀번호는 코드나 저장소에 저장하지 않는다. 사용자가 브라우저 창에서
직접 로그인하면, 로그인 이후의 쿠키/세션 정보(storage_state)만 로컬 파일로
저장해 다음 실행부터 재사용한다.
"""

from playwright.sync_api import Browser, BrowserContext, Playwright

from . import config


def interactive_login(playwright: Playwright) -> BrowserContext:
    """브라우저 창을 띄워 사용자가 직접 로그인하도록 하고, 세션을 저장한다."""
    config.AUTH_DIR.mkdir(parents=True, exist_ok=True)

    browser: Browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(config.NAVER_LOGIN_URL)

    print("\n[login] 브라우저 창에서 네이버 아이디/비밀번호로 직접 로그인하세요.")
    print("[login] (2단계 인증 등이 있다면 모두 완료하세요.)")
    input("[login] 로그인을 마쳤으면 이 터미널에서 Enter 키를 누르세요... ")

    context.storage_state(path=str(config.STORAGE_STATE_PATH))
    print(f"[login] 로그인 세션을 저장했습니다: {config.STORAGE_STATE_PATH}")

    return context


def load_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """저장된 storage_state로 브라우저 컨텍스트를 연다. 없으면 에러를 발생시킨다."""
    if not config.STORAGE_STATE_PATH.exists():
        raise RuntimeError(
            "저장된 로그인 세션이 없습니다. 먼저 다음 명령으로 로그인하세요:\n"
            "  python -m newspaper_bot.login"
        )

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(config.STORAGE_STATE_PATH))
    return context
