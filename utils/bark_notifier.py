import requests
from config.config import Config
from utils.logger import setup_logger

logger = setup_logger("bark_notifier")

class BarkNotifier:
    MAX_BODY_LENGTH = 1000

    def __init__(self):
        self.config = Config()
        self.api_key = getattr(self.config, 'BARK_KEY', None)
        
    def send(self, title, content, group="AI助手", url=None, icon=None, level=None):
        """
        发送 Bark 通知
        :param title: 通知标题
        :param content: 通知内容
        :param group: 分组名称
        :param url: 点击通知后跳转链接
        :param icon: 通知图标
        :param level: 通知级别
        """
        if not self.api_key:
            logger.warning("未配置 BARK_KEY，跳过发送通知")
            return False
            
        api_url = f"https://api.day.app/{self.api_key}/"
        body = self._truncate_body(str(content))
        
        data = {
            "title": title,
            "body": body,
            "group": group,
            "icon": "https://cdn-icons-png.flaticon.com/512/2583/2583259.png" if icon is None else icon # AI 图标
        }

        if url is not None:
            data["url"] = url
        if level is not None:
            data["level"] = level
        
        try:
            response = requests.post(api_url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Bark 通知发送成功: {title}")
                return True
            else:
                logger.error(f"Bark 通知发送失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Bark 通知发送异常: {e}")
            return False

    def _truncate_body(self, content):
        if len(content) <= self.MAX_BODY_LENGTH:
            return content
        return f"{content[: self.MAX_BODY_LENGTH - 3]}..."
