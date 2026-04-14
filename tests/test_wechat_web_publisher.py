import os
import builtins
import importlib
import sys
import tempfile
import unittest
import shutil
import base64
from pathlib import Path
from unittest.mock import patch


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def count(self):
        return self.page.counts.get(self.selector, 0)

    def is_visible(self):
        return self.page.counts.get(self.selector, 0) > 0

    def click(self, *args, **kwargs):
        self.page.click_selector(self.selector, **kwargs)

    def hover(self):
        self.page.hover_selector(self.selector)

    def locator(self, selector):
        return FakeLocator(self.page, selector)

    def screenshot(self, **kwargs):
        self.page.calls.append(("locator_screenshot", self.selector, kwargs))
        return b"ok"

    def get_attribute(self, name):
        if self.selector == self.page.fail_get_attribute_selector:
            raise self.page.fail_get_attribute_exception
        return self.page.attributes.get((self.selector, name))


class FakePage:
    def __init__(
        self,
        counts=None,
        goto_side_effects=None,
        wait_side_effects=None,
        attributes=None,
        fail_get_attribute_selector=None,
        fail_get_attribute_exception=None,
        fail_click_selector=None,
        fail_click_exception=None,
        screenshot_exception=None,
        evaluate_result=None,
        evaluate_exception=None,
        url="https://mp.weixin.qq.com",
        popup_page=None,
    ):
        self.counts = counts or {}
        self.goto_side_effects = list(goto_side_effects or [])
        self.wait_side_effects = list(wait_side_effects or [])
        self.attributes = attributes or {}
        self.fail_get_attribute_selector = fail_get_attribute_selector
        self.fail_get_attribute_exception = fail_get_attribute_exception
        self.fail_click_selector = fail_click_selector
        self.fail_click_exception = fail_click_exception
        self.fail_click_sequence = {}
        self.screenshot_exception = screenshot_exception
        self.evaluate_result = evaluate_result
        self.evaluate_exception = evaluate_exception
        self.url = url
        self.popup_page = popup_page
        self.context = None
        self.calls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.url = url
        self.calls.append(("goto", url, wait_until, timeout))
        if self.goto_side_effects:
            self.counts = dict(self.goto_side_effects.pop(0))

    def locator(self, selector):
        self.calls.append(("locator", selector))
        return FakeLocator(self, selector)

    def screenshot(self, **kwargs):
        self.calls.append(("screenshot", kwargs))
        if self.screenshot_exception is not None:
            raise self.screenshot_exception
        return b"ok"

    def evaluate(self, expression):
        self.calls.append(("evaluate", expression))
        if self.evaluate_exception is not None:
            raise self.evaluate_exception
        return self.evaluate_result

    def wait_for_timeout(self, value):
        self.calls.append(("wait_for_timeout", value))
        if self.wait_side_effects:
            self.counts = dict(self.wait_side_effects.pop(0))

    def wait_for_load_state(self, state=None):
        self.calls.append(("wait_for_load_state", state))

    def click_selector(self, selector):
        return self.click_selector_with_kwargs(selector)

    def click_selector_with_kwargs(self, selector, **kwargs):
        if kwargs:
            self.calls.append(("click", selector, kwargs))
        else:
            self.calls.append(("click", selector))
        if selector in self.fail_click_sequence and self.fail_click_sequence[selector]:
            next_exception = self.fail_click_sequence[selector].pop(0)
            if next_exception is not None:
                raise next_exception
        if selector == self.fail_click_selector:
            if self.fail_click_exception is not None:
                raise self.fail_click_exception
            raise RuntimeError(f"failed click for {selector}")
        if selector == ".publish_enable_button a" and self.popup_page is not None and self.context is not None:
            self.popup_page.context = self.context
            if self.popup_page not in self.context.pages:
                self.context.pages.append(self.popup_page)

    def hover_selector(self, selector):
        self.calls.append(("hover", selector))


