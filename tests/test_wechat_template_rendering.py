import unittest
from types import SimpleNamespace
from unittest.mock import patch

from utils.wechat_publisher import WeChatPublisher


class WeChatTemplateRenderingTest(unittest.TestCase):
    def _create_publisher(self):
        fake_config = SimpleNamespace(
            LOG_DIR='.',
            WECHAT_CONFIG={},
            PUBLISH_CONFIG={},
        )

        with patch('utils.wechat_publisher.Config', return_value=fake_config), \
             patch('utils.wechat_publisher.setup_logger'):
            return WeChatPublisher()

    def test_normalize_template_html_decodes_editor_copy(self):
        publisher = self._create_publisher()

        normalized = publisher._normalize_template_html(
            '<section+style="text-align:+center;">Hello+World</section>'
        )

        self.assertIn('<section style="text-align: center;">', normalized)
        self.assertIn('Hello World', normalized)

    def test_format_for_wechat_injects_rendered_body_into_template(self):
        publisher = self._create_publisher()

        with patch.object(
            publisher,
            '_load_template',
            return_value='<section class="shell">{{content}}</section>',
        ):
            article = publisher.format_for_wechat(
                content='第一段\n\n第二段',
                title='模板标题',
                author='作者',
                summary='摘要',
                template_name='wechat_default',
            )

        self.assertEqual(article['title'], '模板标题')
        self.assertIn('<section class="shell">', article['content'])
        self.assertIn('<p>第一段</p><p>第二段</p>', article['content'])


if __name__ == '__main__':
    unittest.main()
