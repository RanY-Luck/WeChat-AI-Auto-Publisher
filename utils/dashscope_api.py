import dashscope
from http import HTTPStatus
from config.config import DASHSCOPE_API_KEY, DASHSCOPE_MODEL
from utils.logger import setup_logger

logger = setup_logger("dashscope_api")


class DashScopeAPI:
    """
    阿里云百炼 (DashScope) API 工具类
    """

    def __init__(self):
        self.api_key = DASHSCOPE_API_KEY
        if not self.api_key or "sk-" not in self.api_key:
            logger.warning("未配置有效的 DASHSCOPE_API_KEY，请在 config/config.py 中配置")

        dashscope.api_key = self.api_key

    def generate_text(self, prompt, model=DASHSCOPE_MODEL):
        """
        生成文本内容
        """
        try:
            logger.info(f"正在调用 DashScope 生成文本，模型: {model}")

            response = self._call_model(prompt, model)

            if response.status_code == HTTPStatus.OK:
                content = self._extract_text_content(response)
                logger.info("DashScope 文本生成成功")
                return content

            error_msg = f"DashScope 调用失败: Code {response.code}, Message {response.message}"
            logger.error(error_msg)
            raise Exception(error_msg)

        except Exception as e:
            logger.error(f"DashScope 生成异常: {e}")
            raise

    def _call_model(self, prompt, model):
        if self._is_qwen3_model(model):
            return dashscope.MultiModalConversation.call(
                model=model,
                messages=[{'role': 'user', 'content': [{'text': prompt}]}],
            )

        return dashscope.Generation.call(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            result_format='message',
        )

    @staticmethod
    def _is_qwen3_model(model):
        return isinstance(model, str) and model.startswith("qwen3")

    def _extract_text_content(self, response):
        try:
            content = response.output.choices[0]['message']['content']
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise Exception("DashScope 返回结构异常，无法提取文本内容") from exc

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('text'):
                    text_parts.append(item['text'])

            if text_parts:
                return ''.join(text_parts)

        raise Exception("DashScope 返回内容中未找到可用文本")
