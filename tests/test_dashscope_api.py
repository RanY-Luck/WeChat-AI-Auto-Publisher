import unittest
from types import SimpleNamespace
from unittest.mock import patch

from utils.dashscope_api import DashScopeAPI


class DashScopeAPITest(unittest.TestCase):
    def test_generate_text_uses_generation_for_legacy_models(self):
        response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[{'message': {'content': 'legacy text'}}]
            ),
            code='',
            message='',
        )

        with patch('utils.dashscope_api.dashscope.Generation.call', return_value=response) as generation_call, \
             patch('utils.dashscope_api.dashscope.MultiModalConversation.call') as multimodal_call:
            client = DashScopeAPI()

            result = client.generate_text('hello', model='qwen-plus')

        self.assertEqual(result, 'legacy text')
        generation_call.assert_called_once_with(
            model='qwen-plus',
            messages=[{'role': 'user', 'content': 'hello'}],
            result_format='message',
        )
        multimodal_call.assert_not_called()

    def test_generate_text_uses_multimodal_for_qwen3_models(self):
        response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[{'message': {'content': [{'text': 'qwen3 text'}]}}]
            ),
            code='',
            message='',
        )

        with patch('utils.dashscope_api.dashscope.Generation.call') as generation_call, \
             patch('utils.dashscope_api.dashscope.MultiModalConversation.call', return_value=response) as multimodal_call:
            client = DashScopeAPI()

            result = client.generate_text('hello', model='qwen3.6-plus')

        self.assertEqual(result, 'qwen3 text')
        generation_call.assert_not_called()
        multimodal_call.assert_called_once_with(
            model='qwen3.6-plus',
            messages=[{'role': 'user', 'content': [{'text': 'hello'}]}],
        )


if __name__ == '__main__':
    unittest.main()
