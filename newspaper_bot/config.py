"""프로젝트 공통 설정 값."""

import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

AUTH_DIR = BASE_DIR / "auth"
STORAGE_STATE_PATH = AUTH_DIR / "storage_state.json"

OUTPUT_DIR = BASE_DIR / "output"
DIAGNOSTICS_DIR = BASE_DIR / "diagnostics"

# 네이버 카페 "신문스크랩" 게시판
CAFE_ID = 31064119
CAFE_MENU_ID = 10
CAFE_BOARD_URL = (
    f"https://cafe.naver.com/f-e/cafes/{CAFE_ID}/menus/{CAFE_MENU_ID}?viewType=L"
)

NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"

DEFAULT_TIMEOUT_MS = 30_000


def expected_post_title(date: dt.date) -> str:
    """실행 날짜에 해당하는 게시글 제목 패턴을 만든다. 예: 2026-08-30 -> '26.8.30 신문스크랩'"""
    yy = date.year % 100
    return f"{yy}.{date.month}.{date.day} 신문스크랩"
