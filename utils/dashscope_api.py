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
            
            messages = [{'role': 'user', 'content': prompt}]
            
            response = dashscope.Generation.call(
                model=model,
                messages=messages,
                result_format='message',  # 设置为 'message' 格式返回
            )
            
            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0]['message']['content']
                logger.info("DashScope 文本生成成功")
                return content
            else:
                error_msg = f"DashScope 调用失败: Code {response.code}, Message {response.message}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"DashScope 生成异常: {e}")
            raise
