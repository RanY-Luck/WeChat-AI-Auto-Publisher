import unittest
from types import SimpleNamespace
from unittest.mock import patch

import scheduler_app


class FakePage:
    def __init__(self):
        self.goto_calls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append(
            {
                "url": url,
                "wait_until": wait_until,
                "timeout": timeout,
            }
        )


class FakeContext:
    def __init__(self, page):
        self.pages = [page]


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, title, content, group="AI助手", url=None, icon=None, level=None):
        self.calls.append(
            {
                "title": title,
                "content": content,
                "group": group,
                "url": url,
                "icon": icon,
                "level": level,
            }
        )
        return True

    def send_image(self, title, image_url, content=None, level=None):
        self.calls.append(
            {
                "method": "send_image",
                "title": title,
                "content": content,
                "image_url": image_url,
                "level": level,
            }
        )
        return True


class FakeUploader:
    def __init__(self, result_url):
        self.result_url = result_url
        self.calls = []

    def upload(self, path, expiration=None):
        self.calls.append({"path": path, "expiration": expiration})
        return self.result_url


class FakeFailingUploader:
    def __init__(self):
        self.calls = []

    def upload(self, path, expiration=None):
        self.calls.append({"path": path, "expiration": expiration})
        raise RuntimeError("upload failed")


class FakeWebPublisher:
    def __init__(self, page, logged_in, publish_outcomes=None, qr_screenshot_error=None, launch_exception=None):
        self.page = page
        self.logged_in = logged_in
        self.publish_outcomes = list(publish_outcomes or [])
        self.qr_screenshot_error = qr_screenshot_error
        self.launch_exception = launch_exception
        self.publish_attempts = 0
        self.saved_screenshots = []
        self.saved_qr_screenshots = []
        self.closed_count = 0
        self.base_url = "https://mp.weixin.qq.com"
        self.timeout_ms = 15000

    def launch_persistent_context(self, playwright=None):
        if self.launch_exception is not None:
            raise self.launch_exception
        return FakeContext(self.page)

    def close(self):
        self.closed_count += 1

    def is_logged_in(self, page):
        return self.logged_in

    def publish_latest_draft(self, page):
        self.publish_attempts += 1
        if self.publish_outcomes:
            outcome = self.publish_outcomes.pop(0)
            if outcome is not None:
                raise outcome

    def save_failure_screenshot(self, page, prefix="failure", timestamp=None):
        path = f"temp/{prefix}-20260407-120000.png"
        self.saved_screenshots.append(path)
        return path

    def save_login_qr_screenshot(self, page, prefix="login-qr", timestamp=None):
        if self.qr_screenshot_error is not None:
            raise self.qr_screenshot_error
        path = f"temp/{prefix}-20260407-120000.png"
        self.saved_qr_screenshots.append(path)
        return path


class FakeScheduleAt:
    def __init__(self, scheduler, time_text):
        self.scheduler = scheduler
        self.time_text = time_text

    def do(self, callback):
        self.scheduler.entries.append({"time": self.time_text, "callback": callback})
        return callback


class FakeScheduleEvery:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.day = self

    def at(self, time_text):
        return FakeScheduleAt(self.scheduler, time_text)


class FakeScheduler:
    def __init__(self):
        self.entries = []

    def every(self):
        return FakeScheduleEvery(self)


