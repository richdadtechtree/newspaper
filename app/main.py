import os
import sys
import argparse
import json
import glob
import shutil
import time
from datetime import datetime
from dotenv import load_dotenv

# Ensure the root of the project is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils import logger, get_safe_newspaper_dir
from app.naver_cafe import NaverCafeScraper
from app.image_downloader import download_images
from app.pdf_builder import ensure_pdf
from app.drive_uploader import upload_and_cleanup


def finalize_output(target_date: str):
    """
    Ensures the PDF exists, then (if RCLONE_REMOTE is configured) uploads the
    day's folder to Google Drive and deletes it locally to save server disk
    space. Returns {"location": str, "uploaded": bool}, or None if there is
    no metadata yet for this date.
    """
    target_dir = get_safe_newspaper_dir(target_date)
    metadata_path = os.path.join(target_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        return None

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if metadata.get("storage") == "uploaded_and_cleaned":
        return {"location": metadata.get("drive_path"), "uploaded": True}

    pdf_path = ensure_pdf(target_date)

    drive_path = upload_and_cleanup(target_dir, target_date)
    if drive_path:
        os.makedirs(target_dir, exist_ok=True)
        metadata["storage"] = "uploaded_and_cleaned"
        metadata["drive_path"] = drive_path
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        return {"location": drive_path, "uploaded": True}

    return {"location": pdf_path or target_dir, "uploaded": False}


# ── --force(새로 받기) 때 쓰는 백업/복구 ────────────────────────────────────────
# 이미 받은 날을 다시 받을 때, 예전 폴더를 바로 지우지 않고 옆으로 옮겨 둔다.
# 새로 받기가 실패하면 예전 폴더를 되돌려 놓아 '아무것도 없는 날'이 생기지 않게 한다.
# 백업 이름은 점(.)으로 시작해서(.2026-11-13.replaced-1700000000) 날짜 폴더를 찾는
# 다른 프로그램(openclaw news_sync 등)이 실수로 집지 않는다.
def _backup_day_dir(target_dir: str):
    """target_dir 에 파일이 있으면 백업 폴더로 옮기고 그 경로를 돌려준다(없으면 None)."""
    if not os.path.isdir(target_dir) or not os.listdir(target_dir):
        return None
    parent, name = os.path.split(target_dir.rstrip(os.sep))
    # 같은 날짜의 예전 백업은 하나만 남기면 충분하다 → 오래된 건 지운다
    for old in glob.glob(os.path.join(parent, f".{name}.replaced-*")):
        shutil.rmtree(old, ignore_errors=True)
    backup = os.path.join(parent, f".{name}.replaced-{int(time.time())}")
    shutil.move(target_dir, backup)
    logger.info(f"[force] 예전 폴더를 백업으로 옮김: {target_dir} -> {backup}")
    return backup


def _restore_day_dir(target_dir: str, backup):
    """새로 받기가 실패했을 때 백업을 원래 자리로 되돌린다."""
    if not backup or not os.path.isdir(backup):
        return
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    shutil.move(backup, target_dir)
    logger.info(f"[force] 새로 받기 실패 → 예전 폴더로 되돌림: {target_dir}")


def _drop_backup(backup):
    """새로 받기가 성공하면 백업은 필요 없다."""
    if backup and os.path.isdir(backup):
        shutil.rmtree(backup, ignore_errors=True)
        logger.info(f"[force] 새로 받기 성공 → 백업 삭제: {backup}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Naver Cafe Newspaper Automated Collection - Phase 1 & 2")
    parser.add_argument("--login", action="store_true", help="Run interactive Naver login to save session")
    parser.add_argument("--date", type=str, default=None, help="Target date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--headful", action="store_true", help="Run Playwright in headful mode (visible browser)")
    parser.add_argument("--pdf-only", action="store_true", help="Skip scraping; just (re)build the PDF from already-downloaded images")
    parser.add_argument("--force", action="store_true",
                        help="이미 받은 날이어도 카페에서 새로 받는다 (예전 폴더는 백업했다가 성공하면 지우고, 실패하면 되돌림)")

    args = parser.parse_args()

    # 1. Login Mode
    if args.login:
        logger.info("Starting interactive Naver login...")
        scraper = NaverCafeScraper(headless=False)
        try:
            scraper.run_interactive_login()
            print("\n==========================================")
            print("Login successful! Session has been saved.")
            print("You can now run without the --login flag.")
            print("==========================================\n")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            sys.exit(1)
        return

    # Determine target date
    target_date = args.date
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"Target date: {target_date}")

    # PDF-only mode: skip scraping entirely, just build/refresh the PDF
    # (and upload it to Google Drive if configured)
    if args.pdf_only:
        result = finalize_output(target_date)
        if result:
            print(f"\n==========================================")
            print(f"{target_date} PDF 생성 완료")
            print(f"위치: {result['location']}" + (" (구글 드라이브)" if result["uploaded"] else ""))
            print(f"==========================================\n")
        else:
            print(f"\n[Error] {target_date}에 대해 PDF를 만들 이미지가 없습니다. 먼저 python app/main.py --date {target_date} 를 실행하세요.\n")
            sys.exit(1)
        return

    # 2. Check duplicate download (--force 면 건너뛰고 무조건 새로 받는다)
    if args.force:
        logger.info(f"[force] {target_date} 를 이미 받았어도 카페에서 새로 받습니다.")
    else:
        try:
            target_dir = get_safe_newspaper_dir(target_date)
            metadata_path = os.path.join(target_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                if meta.get("status") == "success":
                    result = finalize_output(target_date)
                    print(f"\n==========================================")
                    print(f"이미 {target_date} 신문을 처리했습니다. (Status: success)")
                    if result:
                        print(f"위치: {result['location']}" + (" (구글 드라이브)" if result["uploaded"] else ""))
                    print(f"==========================================\n")
                    return
        except Exception as e:
            logger.warning(f"Error checking duplicate: {e}")

    backup_dir = None            # --force 때 옮겨 둔 예전 폴더(실패하면 되돌림)

    # 3. Start Scraping
    # 네이버 봇 탐지가 headless Chrome 자체를 감지하는 것으로 보여, 화면 없는
    # 서버에서도 Xvfb(가상 디스플레이) 위에서 "화면이 있는 척" 띄우고 싶을 때는
    # FORCE_HEADFUL=1을 설정해 headless를 강제로 끌 수 있다 (xvfb-run과 함께 사용).
    force_headful = os.environ.get("FORCE_HEADFUL", "").strip().lower() in ("1", "true", "yes")
    scraper = NaverCafeScraper(headless=not (args.headful or force_headful))
    try:
        scraper.start_browser()

        # Check login status
        if not scraper.check_login_status():
            logger.error("네이버 로그인 상태를 확인해주세요. 'python app/main.py --login'을 실행하여 먼저 로그인해야 합니다.")
            print("\n[Error] 네이버 로그인 상태를 확인해주세요.")
            print("먼저 다음 명령어를 실행하여 수동 로그인을 완료하세요:")
            print("  python app/main.py --login\n")
            scraper.close()
            sys.exit(1)

        # Find post and extract image URLs
        scrape_result = scraper.scrape_today_newspaper(target_date)
        if not scrape_result:
            logger.error(f"{target_date} 날짜의 신문 게시글을 찾지 못했습니다.")
            print(f"\n[Error] {target_date} 날짜의 신문 게시글을 찾지 못했습니다.\n")
            scraper.close()
            sys.exit(1)

        scraper.close()

        # 4. Download images
        image_urls = scrape_result["image_urls"]
        post_title = scrape_result["post_title"]
        post_url = scrape_result["post_url"]
        post_id = scrape_result["post_id"]
        cookies = scrape_result["cookies"]

        if not image_urls:
            logger.error("게시글에서 이미지를 발견하지 못했습니다.")
            print("\n[Error] 게시글에서 이미지를 발견하지 못했습니다.\n")
            sys.exit(1)

        # --force: 새 글과 사진 주소를 찾은 '뒤에야' 예전 폴더를 비킨다.
        # (글을 못 찾았으면 위에서 이미 끝났으므로 예전 파일은 그대로 남는다)
        if args.force:
            backup_dir = _backup_day_dir(get_safe_newspaper_dir(target_date))

        metadata = download_images(
            date_str=target_date,
            post_title=post_title,
            post_url=post_url,
            post_id=post_id,
            image_urls=image_urls,
            cookies=cookies
        )

        # 5. Output Summary
        if metadata.get("status") == "success":
            _drop_backup(backup_dir)
            backup_dir = None
            result = finalize_output(target_date)
            print(f"\n==========================================")
            print(f"{target_date} 신문 수집 완료")
            print(f"제목: {post_title}")
            print(f"이미지: {metadata['downloaded_count']}/{metadata['image_count']}장")
            if result:
                print(f"위치: {result['location']}" + (" (구글 드라이브)" if result["uploaded"] else ""))
            print(f"==========================================\n")
        else:
            print(f"\n==========================================")
            print(f"{target_date} 신문 수집 실패 또는 일부 누락")
            print(f"성공 이미지: {metadata['downloaded_count']}/{metadata['image_count']}장")
            print(f"상태: {metadata['status']}")
            print(f"로그를 확인해주세요: logs/app.log")
            print(f"==========================================\n")
            _restore_day_dir(get_safe_newspaper_dir(target_date), backup_dir)
            sys.exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error during execution: {e}")
        print(f"\n[Error] 실행 중 예기치 않은 오류 발생: {e}\n")
        try:
            _restore_day_dir(get_safe_newspaper_dir(target_date), backup_dir)
        except Exception as re_err:
            logger.error(f"[force] 예전 폴더 되돌리기 실패: {re_err}")
        if scraper:
            try:
                scraper.close()
            except Exception:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()
