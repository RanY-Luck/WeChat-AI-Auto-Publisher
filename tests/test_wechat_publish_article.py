import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from utils.wechat_publisher import WeChatPublisher


class WeChatPublishArticleTest(unittest.TestCase):
    def _create_publisher(self):
        fake_config = SimpleNamespace(
            LOG_DIR='.',
            WECHAT_CONFIG={
                'app_id': 'test-app-id',
                'app_secret': 'test-app-secret',
            },
            PUBLISH_CONFIG={},
        )

        with patch('utils.wechat_publisher.Config', return_value=fake_config), \
             patch('utils.wechat_publisher.setup_logger'):
            publisher = WeChatPublisher()

        publisher.access_token = 'test-access-token'
        return publisher

    def test_publish_article_enables_comments_for_all_users(self):
        publisher = self._create_publisher()
        captured_request = {}

        def fake_request(method, url, **kwargs):
            captured_request['method'] = method
            captured_request['url'] = url
            captured_request['data'] = json.loads(kwargs['data'].decode('utf-8'))
            return SimpleNamespace(json=lambda: {'media_id': 'draft-media-id'})

        with patch.object(publisher, '_make_request', side_effect=fake_request), \
             patch.object(publisher, '_submit_publish', return_value={'publish_id': 'publish-id'}):
            publisher.publish_article(
                {
                    'title': '测试标题',
                    'author': '测试作者',
                    'summary': '测试摘要',
                    'content': '<p>测试正文</p>',
                },
                draft=True,
            )

        article_data = captured_request['data']['articles'][0]
        self.assertEqual(article_data['need_open_comment'], 1)
        self.assertEqual(article_data['only_fans_can_comment'], 0)


if __name__ == '__main__':
    unittest.main()
