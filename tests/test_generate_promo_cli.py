import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import generate_promo


class GeneratePromoCliTest(unittest.TestCase):
    def test_main_reports_partial_failure_when_draft_saved_but_auto_publish_fails(self):
        fake_config = SimpleNamespace(
            PUBLISH_CONFIG={
                "article_template": "wechat_default",
                "enable_schedule": False,
            }
        )
        fake_notifier = Mock()
        fake_generator = Mock()
        fake_generator.generate_promo.return_value = {
            "title": "测试标题",
            "digest": "测试摘要",
            "content": "测试正文",
            "tags": "#测试",
        }
        fake_publisher = Mock()
        fake_publisher.format_for_wechat.return_value = {"content": "<p>测试正文</p>"}
        fake_publisher.publish_article.return_value = {
            "media_id": "draft-media-id",
            "auto_publish_succeeded": False,
            "publish_error": "发布失败: {'errcode': 48001, 'errmsg': 'api unauthorized'}",
            "publish_result": {
                "errcode": 48001,
                "errmsg": "api unauthorized",
                "hint": "自动发布需要认证服务号权限,请手动发布草稿",
            },
        }

        with patch("generate_promo.Config", return_value=fake_config), \
             patch("generate_promo.BarkNotifier", return_value=fake_notifier), \
             patch("generate_promo.PromoGenerator", return_value=fake_generator), \
             patch("generate_promo.WeChatPublisher", return_value=fake_publisher), \
             patch("generate_promo.generate_default_cover", return_value="temp/test-cover.jpg"), \
             patch("generate_promo.os.path.exists", return_value=False), \
             patch("generate_promo.logger") as logger, \
             patch("sys.argv", ["generate_promo.py", "测试主题", "-p"]):
            generate_promo.main()

        logger.error.assert_any_call(
            "草稿保存成功，但自动发布失败: 发布失败: {'errcode': 48001, 'errmsg': 'api unauthorized'}"
        )
        fake_notifier.send.assert_called_with(
            title="公众号草稿保存成功但自动发布失败",
            content="标题: 测试标题\n草稿Media ID: draft-media-id\n错误: 发布失败: {'errcode': 48001, 'errmsg': 'api unauthorized'}",
        )


if __name__ == "__main__":
    unittest.main()