class FakeContext:
    def __init__(self, pages=None):
        self.pages = list(pages or [])
        for page in self.pages:
            page.context = self
        self.timeout_value = None
        self.close_calls = 0

    def set_default_timeout(self, value):
        self.timeout_value = value

    def close(self):
        self.close_calls += 1


class FakeChromium:
    def __init__(self, context):
        self.context = context
        self.called_kwargs = None

    def launch_persistent_context(self, **kwargs):
        self.called_kwargs = kwargs
        return self.context


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class WeChatWebPublisherTest(unittest.TestCase):
    def _load_publisher_class(self):
        module = importlib.import_module("utils.wechat_web_publisher")
        return module.WeChatWebPublisher

    def _create_publisher(self, **kwargs):
        publisher_class = self._load_publisher_class()
        return publisher_class(profile_dir="profile-dir", **kwargs)

    def test_module_import_does_not_require_playwright(self):
        module_name = "utils.wechat_web_publisher"
        sys.modules.pop(module_name, None)

        real_import = builtins.__import__

        def guarded_import(name, globals_=None, locals_=None, fromlist=(), level=0):
            if name.startswith("playwright"):
                raise AssertionError("playwright import attempted at module import time")
            return real_import(name, globals_, locals_, fromlist, level)

        with patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(module_name)

        self.assertTrue(hasattr(module, "WeChatWebPublisher"))

    def test_login_check_returns_false_when_login_ui_present(self):
        publisher = self._create_publisher()
        page = FakePage(counts={"text=扫码登录": 1})
        self.assertFalse(publisher.is_logged_in(page))

    def test_login_check_returns_true_when_authenticated_ui_present(self):
        publisher = self._create_publisher()
        page = FakePage(counts={".weui-desktop-account__info": 1})
        self.assertTrue(publisher.is_logged_in(page))

    def test_login_check_returns_true_for_authenticated_backend_url_even_if_login_text_exists(self):
        publisher = self._create_publisher()
        page = FakePage(
            counts={"text=扫码登录": 1, "text=近期草稿": 1},
            url="https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=123",
        )
        self.assertTrue(publisher.is_logged_in(page))

    def test_login_check_returns_false_when_state_is_ambiguous(self):
        publisher = self._create_publisher()
        page = FakePage(counts={})
        self.assertFalse(publisher.is_logged_in(page))

    def test_publish_latest_draft_clicks_expected_controls_in_order(self):
        publisher = self._create_publisher()
        publish_page = FakePage(
            counts={
                "button.mass_send": 1,
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                "text=发表成功": 1,
            },
            url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
        )
        page = FakePage(
            goto_side_effects=[
                {
                    ".publish_card_container": 1,
                    ".publish_enable_button a": 1,
                },
                {
                    ".publish_card_container": 1,
                },
            ],
            popup_page=publish_page,
        )
        FakeContext([page])

        publisher.publish_latest_draft(page)

        page_actions = [(entry[0], entry[1]) for entry in page.calls if entry[0] in {"click", "hover"}]
        publish_clicks = [entry[1] for entry in publish_page.calls if entry[0] == "click"]
        self.assertEqual(
            page_actions,
            [
                ("hover", ".publish_card_container"),
                ("click", ".publish_enable_button a"),
            ],
        )
        self.assertEqual(
            publish_clicks,
            [
                "button.mass_send",
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible",
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible",
            ],
        )

    def test_publish_latest_draft_waits_for_delayed_primary_confirmation_button(self):
        publisher = self._create_publisher()
        publish_page = FakePage(
            counts={
                "button.mass_send": 1,
            },
            wait_side_effects=[
                {
                    "button.mass_send": 1,
                },
                {
                    "button.mass_send": 1,
                    "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                    "text=发表成功": 1,
                },
                {
                    "button.mass_send": 1,
                    "text=发表成功": 1,
                },
            ],
            url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
        )
        page = FakePage(
            goto_side_effects=[
                {
                    ".publish_card_container": 1,
                    ".publish_enable_button a": 1,
                },
                {
                    ".publish_card_container": 1,
                },
            ],
            popup_page=publish_page,
        )
        FakeContext([page])

        publisher.publish_latest_draft(page)

        publish_clicks = [entry[1] for entry in publish_page.calls if entry[0] == "click"]
        self.assertEqual(
            publish_clicks,
            [
                "button.mass_send",
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible",
            ],
        )

    def test_publish_latest_draft_retries_primary_confirmation_after_transient_dialog_intercepts_click(self):
        publisher = self._create_publisher()
        publish_page = FakePage(
            counts={
                "button.mass_send": 1,
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
            },
            wait_side_effects=[
                {
                    "button.mass_send": 1,
                    "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                    "text=发表成功": 1,
                },
                {
                    "button.mass_send": 1,
                    "text=发表成功": 1,
                },
            ],
            url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
        )
        publish_page.fail_click_sequence = {
            "button.weui-desktop-btn.weui-desktop-btn_primary:visible": [
                RuntimeError("dialog intercepts pointer events"),
            ],
        }
        page = FakePage(
            goto_side_effects=[
                {
                    ".publish_card_container": 1,
                    ".publish_enable_button a": 1,
                },
                {
                    ".publish_card_container": 1,
                },
            ],
            popup_page=publish_page,
        )
        FakeContext([page])

        publisher.publish_latest_draft(page)

        publish_clicks = [entry[1] for entry in publish_page.calls if entry[0] == "click"]
        self.assertEqual(
            publish_clicks,
            [
                "button.mass_send",
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible",
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible",
            ],
        )

    def test_publish_latest_draft_raises_when_publish_success_cannot_be_confirmed(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            publish_page = FakePage(
                counts={
                    "button.mass_send": 1,
                    "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                },
                url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
            )
            page = FakePage(
                counts={".publish_card_container": 1},
                popup_page=publish_page,
            )
            FakeContext([page])

            with self.assertRaises(RuntimeError) as raised:
                publisher.publish_latest_draft(page)

            self.assertIn("未确认发表成功", str(raised.exception))
            self.assertTrue(any(entry[0] == "screenshot" for entry in page.calls))

    def test_publish_latest_draft_requires_latest_draft_to_leave_publishable_state(self):
        publisher = self._create_publisher()
        publish_page = FakePage(
            counts={
                "button.mass_send": 1,
                "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                "text=发表成功": 1,
            },
            url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
        )
        page = FakePage(
            goto_side_effects=[
                {
                    ".publish_card_container": 1,
                    ".publish_enable_button a": 1,
                },
                {
                    ".publish_card_container": 1,
                },
            ],
            popup_page=publish_page,
        )
        FakeContext([page])

        publisher.publish_latest_draft(page)

        goto_calls = [entry for entry in page.calls if entry[0] == "goto"]
        self.assertGreaterEqual(len(goto_calls), 2)

    def test_publish_latest_draft_does_not_treat_original_home_page_as_publish_success(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            publish_page = FakePage(
                counts={
                    "button.mass_send": 1,
                    "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                },
                url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
            )
            page = FakePage(
                counts={
                    ".publish_card_container": 1,
                    "text=近期草稿": 1,
                    ".weui-desktop-account__info": 1,
                },
                url="https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=123",
                popup_page=publish_page,
            )
            FakeContext([page])

            with self.assertRaises(RuntimeError) as raised:
                publisher.publish_latest_draft(page)

            self.assertIn("未确认发表成功", str(raised.exception))

    def test_publish_latest_draft_raises_when_latest_draft_still_has_publish_entry(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            publish_page = FakePage(
                counts={
                    "button.mass_send": 1,
                    "button.weui-desktop-btn.weui-desktop-btn_primary:visible": 1,
                    "text=发表成功": 1,
                },
                url="https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77",
            )
            page = FakePage(
                goto_side_effects=[
                    {
                        ".publish_card_container": 1,
                        ".publish_enable_button a": 1,
                    },
                    {
                        ".publish_card_container": 1,
                        ".publish_enable_button a": 1,
                    },
                ],
                popup_page=publish_page,
            )
            FakeContext([page])

            with self.assertRaises(RuntimeError) as raised:
                publisher.publish_latest_draft(page)

            self.assertIn("草稿仍可发表", str(raised.exception))

    def test_open_draft_list_navigates_and_clicks_draft_entry(self):
        publisher = self._create_publisher(timeout_ms=4321)
        page = FakePage()

        returned_page = publisher.open_draft_list(page)

        self.assertIs(returned_page, page)
        self.assertEqual(
            page.calls,
            [
                ("goto", "https://mp.weixin.qq.com", "domcontentloaded", 4321),
                ("locator", "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"),
                ("locator", "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"),
                ("locator", "text=草稿箱"),
                ("click", "text=草稿箱"),
            ],
        )

    def test_open_draft_list_prefers_direct_draft_href_when_available(self):
        publisher = self._create_publisher(timeout_ms=4321)
        page = FakePage(
            counts={"a[href*='/cgi-bin/appmsg'][href*='action=list_card']": 1},
            attributes={
                ("a[href*='/cgi-bin/appmsg'][href*='action=list_card']", "href"): (
                    "/cgi-bin/appmsg?begin=0&count=10&type=77&action=list_card&token=123&lang=zh_CN"
                ),
            }
        )

        returned_page = publisher.open_draft_list(page)

        self.assertIs(returned_page, page)
        self.assertEqual(
            page.calls,
            [
                ("goto", "https://mp.weixin.qq.com", "domcontentloaded", 4321),
                ("locator", "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"),
                ("locator", "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"),
                (
                    "goto",
                    "https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=10&type=77&action=list_card&token=123&lang=zh_CN",
                    "domcontentloaded",
                    4321,
                ),
            ],
        )

    def test_open_draft_list_builds_draft_href_from_home_token_when_menu_href_missing(self):
        publisher = self._create_publisher(timeout_ms=4321)
        page = FakePage(
            url="https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=456",
        )

        returned_page = publisher.open_draft_list(page)

        self.assertIs(returned_page, page)
        self.assertEqual(
            page.calls,
            [
                ("goto", "https://mp.weixin.qq.com", "domcontentloaded", 4321),
                ("locator", "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"),
                ("locator", "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"),
                (
                    "goto",
                    "https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=10&type=77&action=list_card&token=456&lang=zh_CN",
                    "domcontentloaded",
                    4321,
                ),
            ],
        )

    def test_open_draft_list_skips_get_attribute_when_menu_link_missing(self):
        publisher = self._create_publisher(timeout_ms=4321)
        selector = "a[href*='/cgi-bin/appmsg'][href*='action=list_card']"
        page = FakePage(
            counts={},
            url="https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=789",
            fail_get_attribute_selector=selector,
            fail_get_attribute_exception=RuntimeError("should not call get_attribute"),
        )

        returned_page = publisher.open_draft_list(page)

        self.assertIs(returned_page, page)
        self.assertEqual(
            page.calls,
            [
                ("goto", "https://mp.weixin.qq.com", "domcontentloaded", 4321),
                ("locator", selector),
                ("locator", selector),
                (
                    "goto",
                    "https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=10&type=77&action=list_card&token=789&lang=zh_CN",
                    "domcontentloaded",
                    4321,
                ),
            ],
        )

    def test_save_failure_screenshot_delegates_to_page_abstraction(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            page = FakePage()

            screenshot_path = publisher.save_failure_screenshot(
                page,
                prefix="publish-failed",
                timestamp="20260407-120000",
            )

            expected_path = os.path.join(
                screenshot_dir,
                "publish-failed-20260407-120000.png",
            )
            self.assertEqual(screenshot_path, expected_path)
            self.assertIn(
                ("screenshot", {"path": expected_path, "full_page": True}),
                page.calls,
            )

    def test_save_login_qr_screenshot_uses_locator_screenshot_for_visible_qr(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            raw_png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK9cAAAAASUVORK5CYII="
            )
            page = FakePage(
                counts={"img.js_login_qrcode": 1},
                evaluate_result=f"data:image/png;base64,{base64.b64encode(raw_png).decode('ascii')}",
            )

            screenshot_path = publisher.save_login_qr_screenshot(
                page,
                prefix="login-qr",
                timestamp="20260407-120000",
            )

            expected_path = os.path.join(
                screenshot_dir,
                "login-qr-20260407-120000.png",
            )
            self.assertEqual(screenshot_path, expected_path)
            self.assertIn(("wait_for_timeout", 1000), page.calls)
            self.assertIn(
                ("locator_screenshot", "img.js_login_qrcode", {"path": expected_path}),
                page.calls,
            )
            self.assertFalse(any(call[0] == "evaluate" for call in page.calls))

    def test_save_login_qr_screenshot_ignores_evaluate_results_and_uses_locator(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            raw_jpeg = base64.b64decode(
                "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
                "//////////////////////////////////////////////////////////////////////////2wBDAf//////////////"
                "//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDAREAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/"
                "xAAVEQEBAAAAAAAAAAAAAAAAAAABAP/aAAwDAQACEAMQAAAB6A//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/"
                "xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AR//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AR//2Q=="
            )
            page = FakePage(
                counts={"img.js_login_qrcode": 1},
                evaluate_result=f"data:image/jpeg;base64,{base64.b64encode(raw_jpeg).decode('ascii')}",
            )

            screenshot_path = publisher.save_login_qr_screenshot(
                page,
                prefix="login-qr",
                timestamp="20260407-120000",
            )

            expected_path = os.path.join(
                screenshot_dir,
                "login-qr-20260407-120000.png",
            )
            self.assertEqual(screenshot_path, expected_path)
            self.assertIn(
                ("locator_screenshot", "img.js_login_qrcode", {"path": expected_path}),
                page.calls,
            )
            self.assertFalse(any(call[0] == "evaluate" for call in page.calls))

    def test_save_login_qr_screenshot_falls_back_to_locator_screenshot_when_export_fails(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            page = FakePage(
                counts={"img.js_login_qrcode": 1},
                evaluate_exception=RuntimeError("canvas export failed"),
            )

            screenshot_path = publisher.save_login_qr_screenshot(
                page,
                prefix="login-qr",
                timestamp="20260407-120000",
            )

            expected_path = os.path.join(
                screenshot_dir,
                "login-qr-20260407-120000.png",
            )
            self.assertEqual(screenshot_path, expected_path)
            self.assertIn(
                ("locator_screenshot", "img.js_login_qrcode", {"path": expected_path}),
                page.calls,
            )

    def test_save_login_qr_screenshot_raises_when_qr_element_missing(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            page = FakePage(counts={})

            with self.assertRaises(RuntimeError) as raised:
                publisher.save_login_qr_screenshot(page)

            self.assertIn("二维码", str(raised.exception))

    def test_publish_failure_keeps_original_error_when_screenshot_also_fails(self):
        with tempfile.TemporaryDirectory() as screenshot_dir:
            publisher = self._create_publisher(screenshots_dir=screenshot_dir)
            original_error = RuntimeError("publish failed")
            publish_page = FakePage(
                counts={"button.mass_send": 1},
                fail_click_selector="button.mass_send",
                fail_click_exception=original_error,
            )
            page = FakePage(
                counts={".publish_card_container": 1},
                popup_page=publish_page,
                screenshot_exception=RuntimeError("screenshot failed"),
            )
            FakeContext([page])

            with self.assertRaises(RuntimeError) as raised:
                publisher.publish_latest_draft(page)

            self.assertIs(raised.exception, original_error)
            self.assertTrue(any(entry[0] == "screenshot" for entry in page.calls))

    def test_launch_persistent_context_uses_provided_playwright_object(self):
        fake_context = FakeContext()
        fake_chromium = FakeChromium(fake_context)
        fake_playwright = FakePlaywright(fake_chromium)
        publisher = self._create_publisher(headless=True, timeout_ms=9876)

        context = publisher.launch_persistent_context(playwright=fake_playwright)

        self.assertIs(context, fake_context)
        self.assertEqual(
            fake_chromium.called_kwargs["user_data_dir"],
            "profile-dir",
        )
        self.assertTrue(fake_chromium.called_kwargs["headless"])
        self.assertEqual(fake_context.timeout_value, 9876)

    def test_launch_persistent_context_prefers_system_chromium_when_available(self):
        fake_context = FakeContext()
        fake_chromium = FakeChromium(fake_context)
        fake_playwright = FakePlaywright(fake_chromium)

        with patch.object(shutil, "which", side_effect=["/usr/bin/chromium", None]):
            publisher = self._create_publisher(headless=False, timeout_ms=1234)

        publisher.launch_persistent_context(playwright=fake_playwright)

        self.assertEqual(
            fake_chromium.called_kwargs["executable_path"],
            "/usr/bin/chromium",
        )
        self.assertEqual(
            fake_chromium.called_kwargs["args"],
            ["--no-sandbox", "--disable-dev-shm-usage"],
        )

    def test_launch_persistent_context_releases_profile_processes_when_force_release_enabled(self):
        fake_context = FakeContext()
        fake_chromium = FakeChromium(fake_context)
        fake_playwright = FakePlaywright(fake_chromium)
        publisher = self._create_publisher(force_release_profile=True)

        with patch.object(publisher, "_terminate_profile_processes") as terminate_processes:
            publisher.launch_persistent_context(playwright=fake_playwright)

        terminate_processes.assert_called_once_with()

    def test_auto_open_browser_does_not_force_release_profile_by_default(self):
        with patch.dict("os.environ", {"AUTO_OPEN_BROWSER": "true"}, clear=False):
            publisher = self._create_publisher()

        self.assertFalse(publisher.force_release_profile)

    def test_launch_persistent_context_cleans_stale_singleton_files_when_profile_unused(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            profile_path = Path(profile_dir)
            for name in ("SingletonCookie", "SingletonLock", "SingletonSocket"):
                (profile_path / name).write_text("stale", encoding="utf-8")

            fake_context = FakeContext()
            fake_chromium = FakeChromium(fake_context)
            fake_playwright = FakePlaywright(fake_chromium)
            publisher_class = self._load_publisher_class()
            publisher = publisher_class(profile_dir=profile_dir)

            with patch.object(
                publisher,
                "_has_active_profile_process",
                return_value=False,
            ):
                publisher.launch_persistent_context(playwright=fake_playwright)

            for name in ("SingletonCookie", "SingletonLock", "SingletonSocket"):
                self.assertFalse((profile_path / name).exists(), name)

    def test_launch_persistent_context_keeps_singleton_files_when_profile_in_use(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            profile_path = Path(profile_dir)
            for name in ("SingletonCookie", "SingletonLock", "SingletonSocket"):
                (profile_path / name).write_text("active", encoding="utf-8")

            fake_context = FakeContext()
            fake_chromium = FakeChromium(fake_context)
            fake_playwright = FakePlaywright(fake_chromium)
            publisher_class = self._load_publisher_class()
            publisher = publisher_class(profile_dir=profile_dir)

            with patch.object(
                publisher,
                "_has_active_profile_process",
                return_value=True,
            ):
                publisher.launch_persistent_context(playwright=fake_playwright)

            for name in ("SingletonCookie", "SingletonLock", "SingletonSocket"):
                self.assertTrue((profile_path / name).exists(), name)

    def test_close_is_idempotent_and_cleans_context_and_runtime(self):
        publisher = self._create_publisher()
        fake_context = FakeContext()
        fake_playwright = FakePlaywright(FakeChromium(fake_context))
        publisher._context = fake_context
        publisher._playwright = fake_playwright

        publisher.close()
        publisher.close()

        self.assertEqual(fake_context.close_calls, 1)
        self.assertEqual(fake_playwright.stop_calls, 1)
        self.assertIsNone(publisher._context)
        self.assertIsNone(publisher._playwright)


if __name__ == "__main__":
    unittest.main()
