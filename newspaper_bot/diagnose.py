"""네이버 카페 게시판의 실제 HTML 구조를 확인하기 위한 진단 도구.

아직 게시글 자동 검색/다운로드 기능은 구현하지 않는다. 이 스크립트는
- 게시판 목록 페이지에 접속해 HTML/스크린샷을 저장하고
- 페이지에 존재하는 iframe 목록을 저장하고
- '스크랩'이 포함된 링크 후보를 모아서
이후 단계(게시글 검색, 이미지 다운로드) 구현 시 실제 셀렉터를 파악하는 데 쓴다.

사용법:
    python -m newspaper_bot.diagnose
    python -m newspaper_bot.diagnose --headed   # 브라우저 창을 보면서 실행
"""

import argparse
import datetime as dt
import json

from playwright.sync_api import Frame, sync_playwright

from . import config
from .auth import load_context


def _dump_frame_links(frame: Frame) -> list[dict]:
    """프레임 안에서 '스크랩' 텍스트를 포함한 링크를 모두 수집한다."""
    try:
        anchors = frame.eval_on_selector_all(
            "a",
            "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
            ".filter(x => x.text.length > 0)",
        )
    except Exception as exc:  # noqa: BLE001 - 진단 목적이므로 실패해도 계속 진행
        print(f"[diagnose] 프레임({frame.url})에서 링크 수집 실패: {exc}")
        return []

    return [a for a in anchors if "스크랩" in a["text"]]


def run_diagnosis(headless: bool = True) -> None:
    config.DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    with sync_playwright() as playwright:
        context = load_context(playwright, headless=headless)
        page = context.new_page()

        print(f"[diagnose] 게시판 접속: {config.CAFE_BOARD_URL}")
        page.goto(config.CAFE_BOARD_URL, wait_until="networkidle", timeout=config.DEFAULT_TIMEOUT_MS)
        page.wait_for_timeout(2000)

        if "nid.naver.com" in page.url:
            print(
                "[diagnose] 경고: 로그인 페이지로 리다이렉트되었습니다. "
                "저장된 세션이 만료되었을 수 있습니다. `python -m newspaper_bot.login` 을 다시 실행하세요."
            )

        html_path = config.DIAGNOSTICS_DIR / f"board_{timestamp}.html"
        html_path.write_text(page.content(), encoding="utf-8")
        print(f"[diagnose] 게시판 HTML 저장: {html_path}")

        screenshot_path = config.DIAGNOSTICS_DIR / f"board_{timestamp}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"[diagnose] 게시판 스크린샷 저장: {screenshot_path}")

        frames_info = [{"name": f.name, "url": f.url} for f in page.frames]
        frames_path = config.DIAGNOSTICS_DIR / f"frames_{timestamp}.json"
        frames_path.write_text(
            json.dumps(frames_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[diagnose] iframe 목록 저장: {frames_path} ({len(frames_info)}개)")

        candidates = []
        for frame in page.frames:
            for link in _dump_frame_links(frame):
                candidates.append({"frame": frame.url, **link})

        candidates_path = config.DIAGNOSTICS_DIR / f"candidates_{timestamp}.json"
        candidates_path.write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[diagnose] '스크랩' 포함 링크 후보 저장: {candidates_path} ({len(candidates)}건)")

        today_pattern = config.expected_post_title(dt.date.today())
        print(f"[diagnose] 참고: 오늘 날짜 기준 예상 게시글 제목 패턴 -> '{today_pattern}'")

        context.close()

    print("\n[diagnose] 완료. diagnostics/ 폴더의 HTML/스크린샷/JSON 파일로 실제 구조를 확인하세요.")


def main() -> None:
    parser = argparse.ArgumentParser(description="네이버 카페 게시판 HTML 구조 진단 도구")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="브라우저 창을 표시하여 실행합니다 (기본값: headless)",
    )
    args = parser.parse_args()
    run_diagnosis(headless=not args.headed)


if __name__ == "__main__":
    main()
