from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _install_fake_config_module():
    config_package = types.ModuleType("config")
    config_module = types.ModuleType("config.config")

    class FakeConfig:
        def __init__(self):
            self.PUBLISH_CONFIG = {}
            self.WEB_PUBLISH_CONFIG = {}
            self.IMGBB_API_KEY = ""
            self.IMGBB_EXPIRATION = 600

    config_module.DASHSCOPE_API_KEY = ""
    config_module.DASHSCOPE_MODEL = ""
    config_module.WECHAT_CONFIG = {}
    config_module.BARK_KEY = ""
    config_module.IMGBB_API_KEY = ""
    config_module.IMGBB_EXPIRATION = 600
    config_module.LOGGING_CONFIG = {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": str(ROOT / "logs" / "test.log"),
    }
    config_module.Config = FakeConfig

    sys.modules["config"] = config_package
    sys.modules["config.config"] = config_module


_install_fake_config_module()

import scheduler_app


class FakeRandom:
    def __init__(self, run_count, minutes):
        self.run_count = run_count
        self.minutes = minutes
        self.randint_calls = []

    def randint(self, start, end):
        self.randint_calls.append((start, end))
        return self.run_count

    def sample(self, population, count):
        return list(self.minutes)


class FakeNotifier:
    def __init__(self):
        self.send_calls = []
        self.send_image_calls = []

    def send(self, **kwargs):
        self.send_calls.append(kwargs)
        return True

    def send_image(self, **kwargs):
        self.send_image_calls.append(kwargs)
        return True


class FakePage:
    def __init__(self):
        self.goto_calls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append(
            {"url": url, "wait_until": wait_until, "timeout": timeout}
        )


class FakeContext:
    def __init__(self, page):
        self.pages = [page]


class FakeWebPublisher:
    def __init__(self, logged_in_sequence):
        self.logged_in_sequence = list(logged_in_sequence)
        self.page = FakePage()
        self.close_calls = 0
        self.base_url = "https://mp.weixin.qq.com"
        self.timeout_ms = 15000

    def launch_persistent_context(self):
        return FakeContext(self.page)

    def is_logged_in(self, page):
        if self.logged_in_sequence:
            return self.logged_in_sequence.pop(0)
        return False

    def save_login_qr_screenshot(self, page, prefix="login-qr"):
        return str(ROOT / "temp" / f"{prefix}.png")

    def save_failure_screenshot(self, page, prefix="login-precheck"):
        return str(ROOT / "temp" / f"{prefix}.png")

    def close(self):
        self.close_calls += 1


