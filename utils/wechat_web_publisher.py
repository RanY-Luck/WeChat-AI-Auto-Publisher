import os
import signal
import shutil
import subprocess
import time
from datetime import datetime
from urllib.parse import urlparse


class WeChatWebPublisher:
    PROFILE_LOCK_FILENAMES = (
        "SingletonCookie",
        "SingletonLock",
        "SingletonSocket",
    )
    DEFAULT_BROWSER_ARGS = (
        "--no-sandbox",
        "--disable-dev-shm-usage",
    )

    def __init__(
        self,
        profile_dir,
        headless=False,
        timeout_ms=15000,
        screenshots_dir="temp/wechat-web-publisher",
        base_url="https://mp.weixin.qq.com",
        executable_path=None,
        browser_args=None,
        force_release_profile=None,
    ):
        self.profile_dir = profile_dir
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.screenshots_dir = screenshots_dir
        self.base_url = base_url
        self.executable_path = executable_path or self._detect_chromium_executable()
        if browser_args is None:
            browser_args = list(self.DEFAULT_BROWSER_ARGS) if self.executable_path else []
        self.browser_args = list(browser_args)
        if force_release_profile is None:
            force_release_profile = os.environ.get("AUTO_OPEN_BROWSER", "").lower() == "true"
        self.force_release_profile = bool(force_release_profile)
        self._playwright = None
        self._context = None

    def launch_persistent_context(self, playwright=None):
        if self.force_release_profile:
            self._terminate_profile_processes()
        self._cleanup_stale_profile_lock()
        runtime = playwright or self._start_playwright_runtime()
        launch_kwargs = {
            "user_data_dir": self.profile_dir,
            "headless": self.headless,
        }
        if self.executable_path:
            launch_kwargs["executable_path"] = self.executable_path
        if self.browser_args:
            launch_kwargs["args"] = self.browser_args
        context = runtime.chromium.launch_persistent_context(**launch_kwargs)
        if hasattr(context, "set_default_timeout"):
            context.set_default_timeout(self.timeout_ms)
        self._context = context
        return context

    def close(self):
        context = self._context
        runtime = self._playwright
        self._context = None
        self._playwright = None

        if context is not None and hasattr(context, "close"):
            context.close()
        if runtime is not None and hasattr(runtime, "stop"):
            runtime.stop()

    def is_logged_in(self, page):
        if self._is_authenticated_url(getattr(page, "url", "")):
            return True
        if self._has_any_element(page, self._authenticated_shell_selectors()):
            return True
        if self._has_element(page, self._login_entry_selector()):
            return False
        return False

    def open_draft_list(self, page):
        page.goto(
            self._home_url(),
            wait_until="domcontentloaded",
            timeout=self.timeout_ms,
        )
        page.locator(self._draft_list_entry_selector()).click()
        return page

    def publish_latest_draft(self, page):
        try:
            page.goto(
                self._home_url(),
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )
            initial_page_count = self._get_page_count(page)
            draft_card = self._locate_latest_draft_card(page)
            self._hover_locator(draft_card)
            self._click_locator(
                draft_card.locator(self._draft_publish_entry_selector()),
                force=True,
            )
            publish_page = self._resolve_publish_page(page, initial_page_count)
            if hasattr(publish_page, "wait_for_load_state"):
                publish_page.wait_for_load_state("domcontentloaded")
            self._click_locator(publish_page.locator(self._editor_publish_button_selector()))
            publish_page.wait_for_timeout(2000)
            self._click_first_visible_primary_button(publish_page)
            publish_page.wait_for_timeout(1500)
            self._click_first_visible_primary_button(publish_page, required=False)
        except Exception:
            try:
                self.save_failure_screenshot(page, prefix="publish-failed")
            except Exception:
                pass
            raise

    def save_failure_screenshot(self, page, prefix="failure", timestamp=None):
        os.makedirs(self.screenshots_dir, exist_ok=True)
        resolved_timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        screenshot_path = os.path.join(
            self.screenshots_dir,
            f"{prefix}-{resolved_timestamp}.png",
        )
        page.screenshot(path=screenshot_path, full_page=True)
        return screenshot_path

    def _start_playwright_runtime(self):
        if self._playwright is None:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
        return self._playwright

    def _detect_chromium_executable(self):
        for command in ("chromium", "chromium-browser"):
            resolved = shutil.which(command)
            if resolved:
                return resolved
        return None

    def _cleanup_stale_profile_lock(self):
        if self._has_active_profile_process():
            return

        for filename in self.PROFILE_LOCK_FILENAMES:
            path = os.path.join(self.profile_dir, filename)
            try:
                if os.path.lexists(path):
                    os.unlink(path)
            except OSError:
                pass

    def _has_active_profile_process(self):
        return bool(self._profile_process_ids())

    def _profile_process_ids(self):
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid=,args="],
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            return []

        profile_marker = f"--user-data-dir={self.profile_dir}"
        profile_hint = os.path.normpath(self.profile_dir)
        pids = []

        for line in result.stdout.splitlines():
            normalized_line = line.strip()
            if not normalized_line:
                continue
            parts = normalized_line.split(None, 1)
            if len(parts) != 2:
                continue
            pid_text, args_text = parts
            lowered_line = args_text.lower()
            if "chrom" not in lowered_line:
                continue
            if profile_marker in args_text or profile_hint in args_text:
                try:
                    pids.append(int(pid_text))
                except ValueError:
                    continue
        return pids

    def _terminate_profile_processes(self):
        pids = [pid for pid in self._profile_process_ids() if pid != os.getpid()]
        if not pids:
            return

        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        for _ in range(10):
            if not self._profile_process_ids():
                return
            time.sleep(0.5)

        for pid in self._profile_process_ids():
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def _has_element(self, page, selector):
        locator = page.locator(selector)
        if hasattr(locator, "count"):
            return locator.count() > 0
        if hasattr(locator, "is_visible"):
            return bool(locator.is_visible())
        return False

    def _has_any_element(self, page, selectors):
        return any(self._has_element(page, selector) for selector in selectors)

    def _wait_for_element(self, page, selector, timeout_ms):
        max_attempts = max(1, timeout_ms // 500)
        for _ in range(max_attempts):
            if self._has_element(page, selector):
                return True
            if hasattr(page, "wait_for_timeout"):
                page.wait_for_timeout(500)
        return self._has_element(page, selector)

    def _get_page_count(self, page):
        context = self._resolve_page_context(page)
        pages = getattr(context, "pages", None) if context is not None else None
        if pages is None:
            return 0
        return len(pages)

    def _locate_latest_draft_card(self, page):
        if self._wait_for_element(page, self._recent_draft_card_selector(), timeout_ms=5000):
            return page.locator(self._recent_draft_card_selector()).first
        self.open_draft_list(page)
        return page.locator(self._latest_draft_selector()).first

    def _resolve_publish_page(self, page, initial_page_count):
        context = self._resolve_page_context(page)
        if context is None:
            return page

        max_attempts = max(1, self.timeout_ms // 500)
        for _ in range(max_attempts):
            pages = getattr(context, "pages", None) or []
            if len(pages) > initial_page_count:
                return pages[-1]
            if self._is_editor_url(getattr(page, "url", "")):
                return page
            if hasattr(page, "wait_for_timeout"):
                page.wait_for_timeout(500)

        if self._is_editor_url(getattr(page, "url", "")):
            return page
        raise RuntimeError("未找到发表编辑页")

    def _resolve_page_context(self, page):
        context = getattr(page, "context", None)
        if context is not None:
            return context
        return self._context

    def _click_first_visible_primary_button(self, page, required=True):
        selector = self._visible_primary_button_selector()
        if not self._has_element(page, selector):
            if required:
                raise RuntimeError("未找到可见的确认按钮")
            return False
        self._click_locator(page.locator(selector).first)
        return True

    def _hover_locator(self, locator):
        if hasattr(locator, "hover"):
            locator.hover()

    def _click_locator(self, locator, **kwargs):
        try:
            locator.click(**kwargs)
        except TypeError:
            locator.click()

    def _is_authenticated_url(self, current_url):
        if not current_url:
            return False
        parsed = urlparse(current_url)
        return parsed.netloc == "mp.weixin.qq.com" and parsed.path.startswith("/cgi-bin/")

    def _is_editor_url(self, current_url):
        if not current_url:
            return False
        parsed = urlparse(current_url)
        return parsed.netloc == "mp.weixin.qq.com" and parsed.path == "/cgi-bin/appmsg"

    def _home_url(self):
        return self.base_url

    def _login_entry_selector(self):
        return "text=扫码登录"

    def _authenticated_shell_selectors(self):
        return (
            "text=近期草稿",
            ".weui-desktop-account__info",
        )

    def _recent_draft_card_selector(self):
        return ".publish_card_container"

    def _draft_list_entry_selector(self):
        return "text=草稿箱"

    def _latest_draft_selector(self):
        return ".publish_card_container .weui-desktop-card:first-child"

    def _draft_publish_entry_selector(self):
        return ".publish_enable_button a"

    def _editor_publish_button_selector(self):
        return "button.mass_send"

    def _visible_primary_button_selector(self):
        return "button.weui-desktop-btn.weui-desktop-btn_primary:visible"
