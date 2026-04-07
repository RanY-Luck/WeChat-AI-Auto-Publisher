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
        你是一位拥有10年经验的资深短视频和公众号运营专家，擅长跨平台内容重构与爆款公式设计。
        
        任务：请分析以下输入内容，结合中国用户心理、利用悬念前置、感官刺激、认知冲突等钩子，设计爆款中文标题、热门中文标签和一段情感小文章。
        
        输入内容：
        {input_text}
        
        要求：
        要求：
        1. 关键词 (keyword)：从输入内容中提炼核心名词，2-5个字（例如：深夜加班）。
        2. 副标题 (subtitle)：6-8个字，总结文章情感或核心主旨，唯美、感性（例如：再见，不是终点）。
        3. 摘要 (digest)：80-100字，作为微信公众号的封面摘要，要吸引人点击，语句通顺完整。
        4. 标签 (tags)：8个以上，紧扣主题，包含热门话题标签，每个标签前加"#"，用空格分隔。
        5. 内容 (content)：约150字，语气感性、温暖，能够触动人心，引发读者共鸣。
        
        请严格按照以下 JSON 格式输出：
        {{
            "keyword": "核心名词",
            "subtitle": "6-8个字的唯美短句",
            "digest": "这里是微信封面摘要...",
            "tags": "#标签1 #标签2 #标签3...",
            "content": "这里是情感小文章内容..."
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
                
                # 组合特定格式的标题: 远方岛屿 {keyword} | {subtitle}
                keyword = result.get("keyword", input_text[:5]) # 降级处理
                subtitle = result.get("subtitle", "未生成标题")
                result["title"] = f"远方夜听 {keyword} | {subtitle}"
                
                # 确保有摘要，如果没有则使用内容截断（后备方案）
                if not result.get("digest"):
                    result["digest"] = result.get("content", "")[:100]
                
                return result
            except json.JSONDecodeError:
                logger.warning("JSON解析失败，尝试简单提取或返回原始文本")
                # 如果解析失败，尝试手动构造结构（这里简单返回）
                return {
                    "title": f"远方夜听 {input_text[:5]} | 自动生成失败",
                    "digest": response_text[:100],
                    "tags": "",
                    "content": response_text
                }
                
        except Exception as e:
            logger.error(f"生成文案失败: {e}")
            return None
