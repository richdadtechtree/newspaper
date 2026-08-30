"""최초 1회 실행: 네이버에 직접 로그인하고 세션을 저장한다.

사용법:
    python -m newspaper_bot.login
"""

from playwright.sync_api import sync_playwright

from .auth import interactive_login


def main() -> None:
    with sync_playwright() as playwright:
        context = interactive_login(playwright)
        context.close()


if __name__ == "__main__":
    main()
