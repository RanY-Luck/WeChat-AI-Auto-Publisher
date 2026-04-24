import unittest

from utils.wechat_web_publisher import WeChatWebPublisher


class FakeContext:
    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


class FakeRuntime:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class WeChatWebPublisherCloseTests(unittest.TestCase):
    def test_close_terminates_profile_processes_when_runtime_leaves_browser_running(self):
        publisher = WeChatWebPublisher(profile_dir="/tmp/wechat-profile")
        context = FakeContext()
        runtime = FakeRuntime()
        terminate_calls = []

        publisher._context = context
        publisher._playwright = runtime
        publisher._has_active_profile_process = lambda: True
        publisher._terminate_profile_processes = lambda: terminate_calls.append(True)

        publisher.close()

        self.assertEqual(context.close_calls, 1)
        self.assertEqual(runtime.stop_calls, 1)
        self.assertEqual(terminate_calls, [True])

    def test_close_skips_profile_cleanup_when_no_browser_process_remains(self):
        publisher = WeChatWebPublisher(profile_dir="/tmp/wechat-profile")
        context = FakeContext()
        runtime = FakeRuntime()
        terminate_calls = []

        publisher._context = context
        publisher._playwright = runtime
        publisher._has_active_profile_process = lambda: False
        publisher._terminate_profile_processes = lambda: terminate_calls.append(True)

        publisher.close()

        self.assertEqual(context.close_calls, 1)
        self.assertEqual(runtime.stop_calls, 1)
        self.assertEqual(terminate_calls, [])


if __name__ == "__main__":
    unittest.main()
