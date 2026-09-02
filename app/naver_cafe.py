import os
import re
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
from app.utils import logger

class NaverCafeScraper:
    CAFE_ID = 31064119

    def __init__(self, headless: bool = True):
        self.profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'browser_profile'))
        os.makedirs(self.profile_dir, exist_ok=True)
        self.headless = headless
        self.playwright = None
        self.context = None
        self.page = None

    def start_browser(self, headless: bool = None) -> Page:
        if headless is not None:
            self.headless = headless

        self.playwright = sync_playwright().start()

        # 실제 Google Chrome이 설치된 환경(예: Mac)에서는 채널 "chrome"을 사용해
        # 네이버의 자동화 탐지를 피한다. Chrome이 없는 환경(예: ARM 리눅스 서버)에서는
        # PLAYWRIGHT_BROWSER_CHANNEL을 빈 값으로 설정하면 Playwright 내장 Chromium을
        # 사용한다 (사전에 `playwright install chromium` 필요).
        channel = os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL", "chrome").strip()
        logger.info(f"Launching browser with profile at {self.profile_dir} (headless={self.headless}, channel={channel or 'bundled chromium'})")

        launch_kwargs = dict(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            viewport={"width": 1280, "height": 1024},
            # 네이버는 한국 서비스인데 Playwright 기본값(locale/timezone)은 en-US/UTC라
            # 그 자체로 비정상 신호가 될 수 있다. 실제 한국 사용자 환경에 맞춘다.
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        if channel:
            launch_kwargs["channel"] = channel

        self.context = self.playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Avoid webdriver detection
        self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self.page

    def close(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("Browser closed.")

    def _save_debug_snapshot(self, tag: str):
        """Saves a screenshot + HTML dump of the current page for post-mortem debugging."""
        debug_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs', 'debug'))
        os.makedirs(debug_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(debug_dir, f"{tag}_{ts}")
        try:
            self.page.screenshot(path=f"{base}.png", full_page=True)
            with open(f"{base}.html", "w", encoding="utf-8") as f:
                f.write(self.page.content())
            # 실제 게시글 본문은 cafe_main iframe 안에 있어서 self.page.content()에는
            # 안 잡힌다. 진단이 의미 있으려면 iframe 내부 문서도 따로 저장해야 한다.
            frame = self.page.frame(name="cafe_main")
            if frame:
                with open(f"{base}_iframe.html", "w", encoding="utf-8") as f:
                    f.write(frame.content())
            logger.error(f"진단 정보 저장: {base}.png / {base}.html" + (f" / {base}_iframe.html" if frame else ""))
        except Exception as e:
            logger.error(f"진단 정보 저장 실패: {e}")

    def _start_network_capture(self):
        """
        Starts recording lightweight metadata (url/status/content-type, plus
        a body preview for JSON responses) for non-static-asset responses.
        Used to diagnose article-load failures with real network evidence
        instead of guessing from the rendered DOM alone. Returns (log, handler);
        pass both to _stop_network_capture() when done, and the log itself to
        _dump_network_log() if you want to persist it.
        """
        log = []
        static_exts = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ico")

        def on_response(response):
            url = response.url
            if any(url.split("?")[0].endswith(ext) for ext in static_exts):
                return
            try:
                content_type = response.headers.get("content-type", "")
            except Exception:
                content_type = ""
            entry = {"url": url, "status": response.status, "content_type": content_type}
            if "json" in content_type:
                try:
                    entry["body_preview"] = response.text()[:4000]
                except Exception:
                    pass
            log.append(entry)

        self.page.on("response", on_response)
        return log, on_response

    def _stop_network_capture(self, handler):
        try:
            self.page.remove_listener("response", handler)
        except Exception:
            pass

    def _dump_network_log(self, log, tag):
        debug_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs', 'debug'))
        os.makedirs(debug_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"{tag}_{ts}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(log, f, ensure_ascii=False, indent=2)
            logger.error(f"네트워크 응답 기록 저장: {path} ({len(log)}건)")
        except Exception as e:
            logger.error(f"네트워크 응답 기록 저장 실패: {e}")

    def _wait_for_article_body(self):
        """
        Waits for the (possibly dynamically-attached) cafe_main iframe and
        for the article body images inside it. Returns the root (frame or
        page) to query further, or None if the body never rendered in time.
        """
        try:
            self.page.wait_for_selector('iframe[name="cafe_main"]', timeout=15000)
        except PlaywrightTimeoutError:
            pass  # some articles render without this iframe; fall through

        frame = self.page.frame(name="cafe_main")
        root = frame if frame else self.page

        try:
            root.wait_for_selector(".se-module-image, .se-image-resource, img", timeout=20000)
            return root
        except PlaywrightTimeoutError:
            return None

    def run_interactive_login(self):
        """Opens Naver Login page and lets the user manually authenticate."""
        self.start_browser(headless=False)
        logger.info("Navigating to Naver Login Page...")
        self.page.goto("https://nid.naver.com/nidlogin.login")
        logger.info("Please login in the browser window, complete any 2-factor authentication, and verify the login is successful.")
        input("Once you are fully logged in and can see your Naver landing page, press ENTER here to save session and close browser...")

        # Save storage state
        cookies = self.context.cookies()
        logger.info(f"Login session saved successfully. Saved {len(cookies)} cookies.")
        self.close()

    def check_login_status(self) -> bool:
        """Navigates to naver main and checks if user is logged in."""
        logger.info("Checking login status...")
        self.page.goto("https://www.naver.com")
        self.page.wait_for_timeout(2000)

        # Naver home has profile area. If logged in, element like '#gnb_name' or logout button exists
        # If not, login button 'a.gnb_btn_login' exists
        is_logged_in = False
        try:
            if self.page.locator("#gnb_name").is_visible() or self.page.locator(".MyView-module__my_info___HdrrQ").is_visible():
                is_logged_in = True
            elif not self.page.locator(".gnb_btn_login").is_visible():
                # fallback checks
                is_logged_in = True
        except Exception:
            pass

        logger.info(f"Login check result: {'LOGGED IN' if is_logged_in else 'NOT LOGGED IN'}")
        return is_logged_in

    def scrape_today_newspaper(self, target_date: str) -> dict:
        """
        Navigates to cafe, finds the post for target_date, extracts image URLs, and returns metadata.
        """
        # SPA URL or classic URL
        cafe_url = "https://cafe.naver.com/f-e/cafes/31064119/menus/10?viewType=L"
        logger.info(f"Navigating to Cafe Menu: {cafe_url}")
        self.page.goto(cafe_url)
        self.page.wait_for_load_state("networkidle")

        # Naver Cafe might load the article list inside an iframe or directly in SPA.
        # Let's inspect list elements.
        # In classic, list is in iframe #cafe_main.
        # Let's find if iframe exists and use frame if it does.
        frame = self.page.frame(name="cafe_main")
        root = frame if frame else self.page

        # Wait a bit for list elements to render
        root.wait_for_timeout(3000)

        # Let's search for the list items.
        # Selectors: a.article, a.article_title inside table
        logger.info("Searching for article list...")
        articles = []

        # Try extracting articles from table rows
        rows = root.locator("tr").all()
        logger.info(f"Found {len(rows)} potential table rows.")

        # If no table rows, check modern SPA elements
        if not rows:
            rows = root.locator("li").all()
            logger.info(f"Found {len(rows)} potential list items.")

        target_post = None

        # 게시글 제목은 "YY.M.D 신문스크랩" 형태(예: "26.9.1 신문스크랩", 앞자리 0 없음)를
        # 사용한다. 앞뒤로 숫자가 더 붙지 않는 정확한 날짜만 매칭해서(예: "26.9.1"이
        # "26.9.10"에 포함되어 오매칭되는 것을 방지), 오늘 게시글이 아직 없을 때
        # 엉뚱한 과거 게시글을 잘못 채택하지 않도록 한다. 오늘 것을 못 찾으면 반드시
        # None을 반환해서 (임의로 예전 게시글을 대신 쓰지 않고) 호출한 쪽에서 재시도하게 한다.
        year, month, day = target_date.split("-")
        yy = year[2:]
        date_pattern = re.compile(
            rf'(?<!\d){re.escape(yy)}\.0?{int(month)}\.0?{int(day)}(?!\d)'
        )

        for row in rows:
            # Also extract anchor link
            link_el = row.locator("a.article, a.article_title, a").first
            if not link_el or not link_el.is_visible():
                continue

            title = link_el.inner_text().strip()
            href = link_el.get_attribute("href") or ""

            is_match = bool(date_pattern.search(title))

            if is_match and href:
                # Construct clean URL
                # href can be javascript:clickArticle(...) or a path /ArticleRead.nhn?... or a full URL
                post_url = href
                if not href.startswith("http"):
                    post_url = "https://cafe.naver.com" + href

                # Extract article ID from URL/click script.
                # The modern URL is .../articles/<id>?..., so check that
                # specific pattern before falling back to legacy
                # ?articleid=<id> or a bare digit run (which would otherwise
                # match the cafe ID appearing earlier in the URL).
                article_id = ""
                id_match = re.search(r'/articles/(\d+)', post_url)
                if not id_match:
                    id_match = re.search(r'articleid=(\d+)', post_url, re.IGNORECASE)
                if id_match:
                    article_id = id_match.group(1)
                else:
                    id_match_href = re.search(r'(\d+)', href)
                    if id_match_href:
                        article_id = id_match_href.group(1)

                target_post = {
                    "title": title,
                    "url": post_url,
                    "id": article_id,
                    "date": target_date
                }
                logger.info(f"Found matching post: {title} (URL: {post_url}, ID: {article_id})")
                break

        if not target_post:
            logger.warning(f"Could not find a post matching date {target_date}.")
            return None

        # Navigate to the article. Capture network activity throughout so that,
        # if every rendering attempt below fails, we have real evidence (API
        # status codes / bodies) instead of only a blank DOM to guess from.
        network_log, network_handler = self._start_network_capture()
        try:
            logger.info(f"Opening post: {target_post['title']}")
            if "javascript:" in target_post['url']:
                # Click the element instead
                # find the link element in the list again and click it
                link_el.click()
            else:
                self.page.goto(target_post['url'])

            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_timeout(3000)

            root = self._wait_for_article_body()

            if root is None:
                logger.warning("게시글 본문 로딩 타임아웃, 새로고침 후 재시도합니다.")
                self._save_debug_snapshot("post_load_timeout_1")
                self.page.reload()
                self.page.wait_for_load_state("networkidle")
                self.page.wait_for_timeout(3000)
                root = self._wait_for_article_body()

            if root is None and target_post["id"]:
                # 최신(ca-fe) SPA가 계속 렌더링에 실패하면, 훨씬 단순한 예전 방식
                # 게시글 페이지로 한 번 더 시도해본다.
                legacy_url = f"https://cafe.naver.com/ArticleRead.nhn?clubid={self.CAFE_ID}&articleid={target_post['id']}"
                logger.warning(f"최신 페이지 로딩 실패, 예전 방식 페이지로 재시도합니다: {legacy_url}")
                self._save_debug_snapshot("post_load_timeout_2")
                self.page.goto(legacy_url)
                self.page.wait_for_load_state("networkidle")
                self.page.wait_for_timeout(3000)
                root = self._wait_for_article_body()

            if root is None:
                self._save_debug_snapshot("post_load_timeout_3")
                self._dump_network_log(network_log, "post_load_network")
                logger.error(f"게시글 본문에서 이미지를 찾지 못했습니다 (post_url={target_post['url']}).")
                return None
        finally:
            self._stop_network_capture(network_handler)

        # Extract images
        # Naver Cafe editor (SmartEditor One) images are in `div.se-image-resource img` or `div.se-module-image img`
        # Let's extract all image tags
        logger.info("Extracting image elements...")
        img_locators = root.locator("div.se-image-resource img, div.se-module-image img, .se-component-image img").all()

        # Fallback to general images inside article content if editor classes aren't matched
        if not img_locators:
            img_locators = root.locator("div.article-viewer img, #tbody img").all()

        logger.info(f"Found {len(img_locators)} potential images.")

        image_urls = []
        for img in img_locators:
            # Naver Cafe images usually have the original source URL in data-lazy-src or src attribute.
            # Usually, original image source can be found in data-src, data-lazy-src, or src.
            # Also, URL often ends with ?type=w800 or similar thumbnail indicators. Removing the query parameter or changing it to type=w1080 or type=org can give original resolution.
            # Let's inspect attributes:
            src = img.get_attribute("data-src") or img.get_attribute("data-lazy-src") or img.get_attribute("src") or ""
            if not src:
                continue
            logger.info(f"Raw image src found: {src}")
            # Filter out UI images, smileys, stickers, profile pictures etc.
            if "cafe.naver.com" not in src and "post.naver.com" not in src and "naver.net" not in src and "pstatic.net" not in src:
                continue
            if "/static/" in src or "emoticon" in src or "sticker" in src or "profile" in src or "btn" in src:
                continue

            # Standardize URL to get high-resolution image
            # cafeptthumb-phinf.pstatic.net URLs already use type=w1600 which is high-res.
            # type=org is NOT supported on this CDN and returns 404.
            # Keep original type param if present; otherwise request w1600.
            if "type=" not in src:
                if "?" in src:
                    src += "&type=w1600"
                else:
                    src += "?type=w1600"

            if src not in image_urls:
                image_urls.append(src)

        logger.info(f"Extracted {len(image_urls)} unique high-res image URLs.")

        # Grab context cookies for image downloader
        cookies = self.context.cookies()

        return {
            "post_title": target_post["title"],
            "post_url": target_post["url"],
            "post_id": target_post["id"],
            "image_urls": image_urls,
            "cookies": cookies
        }
