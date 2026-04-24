import json
import logging
from utils.dashscope_api import DashScopeAPI
from utils.logger import setup_logger

logger = setup_logger("promo_generator")

class PromoGenerator:
    def __init__(self):
        self.client = DashScopeAPI()

    def generate_promo(self, input_text):
        """
        根据输入文本生成爆款标题、标签和情感小文章
        
        Args:
            input_text (str): 输入的主题、草稿或描述
            
        Returns:
            dict: 包含 title, tags, content 的字典
        """
        logger.info(f"开始生成推广文案，输入: {input_text[:50]}...")
        
        prompt = f"""
        你是一位擅长公众号争议话题写作的中文内容策划，熟悉男女关系、家庭关系、情感冲突类选题。

        任务：围绕下面的输入主题，输出一篇能激发评论区讨论的公众号文案。整体方向要有观点冲突感，但不能低俗、不能违法违规。

        输入主题：
        {input_text}

        标题要求：
        1. 标题必须使用这个句式：发现中国有一个奇怪的现象：xxx
        2. xxx 必须直接围绕输入主题展开，不要改成诗意抒情标题
        3. 不要出现旧账号模板词，不要使用固定栏目包装语

        内容要求：
        1. 摘要 (digest)：80-100字，强调现象、冲突、讨论点，适合做封面摘要
        2. 标签 (tags)：8个以上，聚焦两性、婚姻、家庭、情感讨论，每个标签前加"#"，用空格分隔
        3. 内容 (content)：约350字，语气偏观点讨论、现实观察、引发站队和共鸣，不要写成治愈散文

        请严格按照以下 JSON 格式输出：
        {{
            "title": "发现中国有一个奇怪的现象：xxx",
            "digest": "这里是微信封面摘要...",
            "tags": "#标签1 #标签2 #标签3...",
            "content": "这里是观点型短文内容..."
        }}
        """
        
        try:
            # 使用 generate_text 生成内容
            response_text = self.client.generate_text(prompt)
            
            # 清理可能的 Markdown 代码块标记
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            
            # 尝试解析 JSON
            try:
                result = json.loads(cleaned_text)

                result["title"] = (result.get("title") or input_text).strip()
                # 确保有摘要，如果没有则使用内容截断（后备方案）
                if not result.get("digest"):
                    result["digest"] = result.get("content", "")[:100]

                return result
            except json.JSONDecodeError:
                logger.warning("JSON解析失败，尝试简单提取或返回原始文本")
                # 如果解析失败，尝试手动构造结构（这里简单返回）
                return {
                    "title": input_text.strip(),
                    "digest": response_text[:100],
                    "tags": "",
                    "content": response_text
                }
                
        except Exception as e:
            logger.error(f"生成文案失败: {e}")
            return None
