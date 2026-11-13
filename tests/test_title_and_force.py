"""제목 필터(신문스크랩만) + --force(새로 받기) 오프라인 검사.

카페·브라우저·인터넷 없이 돈다: 브라우저/다운로드 부분을 가짜로 바꿔 끼운다.
실행:  python3 tests/test_title_and_force.py
"""
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# 서버 venv 가 아니어도 돌도록, 없는 외부 모듈은 빈 껍데기로 채운다
for name in ("dotenv", "requests", "playwright", "playwright.sync_api", "PIL", "img2pdf"):
    if name not in sys.modules:
        try:
            __import__(name)
        except Exception:
            m = types.ModuleType(name)
            m.load_dotenv = lambda *a, **k: None
            m.__getattr__ = lambda attr: type(attr, (Exception,), {})   # 아무 이름이나 빈 껍데기
            sys.modules[name] = m

from app import naver_cafe   # noqa: E402
from app import main as M    # noqa: E402


class TitleFilter(unittest.TestCase):
    def setUp(self):
        for k in ("NEWSPAPER_TITLE_KEYWORD", "NEWSPAPER_TITLE_EXCLUDE"):
            os.environ.pop(k, None)

    def test_only_newspaper_posts(self):
        ok = naver_cafe._oc_title_ok
        self.assertTrue(ok("26.11.13 신문스크랩"))
        self.assertTrue(ok("26.11.13 신문 스크랩"))          # 띄어쓰기 무시
        self.assertFalse(ok("26.11.13 미모"))               # 스크린샷의 4737번 글
        os.environ["NEWSPAPER_TITLE_EXCLUDE"] = "공지"
        self.assertFalse(ok("26.11.13 신문스크랩 공지"))
        os.environ["NEWSPAPER_TITLE_KEYWORD"] = ""          # 끄면 예전처럼 통과
        os.environ.pop("NEWSPAPER_TITLE_EXCLUDE")
        self.assertTrue(ok("26.11.13 미모"))


class Force(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["NEWSPAPER_OUTPUT_DIR"] = self.tmp
        os.environ.pop("RCLONE_REMOTE", None)
        self.day = os.path.join(self.tmp, "2026-11", "2026-11-13")
        os.makedirs(self.day)
        # 예전에 잘못 받은 '미모' 글 6장
        for i in range(1, 7):
            open(os.path.join(self.day, "%02d.jpg" % i), "w").write("old")
        json.dump({"status": "success", "post_title": "26.11.13 미모"},
                  open(os.path.join(self.day, "metadata.json"), "w"))

    def run_main(self, argv, new_status="success", found=True):
        calls = {"scraped": 0}

        class FakeScraper:
            def __init__(self, *a, **k): pass
            def start_browser(self): pass
            def check_login_status(self): return True
            def close(self): pass
            def scrape_today_newspaper(self, d):
                calls["scraped"] += 1
                if not found:
                    return None
                return {"image_urls": ["u"] * 30, "post_title": "26.11.13 신문스크랩",
                        "post_url": "x", "post_id": "4736", "cookies": []}

        def fake_download(date_str, **kw):
            d = M.get_safe_newspaper_dir(date_str)
            os.makedirs(d, exist_ok=True)
            for i in range(1, 31):
                open(os.path.join(d, "%02d.jpg" % i), "w").write("new")
            meta = {"status": new_status, "downloaded_count": 30, "image_count": 30,
                    "post_title": kw["post_title"]}
            json.dump(meta, open(os.path.join(d, "metadata.json"), "w"))
            return meta

        with mock.patch.object(M, "NaverCafeScraper", FakeScraper), \
             mock.patch.object(M, "download_images", fake_download), \
             mock.patch.object(M, "ensure_pdf", lambda d: None), \
             mock.patch.object(sys, "argv", ["main.py", "--date", "2026-11-13"] + argv):
            code = 0
            try:
                M.main()
            except SystemExit as e:
                code = e.code or 0
        return code, calls

    def files(self):
        return sorted(f for f in os.listdir(self.day) if f.endswith(".jpg"))

    def backups(self):
        return [f for f in os.listdir(os.path.dirname(self.day)) if ".replaced-" in f]

    def test_without_force_keeps_old(self):
        code, calls = self.run_main([])
        self.assertEqual((code, calls["scraped"]), (0, 0))   # 이미 받았다고 카페에 안 감
        self.assertEqual(len(self.files()), 6)

    def test_force_redownloads(self):
        code, calls = self.run_main(["--force"])
        self.assertEqual((code, calls["scraped"]), (0, 1))
        self.assertEqual(len(self.files()), 30)               # 예전 6장 대신 새 30장
        meta = json.load(open(os.path.join(self.day, "metadata.json")))
        self.assertEqual(meta["post_title"], "26.11.13 신문스크랩")
        self.assertEqual(self.backups(), [])                  # 성공하면 백업 지움

    def test_force_failure_restores_old(self):
        code, _ = self.run_main(["--force"], new_status="partial")
        self.assertEqual(code, 1)
        self.assertEqual(len(self.files()), 6)                # 예전 그대로 복구
        self.assertEqual(self.backups(), [])

    def test_force_post_not_found_keeps_old(self):
        code, _ = self.run_main(["--force"], found=False)
        self.assertEqual(code, 1)
        self.assertEqual(len(self.files()), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
