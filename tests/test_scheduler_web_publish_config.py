import pathlib
import unittest
from unittest.mock import patch

from config import config as config_module
from config.config import Config


EXAMPLE_CONFIG_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "config" / "config.py.example"
)


def load_example_config():
    namespace = {}
    with EXAMPLE_CONFIG_PATH.open("r", encoding="utf-8") as example_file:
        exec(example_file.read(), namespace)
    return namespace


class SchedulerWebPublishConfigTest(unittest.TestCase):
    def test_config_exposes_web_publish_settings(self):
        example_ns = load_example_config()
        expected_publish_keys = [
            "enable_web_publish",
            "publish_time",
            "login_check_hours_before",
            "max_publish_retries",
        ]

        with patch.object(Config, "_create_directories", return_value=None):
            config = Config()

        self.assertEqual(config.IMGBB_API_KEY, config_module.IMGBB_API_KEY)
        self.assertEqual(config.IMGBB_EXPIRATION, config_module.IMGBB_EXPIRATION)
        self.assertEqual(config.WEB_PUBLISH_CONFIG, config_module.WEB_PUBLISH_CONFIG)
        for key in expected_publish_keys:
            self.assertIn(key, config.PUBLISH_CONFIG)
            self.assertIn(key, config_module.PUBLISH_CONFIG)
            self.assertEqual(config.PUBLISH_CONFIG[key], config_module.PUBLISH_CONFIG[key])

        self.assertEqual(
            config.PUBLISH_CONFIG["publish_time"],
            config_module.PUBLISH_CONFIG["publish_time"],
        )

        example_publish_config = example_ns["PUBLISH_CONFIG"]
        for key in expected_publish_keys:
            self.assertIn(key, example_publish_config)

        self.assertEqual(example_ns["IMGBB_EXPIRATION"], 86400)
        self.assertEqual(example_publish_config["publish_time"], "20:00")
        self.assertTrue(example_publish_config["enable_web_publish"])
        self.assertEqual(example_publish_config["login_check_hours_before"], 2)
        self.assertEqual(example_publish_config["max_publish_retries"], 3)

        example_web_publish_config = example_ns["WEB_PUBLISH_CONFIG"]
        self.assertEqual(example_web_publish_config["browser_profile_dir"], "/data/wechat-profile")
        self.assertEqual(example_web_publish_config["novnc_port"], 6080)
        self.assertFalse(example_web_publish_config["headless"])

if __name__ == "__main__":
    unittest.main()
