"""
PressReader(국립중앙도서관) 매일경제 지면 탐침(probe) 스크립트.

목적: "기사별 사진/이미지를 가져와 우리 페이지에 띄울 수 있는가?" 와
      "화질이 지금(네이버 카페 이미지)보다 좋은가?" 를 판단할 재료를 모은다.

이 스크립트는 '수집기'가 아니라 '조사용'이다. 하는 일:
  1) 페이지를 열고 오가는 이미지 응답(URL/크기/해상도)을 전부 기록
  2) 지면 전체 이미지와 기사별 이미지가 어떤 URL 규칙인지 확인할 수 있게 저장
  3) 기사 영역을 클릭해 보고, 클릭 전/후 새로 생기는 이미지·텍스트를 비교
  4) 화면 스크린샷 + DOM(HTML) 저장 → 구조 분석용

사용법 (본인 PC, 프로젝트 루트에서):
  python scripts/pressreader_probe.py --login          # 최초 1회: 도서관 로그인 후 Enter
  python scripts/pressreader_probe.py --date 2026-10-31 # 탐침 실행 (날짜 생략 시 오늘)

결과는 data/pressreader_probe/<날짜>/ 에 저장된다. (git 커밋 대상 아님)
"""
import os
import sys
import json
import argparse
from datetime import datetime

# 프로젝트 루트를 import 경로에 추가 (다른 스크립트와 동일한 방식)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# 네이버 로그인 세션과 섞이지 않도록 별도 프로필 폴더 사용
PROFILE_DIR = os.path.join(ROOT, "browser_profile_pressreader")
BASE = "https://pressreader.nl.go.kr/korea-republic/maeil-business-newspaper"


