import unittest
from types import SimpleNamespace
from unittest.mock import patch
import requests

from utils.bark_notifier import BarkNotifier


class BarkNotifierTest(unittest.TestCase):
    @patch("utils.bark_notifier.requests.get")
    @patch("utils.bark_notifier.Config")
    def test_send_image_uses_bark_image_endpoint(self, mock_config, mock_get):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_get.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()

        result = notifier.send_image(
            title="微信扫码登录",
            image_url="https://example.com/qr.png",
            content="请扫码登录公众号后台",
            level="critical",
        )

        self.assertTrue(result)
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_url, "https://api.day.app/test-key/微信扫码登录")
        self.assertEqual(called_params["image"], "https://example.com/qr.png")
        self.assertEqual(called_params["body"], "请扫码登录公众号后台")
        self.assertEqual(called_params["level"], "critical")

    @patch("utils.bark_notifier.requests.get")
    @patch("utils.bark_notifier.Config")
    def test_send_image_omits_optional_params_when_not_provided(self, mock_config, mock_get):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_get.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()

        result = notifier.send_image(
            title="微信扫码登录",
            image_url="https://example.com/qr.png",
        )

        self.assertTrue(result)
        mock_get.assert_called_once()
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["image"], "https://example.com/qr.png")
        self.assertNotIn("body", called_params)
        self.assertNotIn("level", called_params)

    @patch("utils.bark_notifier.requests.post")
    @patch("utils.bark_notifier.requests.get")
    @patch("utils.bark_notifier.Config")
    def test_send_image_falls_back_to_standard_notification_when_image_request_fails(
        self,
        mock_config,
        mock_get,
        mock_post,
    ):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_get.side_effect = requests.exceptions.SSLError("eof")
        mock_post.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()

        result = notifier.send_image(
            title="微信扫码登录",
            image_url="https://example.com/qr.png",
            content="请扫码登录公众号后台",
        )

        self.assertTrue(result)
        self.assertEqual(mock_get.call_count, 3)
        mock_post.assert_called_once()
        called_json = mock_post.call_args.kwargs["json"]
        self.assertEqual(called_json["title"], "微信扫码登录")
        self.assertEqual(called_json["body"], "请扫码登录公众号后台")
        self.assertEqual(called_json["icon"], "https://example.com/qr.png")

    @patch("utils.bark_notifier.requests.post")
    @patch("utils.bark_notifier.Config")
    def test_send_truncates_oversized_body(self, mock_config, mock_post):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_post.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()
        oversized_body = "x" * 5000

        result = notifier.send(title="title", content=oversized_body)

        self.assertTrue(result)
        called_json = mock_post.call_args.kwargs["json"]
        self.assertLessEqual(len(called_json["body"]), 1000)
        self.assertTrue(called_json["body"].endswith("..."))

    @patch("utils.bark_notifier.requests.post")
    @patch("utils.bark_notifier.Config")
    def test_send_includes_optional_url_icon_and_level(self, mock_config, mock_post):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_post.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()

        result = notifier.send(
            title="title",
            content="content",
            group="group",
            url="https://example.com/qr",
            icon="https://example.com/icon.png",
            level="critical",
        )

        self.assertTrue(result)
        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        called_json = mock_post.call_args.kwargs["json"]
        self.assertEqual(called_url, "https://api.day.app/test-key/")
        self.assertEqual(called_json["title"], "title")
        self.assertEqual(called_json["body"], "content")
        self.assertEqual(called_json["group"], "group")
        self.assertEqual(called_json["url"], "https://example.com/qr")
        self.assertEqual(called_json["icon"], "https://example.com/icon.png")
        self.assertEqual(called_json["level"], "critical")

    @patch("utils.bark_notifier.requests.post")
    @patch("utils.bark_notifier.Config")
    def test_send_keeps_existing_defaults_when_optional_args_omitted(self, mock_config, mock_post):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_post.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()

        result = notifier.send(title="title", content="content")

        self.assertTrue(result)
        mock_post.assert_called_once()
        called_json = mock_post.call_args.kwargs["json"]
        self.assertEqual(called_json["title"], "title")
        self.assertEqual(called_json["body"], "content")
        self.assertEqual(called_json["group"], "AI助手")
        self.assertEqual(
            called_json["icon"],
            "https://cdn-icons-png.flaticon.com/512/2583/2583259.png",
        )
        self.assertNotIn("url", called_json)
        self.assertNotIn("level", called_json)

    @patch("utils.bark_notifier.requests.post")
    @patch("utils.bark_notifier.Config")
    def test_send_passes_through_empty_icon_when_explicitly_provided(self, mock_config, mock_post):
        mock_config.return_value = SimpleNamespace(BARK_KEY="test-key")
        mock_post.return_value = SimpleNamespace(status_code=200, text="ok")
        notifier = BarkNotifier()

        result = notifier.send(title="title", content="content", icon="")

        self.assertTrue(result)
        mock_post.assert_called_once()
        called_json = mock_post.call_args.kwargs["json"]
        self.assertIn("icon", called_json)
        self.assertEqual(called_json["icon"], "")


if __name__ == "__main__":
    unittest.main()
