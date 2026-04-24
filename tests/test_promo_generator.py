from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _install_fake_modules():
    config_package = types.ModuleType("config")
    config_module = types.ModuleType("config.config")
    config_module.DASHSCOPE_API_KEY = ""
    config_module.DASHSCOPE_MODEL = "qwen3.6-plus"
    config_module.LOGGING_CONFIG = {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": str(ROOT / "logs" / "test.log"),
    }

    dashscope_module = types.ModuleType("dashscope")
    dashscope_module.api_key = ""

    sys.modules["config"] = config_package
    sys.modules["config.config"] = config_module
    sys.modules["dashscope"] = dashscope_module


_install_fake_modules()

from utils.promo_generator import PromoGenerator


class FakeClient:
    def __init__(self, response_text):
        self.response_text = response_text
        self.prompts = []

    def generate_text(self, prompt):
        self.prompts.append(prompt)
        return self.response_text


class PromoGeneratorTests(unittest.TestCase):
    def test_generate_promo_uses_discussion_style_prompt(self):
        generator = PromoGenerator()
        fake_client = FakeClient(
            """
            {
                "title": "发现中国有一个奇怪的现象：男女那些事",
                "digest": "这是摘要",
                "tags": "#两性 #婚姻",
                "content": "这是正文"
            }
            """
        )
        generator.client = fake_client

        generator.generate_promo("男女那些事")

        prompt = fake_client.prompts[0]
        self.assertIn("男女关系", prompt)
        self.assertIn("家庭关系", prompt)
        self.assertIn("情感冲突", prompt)
        self.assertIn("发现中国有一个奇怪的现象：", prompt)
        self.assertNotIn("远方夜听", prompt)
        self.assertNotIn("副标题 (subtitle)", prompt)
        self.assertIn("约350字", prompt)
        self.assertNotIn("约150字", prompt)

    def test_generate_promo_returns_model_title_without_old_prefix_template(self):
        generator = PromoGenerator()
        generator.client = FakeClient(
            """
            {
                "title": "发现中国有一个奇怪的现象：男女那些事",
                "digest": "这是摘要",
                "tags": "#两性 #婚姻",
                "content": "这是正文"
            }
            """
        )

        result = generator.generate_promo("男女那些事")

        self.assertEqual(result["title"], "发现中国有一个奇怪的现象：男女那些事")
        self.assertNotIn("远方夜听", result["title"])

    def test_generate_promo_fallback_title_does_not_use_old_template(self):
        generator = PromoGenerator()
        generator.client = FakeClient("not-json")

        result = generator.generate_promo("家庭那些事")

        self.assertEqual(result["title"], "家庭那些事")
        self.assertNotIn("远方夜听", result["title"])


if __name__ == "__main__":
    unittest.main()