def launch(p, headless: bool):
    """로그인 세션이 유지되는 persistent context로 브라우저를 연다."""
    kwargs = dict(
        user_data_dir=PROFILE_DIR,
        headless=headless,
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        viewport={"width": 1600, "height": 1000},
        # 서버(ARM/컨테이너)에서 브라우저가 멈추지 않도록 기존 naver_cafe.py와 같은 옵션을 쓴다
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    # ARM 서버 등에서 시스템 Chromium을 쓰는 기존 프로젝트와 같은 환경변수를 존중
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if exe:
        kwargs["executable_path"] = exe
    return p.chromium.launch_persistent_context(**kwargs)


def do_login():
    """사람이 직접 도서관 로그인을 끝내고 Enter를 누르면 세션이 프로필에 저장된다."""
    with sync_playwright() as p:
        ctx = launch(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://pressreader.nl.go.kr/")
        # 붙여넣기로 딸려 온 엔터가 입력 버퍼에 남아 있으면 input()이 바로 통과해 버리므로 먼저 비운다
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:
            pass  # Windows 등 termios가 없는 환경은 그냥 진행
        # 엔터만으로는 넘어가지 않게, 'done'을 직접 입력해야 저장하고 종료한다
        while input("로그인을 마치고 매일경제 지면이 보이면 done 이라고 입력 후 Enter: ").strip().lower() != "done":
            print("아직 종료하지 않습니다. 브라우저에서 로그인을 계속하세요.")
        ctx.close()
    print("세션 저장 완료. 이제 --login 없이 실행하세요.")


def probe(date_str: str, headless: bool):
    ymd = date_str.replace("-", "")
    url = f"{BASE}/{ymd}/page/1"
    out_dir = os.path.join(ROOT, "data", "pressreader_probe", date_str)
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    records = []  # 이미지로 보이는 모든 응답 기록

    def on_response(resp):
        """이미지 응답을 가로채 파일로 저장하고 메타정보를 남긴다."""
        try:
            ctype = resp.headers.get("content-type", "")
            if not ctype.startswith("image/"):
                return
            body = resp.body()
            idx = len(records)
            ext = ctype.split("/")[-1].split(";")[0] or "bin"
            path = os.path.join(img_dir, f"{idx:03d}.{ext}")
            with open(path, "wb") as f:
                f.write(body)
            w = h = None
            try:  # 해상도 확인 (화질 비교의 핵심 지표)
                from PIL import Image
                with Image.open(path) as im:
                    w, h = im.size
            except Exception:
                pass
            records.append({
                "idx": idx, "url": resp.url, "status": resp.status,
                "content_type": ctype, "bytes": len(body), "width": w, "height": h,
                "file": os.path.basename(path), "phase": current_phase["name"],
            })
        except Exception as e:  # body()는 리다이렉트/취소된 응답에서 실패할 수 있음
            records.append({"url": resp.url, "error": str(e), "phase": current_phase["name"]})

    current_phase = {"name": "page_load"}

    with sync_playwright() as p:
        ctx = launch(p, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", on_response)

        print(f"접속: {url}")
        page.goto(url, wait_until="domcontentloaded")
        # 로그인 안 돼 있으면 로그인 화면/배너가 뜬다 → 현재 URL로 힌트 제공
        page.wait_for_timeout(8000)  # 지면 타일이 로드될 시간
        print(f"현재 URL: {page.url}")

        page.screenshot(path=os.path.join(out_dir, "01_page.png"), full_page=False)
        with open(os.path.join(out_dir, "01_page.html"), "w", encoding="utf-8") as f:
            f.write(page.content())

        # 지면 주소가 아닌 곳(도서관 로그인 페이지 등)으로 튕겼다면 로그인이 안 된 것이므로 여기서 멈춘다
        if "pressreader" not in page.url.split("/")[2]:
            print("\n[중단] 로그인이 안 된 상태입니다 (도서관 로그인 페이지로 이동됨).")
            print("--login 으로 VNC 화면에서 로그인을 끝낸 뒤 done 을 입력하세요.")
            print(f"스크린샷: {os.path.join(out_dir, '01_page.png')}")
            ctx.close()
            return

        # 기사 영역(핫스팟)으로 추정되는 요소를 DOM에서 찾아본다
        hotspots = page.evaluate("""() => {
            const sel = '[class*="article" i], [class*="hotspot" i], [class*="region" i], area, svg polygon, svg path[data-article]';
            return Array.from(document.querySelectorAll(sel)).slice(0, 80).map(e => {
                const r = e.getBoundingClientRect();
                return {tag: e.tagName, cls: (e.getAttribute('class')||'').slice(0,80),
                        id: e.id, href: e.getAttribute('href'),
                        data: Object.fromEntries(Array.from(e.attributes).filter(a => a.name.startsWith('data-')).map(a => [a.name, a.value.slice(0,80)])),
                        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
            });
        }""") or []  # 페이지 이동 중이면 None이 올 수 있어 빈 목록으로 대체
        with open(os.path.join(out_dir, "hotspots.json"), "w", encoding="utf-8") as f:
            json.dump(hotspots, f, ensure_ascii=False, indent=2)
        print(f"기사 영역 후보 요소: {len(hotspots)}개")

        # 지면 중앙 부근을 클릭해 기사 보기가 열리는지, 새 이미지가 생기는지 관찰
        current_phase["name"] = "after_click"
        before = len(records)
        page.mouse.click(800, 450)
        page.wait_for_timeout(6000)
        page.screenshot(path=os.path.join(out_dir, "02_after_click.png"))
        with open(os.path.join(out_dir, "02_after_click.html"), "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"클릭 후 새로 받은 이미지 응답: {len(records) - before}개")

        ctx.close()

    with open(os.path.join(out_dir, "network_images.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # 요약: 큰 이미지 순으로 출력 → 이게 곧 '지면 해상도'를 보여준다
    ok = [r for r in records if r.get("width")]
    ok.sort(key=lambda r: (r["width"] or 0) * (r["height"] or 0), reverse=True)
    print("\n=== 해상도 큰 순 상위 10개 ===")
    for r in ok[:10]:
        print(f"{r['width']}x{r['height']}  {r['bytes']//1024}KB  [{r['phase']}]  {r['url'][:110]}")
    print(f"\n전체 {len(records)}건 기록 → {out_dir}")


def main():
    ap = argparse.ArgumentParser(description="PressReader 매일경제 탐침")
    ap.add_argument("--login", action="store_true", help="도서관 로그인 세션 저장")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="YYYY-MM-DD")
    ap.add_argument("--headless", action="store_true", help="브라우저 창 숨김 (기본은 창 표시)")
    args = ap.parse_args()
    if args.login:
        do_login()
    else:
        probe(args.date, args.headless)


if __name__ == "__main__":
    main()