class SchedulerWebPublishTest(unittest.TestCase):
    def test_compute_precheck_time_subtracts_hours(self):
        self.assertEqual(scheduler_app.compute_precheck_time("20:00", 2), "18:00")

    def test_compute_precheck_time_wraps_previous_day_clock_time(self):
        # Daily scheduler contract: cross-midnight precheck returns previous-day wall clock time.
        self.assertEqual(scheduler_app.compute_precheck_time("01:00", 2), "23:00")

    def test_login_precheck_prefers_qr_screenshot_for_bark_upload_when_logged_out(self):
        config = SimpleNamespace(
            IMGBB_API_KEY="imgbb-key",
            IMGBB_EXPIRATION=600,
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": 3},
        )
        notifier = FakeNotifier()
        uploader = FakeUploader("https://imgbb.example/qr.png")
        page = FakePage()
        web_publisher = FakeWebPublisher(page=page, logged_in=False)

        result = scheduler_app.login_precheck_job(
            config=config,
            notifier=notifier,
            uploader=uploader,
            web_publisher=web_publisher,
        )

        self.assertFalse(result)
        self.assertEqual(len(page.goto_calls), 1)
        self.assertEqual(page.goto_calls[0]["url"], "https://mp.weixin.qq.com")
        self.assertEqual(uploader.calls[0]["path"], "temp/login-qr-20260407-120000.png")
        self.assertEqual(notifier.calls[0]["method"], "send_image")
        self.assertEqual(notifier.calls[0]["title"], "微信扫码登录")
        self.assertEqual(notifier.calls[0]["image_url"], "https://imgbb.example/qr.png")
        self.assertIsNone(notifier.calls[0]["content"])
        self.assertEqual(web_publisher.saved_qr_screenshots, ["temp/login-qr-20260407-120000.png"])
        self.assertEqual(web_publisher.saved_screenshots, [])
        self.assertEqual(web_publisher.closed_count, 1)

    def test_login_precheck_falls_back_to_full_page_screenshot_when_qr_capture_fails(self):
        config = SimpleNamespace(
            IMGBB_API_KEY="imgbb-key",
            IMGBB_EXPIRATION=600,
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": 3},
        )
        notifier = FakeNotifier()
        uploader = FakeUploader("https://imgbb.example/login-page.png")
        page = FakePage()
        web_publisher = FakeWebPublisher(
            page=page,
            logged_in=False,
            qr_screenshot_error=RuntimeError("qr not found"),
        )

        result = scheduler_app.login_precheck_job(
            config=config,
            notifier=notifier,
            uploader=uploader,
            web_publisher=web_publisher,
        )

        self.assertFalse(result)
        self.assertEqual(notifier.calls[0]["method"], "send_image")
        self.assertEqual(notifier.calls[0]["title"], "微信扫码登录")
        self.assertEqual(uploader.calls[0]["path"], "temp/login-precheck-20260407-120000.png")
        self.assertEqual(notifier.calls[0]["image_url"], "https://imgbb.example/login-page.png")
        self.assertIsNone(notifier.calls[0]["content"])
        self.assertEqual(web_publisher.saved_qr_screenshots, [])
        self.assertEqual(web_publisher.saved_screenshots, ["temp/login-precheck-20260407-120000.png"])

    def test_login_precheck_falls_back_to_novnc_hint_when_uploader_unavailable_or_upload_fails(self):
        cases = [
            ("missing-uploader", None, lambda _config: None),
            ("upload-failed", FakeFailingUploader(), None),
        ]
        for case_name, uploader, uploader_factory in cases:
            with self.subTest(case=case_name):
                config = SimpleNamespace(
                    IMGBB_API_KEY="imgbb-key",
                    IMGBB_EXPIRATION=600,
                    WEB_PUBLISH_CONFIG={"novnc_port": 6080},
                    PUBLISH_CONFIG={"max_publish_retries": 3},
                )
                notifier = FakeNotifier()
                page = FakePage()
                web_publisher = FakeWebPublisher(page=page, logged_in=False)

                result = scheduler_app.login_precheck_job(
                    config=config,
                    notifier=notifier,
                    uploader=uploader,
                    uploader_factory=uploader_factory,
                    web_publisher=web_publisher,
                )

                self.assertFalse(result)
                self.assertEqual(len(notifier.calls), 1)
                self.assertIsNone(notifier.calls[0]["url"])
                self.assertIn("noVNC", notifier.calls[0]["content"])

    def test_login_precheck_prefixes_titles_when_instance_prefix_configured(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": 3},
        )
        notifier = FakeNotifier()
        page = FakePage()
        web_publisher = FakeWebPublisher(page=page, logged_in=False)

        with patch.dict("os.environ", {"BARK_TITLE_PREFIX": "[公众号B] "}, clear=False):
            result = scheduler_app.login_precheck_job(
                config=config,
                notifier=notifier,
                uploader=None,
                uploader_factory=lambda _config: None,
                web_publisher=web_publisher,
            )

        self.assertFalse(result)
        self.assertEqual(notifier.calls[0]["title"], "[公众号B] 微信登录预检查提醒")

    def test_send_qr_debug_notification_uses_icon_only_without_click_url(self):
        notifier = FakeNotifier()

        scheduler_app.send_qr_debug_notification(
            notifier=notifier,
            image_url="https://imgbb.example/debug-qr.png",
        )

        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["method"], "send_image")
        self.assertEqual(notifier.calls[0]["title"], "微信扫码登录")
        self.assertIsNone(notifier.calls[0]["content"])
        self.assertEqual(notifier.calls[0]["image_url"], "https://imgbb.example/debug-qr.png")

    def test_send_qr_debug_notification_prefixes_title_when_instance_prefix_configured(self):
        notifier = FakeNotifier()

        with patch.dict("os.environ", {"BARK_TITLE_PREFIX": "[公众号A] "}, clear=False):
            scheduler_app.send_qr_debug_notification(
                notifier=notifier,
                image_url="https://imgbb.example/debug-qr.png",
            )

        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["title"], "[公众号A] 微信扫码登录")

    def test_main_supports_debug_bark_icon_mode(self):
        with patch.object(scheduler_app, "send_qr_debug_notification") as send_debug:
            result = scheduler_app.main(
                argv=[
                    "--debug-bark-icon-url",
                    "https://imgbb.example/debug-qr.png",
                ]
            )

        send_debug.assert_called_once()
        self.assertEqual(
            send_debug.call_args.kwargs["image_url"],
            "https://imgbb.example/debug-qr.png",
        )
        self.assertEqual(result, 0)

    def test_publish_job_skips_when_not_logged_in_and_sends_alert(self):
        config = SimpleNamespace(
            IMGBB_API_KEY="imgbb-key",
            IMGBB_EXPIRATION=600,
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": 3},
        )
        notifier = FakeNotifier()
        uploader = FakeUploader("https://imgbb.example/publish-login-qr.png")
        page = FakePage()
        web_publisher = FakeWebPublisher(page=page, logged_in=False)

        result = scheduler_app.publish_latest_draft_job(
            config=config,
            notifier=notifier,
            uploader=uploader,
            web_publisher=web_publisher,
        )

        self.assertFalse(result)
        self.assertEqual(web_publisher.publish_attempts, 0)
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["method"], "send_image")
        self.assertEqual(notifier.calls[0]["title"], "微信扫码登录")
        self.assertEqual(notifier.calls[0]["image_url"], "https://imgbb.example/publish-login-qr.png")
        self.assertIsNone(notifier.calls[0]["content"])
        self.assertEqual(len(page.goto_calls), 1)
        self.assertEqual(page.goto_calls[0]["url"], "https://mp.weixin.qq.com")
        self.assertEqual(web_publisher.closed_count, 1)

    def test_login_precheck_reports_profile_in_use_without_exception_alert(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": 3},
        )
        notifier = FakeNotifier()
        page = FakePage()
        web_publisher = FakeWebPublisher(
            page=page,
            logged_in=False,
            launch_exception=RuntimeError("Failed to create a ProcessSingleton for your profile directory"),
        )

        result = scheduler_app.login_precheck_job(
            config=config,
            notifier=notifier,
            web_publisher=web_publisher,
        )

        self.assertFalse(result)
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["title"], "微信登录窗口占用中")
        self.assertIn("登录页已打开", notifier.calls[0]["content"])
        self.assertEqual(web_publisher.closed_count, 1)

    def test_publish_job_reports_profile_in_use_without_exception_alert(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": 3},
        )
        notifier = FakeNotifier()
        page = FakePage()
        web_publisher = FakeWebPublisher(
            page=page,
            logged_in=False,
            launch_exception=RuntimeError("ProcessSingleton for your profile directory"),
        )

        result = scheduler_app.publish_latest_draft_job(
            config=config,
            notifier=notifier,
            web_publisher=web_publisher,
        )

        self.assertFalse(result)
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["title"], "微信登录窗口占用中")
        self.assertIn("关闭登录窗口后", notifier.calls[0]["content"])
        self.assertEqual(web_publisher.closed_count, 1)

    def test_run_startup_login_precheck_triggers_immediate_check_when_web_publish_enabled(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"enable_web_publish": True},
        )
        notifier_calls = []
        invocation_log = []

        def notifier_factory():
            notifier = object()
            notifier_calls.append(notifier)
            return notifier

        def fake_login_precheck_job(**kwargs):
            invocation_log.append(kwargs)
            return False

        result = scheduler_app.run_startup_login_precheck(
            config=config,
            notifier_factory=notifier_factory,
            login_precheck_job_callable=fake_login_precheck_job,
            web_publisher_factory="wp-factory",
            uploader_factory="uploader-factory",
        )

        self.assertFalse(result)
        self.assertEqual(len(invocation_log), 1)
        self.assertIs(invocation_log[0]["config"], config)
        self.assertIs(invocation_log[0]["notifier"], notifier_calls[0])
        self.assertEqual(invocation_log[0]["web_publisher_factory"], "wp-factory")
        self.assertEqual(invocation_log[0]["uploader_factory"], "uploader-factory")

    def test_run_startup_login_precheck_skips_when_web_publish_disabled(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"enable_web_publish": False},
        )

        with patch.object(scheduler_app, "login_precheck_job") as login_precheck:
            result = scheduler_app.run_startup_login_precheck(config=config)

        self.assertIsNone(result)
        login_precheck.assert_not_called()

    def test_run_startup_login_precheck_skips_when_auto_open_browser_enabled(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"enable_web_publish": True},
        )

        with patch.dict("os.environ", {"AUTO_OPEN_BROWSER": "true"}, clear=False):
            with patch.object(scheduler_app, "login_precheck_job") as login_precheck:
                result = scheduler_app.run_startup_login_precheck(config=config)

        self.assertIsNone(result)
        login_precheck.assert_not_called()

    def test_publish_job_retries_up_to_three_times_then_reports_final_status(self):
        cases = [
            (
                [RuntimeError("first"), RuntimeError("second"), None],
                True,
                "成功",
            ),
            (
                [RuntimeError("first"), RuntimeError("second"), RuntimeError("third")],
                False,
                "失败",
            ),
        ]

        for outcomes, expected_result, expected_title_fragment in cases:
            with self.subTest(outcomes=[str(item) if item else None for item in outcomes]):
                config = SimpleNamespace(
                    WEB_PUBLISH_CONFIG={"novnc_port": 6080},
                    PUBLISH_CONFIG={"max_publish_retries": 3},
                )
                notifier = FakeNotifier()
                page = FakePage()
                web_publisher = FakeWebPublisher(
                    page=page,
                    logged_in=True,
                    publish_outcomes=outcomes,
                )

                result = scheduler_app.publish_latest_draft_job(
                    config=config,
                    notifier=notifier,
                    web_publisher=web_publisher,
                )

                self.assertEqual(result, expected_result)
                self.assertEqual(web_publisher.publish_attempts, 3)
                self.assertEqual(len(page.goto_calls), 1)
                self.assertEqual(page.goto_calls[0]["url"], "https://mp.weixin.qq.com")
                self.assertEqual(len(notifier.calls), 1)
                self.assertIn(expected_title_fragment, notifier.calls[0]["title"])
                self.assertEqual(web_publisher.closed_count, 1)

    def test_publish_job_uses_default_retry_count_when_config_is_invalid(self):
        config = SimpleNamespace(
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
            PUBLISH_CONFIG={"max_publish_retries": "not-an-int"},
        )
        notifier = FakeNotifier()
        page = FakePage()
        web_publisher = FakeWebPublisher(
            page=page,
            logged_in=True,
            publish_outcomes=[RuntimeError("1"), RuntimeError("2"), None],
        )

        result = scheduler_app.publish_latest_draft_job(
            config=config,
            notifier=notifier,
            web_publisher=web_publisher,
        )

        self.assertTrue(result)
        self.assertEqual(web_publisher.publish_attempts, 3)
        self.assertIn("成功", notifier.calls[0]["title"])

    def test_schedule_jobs_callbacks_capture_config_and_injected_dependencies(self):
        scheduler = FakeScheduler()
        config = SimpleNamespace(
            PUBLISH_CONFIG={
                "target_time": "11:50",
                "enable_web_publish": True,
                "publish_time": "20:00",
                "login_check_hours_before": 2,
                "max_publish_retries": 3,
            },
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
        )
        invocation_log = []
        notifier_calls = []

        def notifier_factory():
            notifier = object()
            notifier_calls.append(notifier)
            return notifier

        def fake_login_precheck_job(**kwargs):
            invocation_log.append(("login", kwargs))
            return True

        def fake_publish_job(**kwargs):
            invocation_log.append(("publish", kwargs))
            return True

        scheduler_app.schedule_jobs(
            config=config,
            scheduler_module=scheduler,
            notifier_factory=notifier_factory,
            web_publisher_factory="wp-factory",
            uploader_factory="uploader-factory",
            login_precheck_job_callable=fake_login_precheck_job,
            publish_latest_draft_job_callable=fake_publish_job,
        )

        self.assertEqual(len(scheduler.entries), 3)
        self.assertEqual(
            [entry["time"] for entry in scheduler.entries],
            ["11:50", "18:00", "20:00"],
        )
        self.assertEqual(notifier_calls, [])

        for entry in scheduler.entries:
            if entry["time"] in ("18:00", "20:00"):
                entry["callback"]()

        self.assertEqual(len(notifier_calls), 2)
        self.assertEqual(len(invocation_log), 2)
        login_kwargs = invocation_log[0][1]
        publish_kwargs = invocation_log[1][1]
        self.assertIs(login_kwargs["config"], config)
        self.assertIs(publish_kwargs["config"], config)
        self.assertIs(login_kwargs["notifier"], notifier_calls[0])
        self.assertIs(publish_kwargs["notifier"], notifier_calls[1])
        self.assertEqual(login_kwargs["web_publisher_factory"], "wp-factory")
        self.assertEqual(login_kwargs["uploader_factory"], "uploader-factory")
        self.assertEqual(publish_kwargs["web_publisher_factory"], "wp-factory")
        self.assertEqual(publish_kwargs["uploader_factory"], "uploader-factory")

    def test_schedule_jobs_with_web_publish_disabled_only_schedules_draft_job(self):
        scheduler = FakeScheduler()
        config = SimpleNamespace(
            PUBLISH_CONFIG={
                "target_time": "11:50",
                "enable_web_publish": False,
                "publish_time": "20:00",
                "login_check_hours_before": 2,
            },
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
        )
        draft_calls = []

        def draft_job():
            draft_calls.append("called")

        schedule_info = scheduler_app.schedule_jobs(
            config=config,
            scheduler_module=scheduler,
            draft_job_callable=draft_job,
        )

        self.assertEqual(len(scheduler.entries), 1)
        self.assertEqual(scheduler.entries[0]["time"], "11:50")
        self.assertFalse(schedule_info["web_publish_enabled"])
        self.assertIsNone(schedule_info["publish_time"])
        self.assertIsNone(schedule_info["precheck_time"])

        scheduler.entries[0]["callback"]()
        self.assertEqual(draft_calls, ["called"])

    def test_schedule_jobs_uses_default_hours_when_login_check_value_is_invalid(self):
        scheduler = FakeScheduler()
        config = SimpleNamespace(
            PUBLISH_CONFIG={
                "target_time": "11:50",
                "enable_web_publish": True,
                "publish_time": "20:00",
                "login_check_hours_before": "bad-hours",
            },
            WEB_PUBLISH_CONFIG={"novnc_port": 6080},
        )

        schedule_info = scheduler_app.schedule_jobs(
            config=config,
            scheduler_module=scheduler,
        )

        self.assertEqual(schedule_info["precheck_time"], "18:00")
        self.assertEqual(
            [entry["time"] for entry in scheduler.entries],
            ["11:50", "18:00", "20:00"],
        )


if __name__ == "__main__":
    unittest.main()
