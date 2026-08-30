import os
import re
import time
from playwright.sync_api import sync_playwright, Page, BrowserContext
from app.utils import logger

class NaverCafeScraper:
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

        for row in rows:
            text = row.inner_text()
            # Look for date pattern in the row: e.g. YYYY.MM.DD or HH:MM or today's date pattern
            # Let's also check if the row text contains parts of the target date (e.g. "08.21" or "08-21" or "8월 21일")
            # Usually, Naver Cafe lists show dates as:
            # - Today: "HH:MM" (e.g. "07:30")
            # - Older: "YYYY.MM.DD." (e.g. "2026.08.20.")
            # Let's also check target date components: e.g. "2026.08.21" or "08.21"
            date_dots = target_date.replace("-", ".")  # "2026.08.21"
            date_short = date_dots[5:]  # "08.21"

            # Also extract anchor link
            link_el = row.locator("a.article, a.article_title, a").first
            if not link_el or not link_el.is_visible():
                continue

            title = link_el.inner_text().strip()
            href = link_el.get_attribute("href") or ""

            # Check if this row matches our date or title criteria
            # E.g. Title might contain the date "8월 21일" or row contains the date
            is_match = False
            # Check if row mentions the short date (e.g. "08.21" or "8.21")
            # Or if the title mentions the date (e.g. "8/21" or "8월 21일")
            month_day_match = re.search(r'(\d{1,2})[월/.]\s*(\d{1,2})', title)
            if month_day_match:
                m, d = int(month_day_match.group(1)), int(month_day_match.group(2))
                t_m, t_d = int(target_date.split("-")[1]), int(target_date.split("-")[2])
                if m == t_m and d == t_d:
                    is_match = True

            if not is_match and (date_dots in text or date_short in text):
                is_match = True

            # If date is today, row date might be "HH:MM". Let's match if title contains the target day pattern
            if not is_match and ":" in text and len(text.split("\n")) > 1:
                # Row has time (which means it was posted today). Let's see if title looks like a newspaper post
                # Typically newspaper posts have "신문" or "뉴스" or similar keywords
                if "신문" in title or "뉴스" in title:
                    is_match = True

            if is_match and href:
                # Construct clean URL
                # href can be javascript:clickArticle(...) or a path /ArticleRead.nhn?... or a full URL
                post_url = href
                if not href.startswith("http"):
                    post_url = "https://cafe.naver.com" + href

                # Extract article ID from URL/click script
                article_id = ""
                id_match = re.search(r'articleid=(\d+)', post_url, re.IGNORECASE)
                if id_match:
                    article_id = id_match.group(1)
                else:
                    # check if it is in href
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

        # Navigate to the article
        logger.info(f"Opening post: {target_post['title']}")
        if "javascript:" in target_post['url']:
            # Click the element instead
            # find the link element in the list again and click it
            link_el.click()
        else:
            self.page.goto(target_post['url'])

        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(3000)

        # Naver Cafe articles are loaded in #cafe_main iframe.
        frame = self.page.frame(name="cafe_main")
        root = frame if frame else self.page

        # Wait for article body
        root.wait_for_selector(".se-module-image, .se-image-resource, img", timeout=15000)

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