class FakeScheduledJob:
    def __init__(self, scheduler, unit):
        self.scheduler = scheduler
        self.unit = unit
        self.time_text = None
        self.func = None
        self.args = ()
        self.kwargs = {}

    @property
    def day(self):
        return self

    @property
    def minutes(self):
        return self

    def at(self, time_text):
        self.time_text = time_text
        return self

    def do(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        if self.unit == "day":
            self.scheduler.day_jobs.append(self)
        else:
            self.scheduler.minute_jobs.append(self)
        return self

    def cancel(self):
        self.scheduler.cancelled_jobs.append(self)


class FakeScheduler:
    def __init__(self):
        self.day_jobs = []
        self.minute_jobs = []
        self.cancelled_jobs = []

    def every(self, interval=None):
        unit = "day" if interval is None else "minutes"
        return FakeScheduledJob(self, unit)


class RandomDailyScheduleTests(unittest.TestCase):
    def test_generate_random_daily_times_returns_sorted_unique_hhmm_values(self):
        fake_random = FakeRandom(run_count=3, minutes=[61, 5, 1439])
        times = scheduler_app.generate_random_daily_times(
            daily_random_runs_min=3,
            daily_random_runs_max=5,
            random_module=fake_random,
        )

        self.assertEqual(times, ["00:05", "01:01", "23:59"])
        self.assertEqual(fake_random.randint_calls, [(3, 5)])

    def test_generate_random_daily_times_supports_fixed_count_when_min_equals_max(self):
        fake_random = FakeRandom(run_count=5, minutes=[1, 2, 3, 4, 5])

        times = scheduler_app.generate_random_daily_times(
            daily_random_runs_min=5,
            daily_random_runs_max=5,
            random_module=fake_random,
        )

        self.assertEqual(len(times), 5)
        self.assertEqual(fake_random.randint_calls, [(5, 5)])

    def test_filter_future_times_for_today_skips_passed_slots(self):
        result = scheduler_app.filter_future_times_for_today(
            plan_date=date(2026, 4, 17),
            times=["09:00", "10:30", "10:31", "23:59"],
            now=datetime(2026, 4, 17, 10, 30),
        )

        self.assertEqual(result, ["10:31", "23:59"])

    def test_schedule_jobs_registers_random_daily_runs_when_enabled(self):
        scheduler = FakeScheduler()
        config = SimpleNamespace(
            PUBLISH_CONFIG={
                "random_daily_schedule_enabled": True,
                "daily_random_runs_min": 3,
                "daily_random_runs_max": 3,
                "enable_web_publish": False,
            }
        )

        schedule_info = scheduler_app.schedule_jobs(
            config=config,
            scheduler_module=scheduler,
            draft_job_callable=lambda: None,
            now_provider=lambda: datetime(2026, 4, 17, 0, 0),
            random_module=FakeRandom(run_count=2, minutes=[61, 5]),
        )

        self.assertEqual(schedule_info["schedule_mode"], "random_daily")
        self.assertEqual(schedule_info["target_times"], ["00:05", "01:01"])
        self.assertEqual([job.time_text for job in scheduler.day_jobs], ["00:05", "01:01"])
        self.assertEqual(len(scheduler.minute_jobs), 2)

    def test_refresh_random_daily_plan_replaces_plan_after_date_change(self):
        scheduler = FakeScheduler()
        state = {"plan_date": date(2026, 4, 17), "registered_job_refs": []}

        updated_state = scheduler_app.refresh_random_daily_plan(
            state=state,
            scheduler_module=scheduler,
            draft_job_callable=lambda: None,
            daily_random_runs_max=1,
            daily_random_runs_min=1,
            now_provider=lambda: datetime(2026, 4, 18, 0, 1),
            random_module=FakeRandom(run_count=1, minutes=[15]),
        )

        self.assertEqual(updated_state["plan_date"], date(2026, 4, 18))
        self.assertEqual(updated_state["times"], ["00:15"])

    def test_ensure_logged_in_or_start_wait_sends_single_notification(self):
        state = {}
        notifier = FakeNotifier()
        web_publisher = FakeWebPublisher([False, False])

        first_result = scheduler_app.ensure_logged_in_or_start_wait(
            state=state,
            config=SimpleNamespace(WEB_PUBLISH_CONFIG={}),
            notifier=notifier,
            web_publisher_factory=lambda config: web_publisher,
            uploader_factory=lambda config: None,
        )
        second_result = scheduler_app.ensure_logged_in_or_start_wait(
            state=state,
            config=SimpleNamespace(WEB_PUBLISH_CONFIG={}),
            notifier=notifier,
            web_publisher_factory=lambda config: web_publisher,
            uploader_factory=lambda config: None,
        )

        self.assertIsNone(first_result)
        self.assertIsNone(second_result)
        self.assertTrue(state["waiting_for_login"])
        self.assertEqual(len(notifier.send_calls), 1)
        self.assertEqual(web_publisher.close_calls, 0)

    def test_schedule_jobs_skips_new_tasks_while_waiting_for_login_and_resumes_after_login(self):
        scheduler = FakeScheduler()
        notifier = FakeNotifier()
        web_publisher = FakeWebPublisher([False, True])
        draft_calls = []
        publish_calls = []

        def draft_job():
            draft_calls.append("draft")
            return True

        def publish_job(**kwargs):
            publish_calls.append("publish")
            return True

        config = SimpleNamespace(
            PUBLISH_CONFIG={
                "random_daily_schedule_enabled": True,
                "daily_random_runs_min": 1,
                "daily_random_runs_max": 1,
                "enable_web_publish": True,
            },
            WEB_PUBLISH_CONFIG={},
            IMGBB_API_KEY="",
            IMGBB_EXPIRATION=600,
        )

        scheduler_app.schedule_jobs(
            config=config,
            scheduler_module=scheduler,
            draft_job_callable=draft_job,
            publish_latest_draft_job_callable=publish_job,
            notifier_factory=lambda: notifier,
            web_publisher_factory=lambda config: web_publisher,
            uploader_factory=lambda config: None,
            now_provider=lambda: datetime(2026, 4, 17, 0, 0),
            random_module=FakeRandom(run_count=1, minutes=[61]),
        )

        first_run_result = scheduler.day_jobs[0].func()
        second_run_result = scheduler.day_jobs[0].func()
        for minute_job in scheduler.minute_jobs:
            minute_job.func(*minute_job.args, **minute_job.kwargs)

        self.assertFalse(first_run_result)
        self.assertFalse(second_run_result)
        self.assertEqual(draft_calls, ["draft"])
        self.assertEqual(publish_calls, ["publish"])
        self.assertEqual(len(notifier.send_calls), 1)
        self.assertEqual(web_publisher.close_calls, 1)

    def test_config_example_documents_random_daily_schedule_fields(self):
        config_example_text = (ROOT / "config" / "config.py.example").read_text(encoding="utf-8")

        self.assertIn('"random_daily_schedule_enabled"', config_example_text)
        self.assertIn('"daily_random_runs_min"', config_example_text)
        self.assertIn('"daily_random_runs_max"', config_example_text)


if __name__ == "__main__":
    unittest.main()
