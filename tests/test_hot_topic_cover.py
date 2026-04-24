from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest import mock
from PIL import Image


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


class HotTopicCoverTests(unittest.TestCase):
    def test_build_discussion_title_uses_fixed_prefix(self):
        title = scheduler_app.build_discussion_title("男女那些事")

        self.assertEqual(title, "发现中国有一个奇怪的现象：男女那些事")

    def test_build_discussion_title_trims_trailing_punctuation(self):
        title = scheduler_app.build_discussion_title("家庭那些事!!! ")

        self.assertEqual(title, "发现中国有一个奇怪的现象：家庭那些事")

    def test_list_cover_pool_images_returns_supported_images_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_a = Path(temp_dir) / "a.jpg"
            image_b = Path(temp_dir) / "b.png"
            ignored = Path(temp_dir) / "note.txt"
            image_a.write_bytes(b"jpg")
            image_b.write_bytes(b"png")
            ignored.write_text("ignore", encoding="utf-8")

            images = scheduler_app.list_cover_pool_images(temp_dir)

        self.assertEqual([Path(path).name for path in images], ["a.jpg", "b.png"])

    def test_choose_cover_pool_image_uses_random_choice(self):
        images = ["a.jpg", "b.jpg"]

        class FakeRandom:
            def choice(self, values):
                self.values = values
                return "b.jpg"

        fake_random = FakeRandom()

        chosen = scheduler_app.choose_cover_pool_image(images, random_module=fake_random)

        self.assertEqual(chosen, "b.jpg")
        self.assertEqual(fake_random.values, images)

    def test_render_cover_from_pool_asset_creates_new_output_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.jpg"
            Image.new("RGB", (1200, 800), color=(40, 50, 60)).save(source)

            output = scheduler_app.render_cover_from_pool_asset(
                base_image_path=str(source),
                title="发现中国有一个奇怪的现象：男女那些事",
            )

            self.assertNotEqual(output, str(source))
            self.assertTrue(Path(output).exists())
            with Image.open(output) as generated_image:
                self.assertEqual(generated_image.size, (900, 383))

            Path(output).unlink()

    def test_resolve_cover_path_from_pool_returns_none_when_pool_is_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cover_path = scheduler_app.resolve_cover_path_from_pool(
                cover_pool_dir=temp_dir,
                title="发现中国有一个奇怪的现象：家庭那些事",
            )

        self.assertIsNone(cover_path)

    def test_extract_hot_topic_cover_url_ignores_weibo_badge_icon(self):
        cover_url = scheduler_app.extract_hot_topic_cover_url(
            {
                "icon": "https://simg.s.weibo.com/moter/flags/1_0.png",
                "icon_width": 24,
                "icon_height": 24,
            }
        )

        self.assertIsNone(cover_url)

    def test_extract_hot_topic_cover_url_keeps_large_candidate_url(self):
        cover_url = scheduler_app.extract_hot_topic_cover_url(
            {
                "cover": "https://wx1.sinaimg.cn/large/example.jpg",
            }
        )

        self.assertEqual(cover_url, "https://wx1.sinaimg.cn/large/example.jpg")

    def test_get_hot_topic_uses_weibo_socialevent_page_only(self):
        requested_urls = []

        class FakeResponse:
            def __init__(self, text="", payload=None):
                self.text = text
                self._payload = payload or {}

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        def fake_get(url, headers=None, timeout=None):
            requested_urls.append(url)
            if url == "https://s.weibo.com/top/summary?cate=socialevent":
                return FakeResponse(
                    text="""
                    <table>
                        <tr><td class="td-02"><a href="/weibo?q=%23社会事件A%23">社会事件A</a></td></tr>
                        <tr><td class="td-02"><a href="/weibo?q=%23社会事件B%23">社会事件B</a></td></tr>
                    </table>
                    """
                )
            return FakeResponse(
                payload={"data": {"realtime": [{"word": "接口热点"}]}}
            )

        fake_config = types.SimpleNamespace(PUBLISH_CONFIG={"hot_topic_candidate_limit": 2})

        with mock.patch.object(scheduler_app, "Config", return_value=fake_config), mock.patch.object(
            scheduler_app.requests,
            "get",
            side_effect=fake_get,
        ), mock.patch.object(
            scheduler_app.random,
            "choice",
            side_effect=lambda values: values[0],
        ):
            topic_info = scheduler_app.get_hot_topic_from_weibo_hot_search()

        self.assertEqual(
            requested_urls,
            ["https://s.weibo.com/top/summary?cate=socialevent"],
        )
        self.assertEqual(topic_info["title"], "社会事件A")
        self.assertIsNone(topic_info["cover_image_url"])

    def test_get_hot_topic_uses_browser_fallback_when_socialevent_hits_visitor_page(self):
        requested_urls = []

        class FakeResponse:
            def __init__(self, text="", url=""):
                self.text = text
                self.url = url

            def raise_for_status(self):
                return None

        def fake_get(url, headers=None, timeout=None):
            requested_urls.append(url)
            return FakeResponse(
                text="<html><title>Sina Visitor System</title></html>",
                url="https://passport.weibo.com/visitor/visitor?entry=miniblog",
            )

        fake_config = types.SimpleNamespace(PUBLISH_CONFIG={"hot_topic_candidate_limit": 2})

        with mock.patch.object(scheduler_app, "Config", return_value=fake_config), mock.patch.object(
            scheduler_app.requests,
            "get",
            side_effect=fake_get,
        ), mock.patch.object(
            scheduler_app,
            "fetch_weibo_socialevent_html_via_browser",
            return_value="""
            <table>
                <tr><td class="td-02"><a href="/weibo?q=%23社会事件浏览器A%23">社会事件浏览器A</a></td></tr>
                <tr><td class="td-02"><a href="/weibo?q=%23社会事件浏览器B%23">社会事件浏览器B</a></td></tr>
            </table>
            """,
        ) as browser_fetch_mock, mock.patch.object(
            scheduler_app.random,
            "choice",
            side_effect=lambda values: values[0],
        ):
            topic_info = scheduler_app.get_hot_topic_from_weibo_hot_search()

        self.assertEqual(
            requested_urls,
            ["https://s.weibo.com/top/summary?cate=socialevent"],
        )
        browser_fetch_mock.assert_called_once()
        self.assertEqual(topic_info["title"], "社会事件浏览器A")
        self.assertIsNone(topic_info["cover_image_url"])

    def test_resolve_cover_path_prefers_hot_topic_cover_download(self):
        topic_info = {
            "title": "热点话题",
            "cover_image_url": "https://wx1.sinaimg.cn/large/example.jpg",
        }

        with mock.patch.object(
            scheduler_app,
            "download_cover_image",
            return_value="temp/topic-cover.jpg",
        ) as download_mock, mock.patch.object(
            scheduler_app,
            "generate_default_cover",
            return_value="temp/default-cover.jpg",
        ) as default_mock:
            cover_path = scheduler_app.resolve_cover_path(
                topic_info=topic_info,
                title_hint="文章标题",
            )

        self.assertEqual(cover_path, "temp/topic-cover.jpg")
        download_mock.assert_called_once_with(
            "https://wx1.sinaimg.cn/large/example.jpg",
            title_hint="热点话题",
        )
        default_mock.assert_not_called()

    def test_resolve_cover_path_falls_back_to_default_cover(self):
        topic_info = {
            "title": "热点话题",
            "cover_image_url": "https://wx1.sinaimg.cn/large/example.jpg",
        }

        with mock.patch.object(
            scheduler_app,
            "download_cover_image",
            return_value=None,
        ) as download_mock, mock.patch.object(
            scheduler_app,
            "generate_default_cover",
            return_value="temp/default-cover.jpg",
        ) as default_mock:
            cover_path = scheduler_app.resolve_cover_path(
                topic_info=topic_info,
                title_hint="文章标题",
            )

        self.assertEqual(cover_path, "temp/default-cover.jpg")
        download_mock.assert_called_once_with(
            "https://wx1.sinaimg.cn/large/example.jpg",
            title_hint="热点话题",
        )
        default_mock.assert_called_once_with("文章标题")

    def test_resolve_cover_path_normalizes_protocol_relative_cover_url(self):
        topic_info = {
            "title": "热点话题",
            "cover_image_url": "//wx1.sinaimg.cn/large/example.jpg",
        }

        with mock.patch.object(
            scheduler_app,
            "download_cover_image",
            return_value="temp/topic-cover.jpg",
        ) as download_mock:
            cover_path = scheduler_app.resolve_cover_path(
                topic_info=topic_info,
                title_hint="文章标题",
            )

        self.assertEqual(cover_path, "temp/topic-cover.jpg")
        download_mock.assert_called_once_with(
            "https://wx1.sinaimg.cn/large/example.jpg",
            title_hint="热点话题",
        )

    def test_job_removes_cover_file_when_publish_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            cover_path = temp_file.name

        fake_config = types.SimpleNamespace(PUBLISH_CONFIG={})
        fake_generator = mock.Mock()
        fake_generator.generate_promo.return_value = {
            "title": "文章标题",
            "content": "正文内容",
            "digest": "摘要",
        }
        fake_publisher = mock.Mock()
        fake_publisher.format_for_wechat.return_value = "<html>article</html>"
        fake_publisher.publish_article.side_effect = RuntimeError("publish failed")
        fake_notifier = mock.Mock()

        with mock.patch.object(scheduler_app, "Config", return_value=fake_config), mock.patch.object(
            scheduler_app,
            "get_hot_topic_from_weibo_hot_search",
            return_value={"title": "热点话题", "cover_image_url": None},
        ), mock.patch.object(
            scheduler_app,
            "PromoGenerator",
            return_value=fake_generator,
        ), mock.patch.object(
            scheduler_app,
            "WeChatPublisher",
            return_value=fake_publisher,
        ), mock.patch.object(
            scheduler_app,
            "resolve_cover_path",
            return_value=cover_path,
        ), mock.patch.object(
            scheduler_app,
            "BarkNotifier",
            return_value=fake_notifier,
        ):
            result = scheduler_app.job()

        self.assertFalse(result)
        self.assertFalse(Path(cover_path).exists())

    def test_job_uses_discussion_title_and_pool_cover_for_publish(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            cover_path = temp_file.name

        fake_config = types.SimpleNamespace(
            PUBLISH_CONFIG={
                "discussion_title_enabled": True,
                "discussion_cover_pool_dir": str(ROOT / "cover-pool"),
            }
        )
        fake_generator = mock.Mock()
        fake_generator.generate_promo.return_value = {
            "title": "旧标题",
            "content": "正文内容",
            "digest": "摘要",
        }
        fake_publisher = mock.Mock()
        fake_publisher.format_for_wechat.return_value = "<html>article</html>"
        fake_publisher.publish_article.return_value = {"media_id": "123"}
        fake_notifier = mock.Mock()

        with mock.patch.object(scheduler_app, "Config", return_value=fake_config), mock.patch.object(
            scheduler_app,
            "get_hot_topic_from_weibo_hot_search",
            return_value={"title": "男女那些事", "cover_image_url": None},
        ), mock.patch.object(
            scheduler_app,
            "PromoGenerator",
            return_value=fake_generator,
        ), mock.patch.object(
            scheduler_app,
            "WeChatPublisher",
            return_value=fake_publisher,
        ), mock.patch.object(
            scheduler_app,
            "resolve_cover_path_from_pool",
            return_value=cover_path,
        ) as pool_cover_mock, mock.patch.object(
            scheduler_app,
            "BarkNotifier",
            return_value=fake_notifier,
        ):
            result = scheduler_app.job()

        self.assertTrue(result)
        pool_cover_mock.assert_called_once_with(
            str(ROOT / "cover-pool"),
            title="发现中国有一个奇怪的现象：男女那些事",
        )
        self.assertEqual(
            fake_publisher.format_for_wechat.call_args.kwargs["title"],
            "发现中国有一个奇怪的现象：男女那些事",
        )
        self.assertEqual(
            fake_publisher.format_for_wechat.call_args.kwargs["cover_image"],
            cover_path,
        )
        self.assertFalse(Path(cover_path).exists())


if __name__ == "__main__":
    unittest.main()
