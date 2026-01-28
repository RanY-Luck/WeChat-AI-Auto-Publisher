import os
import sys
import logging
import requests
import json
import time
import re
from PIL import Image
from io import BytesIO
from utils.logger import setup_logger
from config.config import Config

class WeChatPublisher:
    def __init__(self):
        # 加载配置
        self.config = Config()
        
        # 设置日志
        self.logger = setup_logger(
            name='WeChatPublisher',
            log_file=os.path.join(self.config.LOG_DIR, 'wechat_publisher.log'),
            level=logging.INFO
        )
        
        # 微信公众号配置
        try:
            self.app_id = self.config.WECHAT_CONFIG.get("app_id", "")
            self.app_secret = self.config.WECHAT_CONFIG.get("app_secret", "")
            self.access_token = None
            self.access_token_expire_time = 0  # 过期时间戳
        except AttributeError as e:
            self.logger.warning(f"未找到微信公众号配置: {str(e)}")
            self.app_id = ""
            self.app_secret = ""
            self.access_token = None
            self.access_token_expire_time = 0
        
        self.logger.info("WeChatPublisher initialized successfully")
    
    def format_for_wechat(self, content, title, author="", cover_image="", summary=""):
        """
        格式化内容以适应微信公众号的排版要求
        
        Args:
            content (str): 文章内容
            title (str): 文章标题
            author (str, optional): 作者
            cover_image (str, optional): 封面图片路径
            summary (str, optional): 文章摘要
        
        Returns:
            dict: 包含格式化后内容的字典
        """
        self.logger.info("开始格式化微信公众号文章")
        
        try:
            # 格式化标题
            formatted_title = self._format_title(title)
            
            # 格式化内容
            formatted_content = self._format_content(content)
            
            # 格式化作者
            formatted_author = self._format_author(author)
            
            # 格式化摘要（微信公众号摘要限制为不超过160个字符）
            MAX_SUMMARY_LENGTH = 100
            article_summary = summary or self._generate_summary(content)
            if len(article_summary) > MAX_SUMMARY_LENGTH:
                self.logger.warning(f"摘要过长({len(article_summary)}字符)，自动截断至{MAX_SUMMARY_LENGTH}字符")
                article_summary = article_summary[:MAX_SUMMARY_LENGTH].strip()
            
            # 生成完整的文章结构
            article = {
                "title": formatted_title,
                "author": formatted_author,
                "cover_image": cover_image,
                "summary": article_summary,
                "content": formatted_content,
                "raw_content": content
            }
            
            self.logger.info("微信公众号文章格式化完成")
            return article
            
        except Exception as e:
            self.logger.error(f"文章格式化过程中出错: {e}")
            raise
    
    def _format_title(self, title):
        """
        格式化微信公众号标题
        
        Args:
            title (str): 原始标题
        
        Returns:
            str: 格式化后的标题
        """
        # 微信公众号标题限制为不超过32个字符
        MAX_TITLE_LENGTH = 32
        
        if len(title) > MAX_TITLE_LENGTH:
            self.logger.warning(f"标题过长({len(title)}字符)，自动截断至{MAX_TITLE_LENGTH}字符")
            title = title[:MAX_TITLE_LENGTH].strip()
        
        return title
    
    def _format_content(self, content):
        """
        格式化微信公众号文章内容
        
        Args:
            content (str): 原始文章内容
        
        Returns:
            str: 格式化后的内容
        """
        # 替换换行符为微信公众号的换行标签
        formatted = content.replace("\n\n", "</p><p>")
        formatted = formatted.replace("\n", "<br/>")
        
        # 添加段落标签
        formatted = f"<p>{formatted}</p>"
        
        # 格式化标题
        formatted = self._format_headings(formatted)
        
        # 格式化列表
        formatted = self._format_lists(formatted)
        
        # 格式化引用
        formatted = self._format_quotes(formatted)
        
        return formatted
    
    def _format_headings(self, content):
        """
        格式化标题
        
        Args:
            content (str): 文章内容
        
        Returns:
            str: 格式化后的内容
        """
        # 替换Markdown标题为微信公众号的标题格式
        content = content.replace("# ", "<h2>")
        content = content.replace("\n# ", "</h2><h2>")
        content = content.replace("</p>", "</h2></p>")
        
        content = content.replace("## ", "<h3>")
        content = content.replace("\n## ", "</h3><h3>")
        content = content.replace("</p>", "</h3></p>")
        
        content = content.replace("### ", "<h4>")
        content = content.replace("\n### ", "</h4><h4>")
        content = content.replace("</p>", "</h4></p>")
        
        return content
    
    def _format_lists(self, content):
        """
        格式化列表
        
        Args:
            content (str): 文章内容
        
        Returns:
            str: 格式化后的内容
        """
        # 替换无序列表
        content = content.replace("- ", "<li>")
        content = content.replace("\n- ", "</li><li>")
        
        # 替换有序列表
        import re
        content = re.sub(r'\n(\d+)\. ', r'</p><ol><li>', content, count=1)
        content = re.sub(r'\n(\d+)\. ', r'</li><li>', content)
        
        # 关闭列表标签
        content = content.replace("</p>", "</li></ol></p>")
        
        return content
    
    def _format_quotes(self, content):
        """
        格式化引用
        
        Args:
            content (str): 文章内容
        
        Returns:
            str: 格式化后的内容
        """
        # 替换Markdown引用为微信公众号的引用格式
        content = content.replace("> ", "<blockquote>")
        content = content.replace("\n> ", "</blockquote><blockquote>")
        content = content.replace("</p>", "</blockquote></p>")
        
        return content
    
    def _format_author(self, author):
        """
        格式化作者信息
        
        Args:
            author (str): 原始作者信息
        
        Returns:
            str: 格式化后的作者信息
        """
        return author or "未知作者"
    
    def _generate_summary(self, content):
        """
        生成文章摘要
        
        Args:
            content (str): 文章内容
        
        Returns:
            str: 文章摘要
        """
        # 简单生成摘要：取前150个字符
        import re
        # 移除HTML标签
        plain_text = re.sub(r'<[^>]+>', '', content)
        # 移除换行符
        plain_text = plain_text.replace("\n", " ")
        # 取前150个字符
        summary = plain_text[:100] + "..." if len(plain_text) > 100 else plain_text
        
        return summary
    
    def get_access_token(self):
        """
        获取微信公众号的访问令牌
        实现缓存机制，避免重复请求
        
        Returns:
            str: 访问令牌
        """
        import time
        
        if not self.app_id or not self.app_secret:
            self.logger.error("微信公众号AppID和AppSecret未配置")
            raise ValueError("微信公众号AppID和AppSecret未配置")
        
        # 检查access_token是否有效（有效期7200秒，提前200秒刷新）
        current_time = time.time()
        if self.access_token and (current_time + 200) < self.access_token_expire_time:
            self.logger.info("使用缓存的access_token")
            return self.access_token
        
        try:
            url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
            response = requests.get(url)
            data = response.json()
            
            if "access_token" in data and "expires_in" in data:
                self.access_token = data["access_token"]
                self.access_token_expire_time = current_time + data["expires_in"]
                self.logger.info(f"获取微信公众号访问令牌成功，有效期至: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.access_token_expire_time))}")
                return self.access_token
            else:
                self.logger.error(f"获取访问令牌失败: {data}")
                raise Exception(f"获取访问令牌失败: {data}")
                
        except Exception as e:
            self.logger.error(f"获取访问令牌过程中出错: {e}")
            raise
    

    def publish_article(self, article, draft=False, thumb_media_id=None):
        """
        发布文章到微信公众号（修复digest超限+字段限制+日志完善）
        
        Args:
            article (dict): 格式化后的文章
            draft (bool): 是否保存为草稿
            thumb_media_id (str, optional): 封面图片的media_id，如果提供则跳过上传
        
        Returns:
            dict: 发布结果
        """
        self.logger.info("开始发布文章到微信公众号")
        
        # 提前定义action变量，避免异常时变量未定义
        action = "保存草稿" if draft else "发布文章"
        
        # 微信字段长度官方限制（统一常量）
        MAX_TITLE_LENGTH = 64    # 标题上限
        MAX_AUTHOR_LENGTH = 20   # 作者上限
        MAX_DIGEST_LENGTH = 120  # 摘要上限（核心：微信实际是120字符，不是200/60）
        
        try:
            # 检查微信公众号配置
            if not self.app_id or not self.app_secret:
                self.logger.warning("微信公众号配置不完整，无法发布文章")
                return {
                    "errcode": -1,
                    "errmsg": "微信公众号配置不完整，无法发布文章",
                    "config_missing": True
                }
            
            # 获取访问令牌
            if not self.access_token:
                self.get_access_token()
            
            # 上传封面图片（如果有）
            cover_media_id = thumb_media_id  # 如果提供了thumb_media_id，则直接使用
            if not cover_media_id and article.get("cover_image"):
                cover_media_id = self._upload_image(article["cover_image"], is_cover=True)
            
            # ========== 核心修复1：处理所有字段，清理+截断+验证长度 ==========
            # 1. 处理标题（≤64字符，清理隐形字符）
            title = article.get("title", "").strip()
            title = re.sub(r'\s+', ' ', title)[:MAX_TITLE_LENGTH]
            self.logger.info(f"标题处理后：{title}（长度：{len(title)}）")
            
            # 2. 处理作者（≤20字符，清理隐形字符）
            author = article.get("author", "").strip()
            author = re.sub(r'\s+', ' ', author)[:MAX_AUTHOR_LENGTH]
            self.logger.info(f"作者处理后：{author}（长度：{len(author)}）")
            
            # 3. 处理摘要（核心：清理所有隐形字符+截断到120+验证长度）
            digest = article.get("summary", "").strip()
            # 清理所有隐形字符（换行/制表符/连续空格→单个空格）
            digest = re.sub(r'[\n\t\s]+', ' ', digest)
            # 截断到120字符（微信官方上限）
            digest = digest[:MAX_DIGEST_LENGTH]
            # 强制验证长度，打印日志
            self.logger.info(f"摘要处理后：{digest}（长度：{len(digest)}）")
            if len(digest) > MAX_DIGEST_LENGTH:
                self.logger.error(f"摘要长度仍超限！处理后长度：{len(digest)}，上限：{MAX_DIGEST_LENGTH}")
            
            # 4. 处理正文（仅做基础非空检查）
            content = article.get("content", "")
            if not content:
                self.logger.warning("正文content字段为空，可能导致发布失败")
            # ========== 组装文章数据 ==========
            article_data = {
                "title": title,
                "author": author,
                "digest": digest,
                "content": content,
                "content_source_url": "",  # 原文链接
                "need_open_comment": 0,
                "only_fans_can_comment": 0
            }
            # 记录cover_media_id的状态
            self.logger.info(f"封面图片media_id状态: cover_media_id={cover_media_id}, type={type(cover_media_id)}")
            
            # 只有当cover_media_id有效时才设置thumb_media_id字段
            if cover_media_id:
                article_data["thumb_media_id"] = cover_media_id
                self.logger.info(f"已设置thumb_media_id为: {cover_media_id}")
            else:
                self.logger.info("未设置thumb_media_id，因为cover_media_id无效")
            
            # 选择发布接口
            if draft:
                url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={self.access_token}"
            else:
                url = f"https://api.weixin.qq.com/cgi-bin/material/add_news?access_token={self.access_token}"
            
            # ========== 核心修复2：完善请求体日志，修复response未定义问题 ==========
            # 记录完整的请求参数
            request_data = {"articles": [article_data]}
            # 检查请求体格式并打印
            try:
                json_str = json.dumps(request_data, ensure_ascii=False, indent=2)
                self.logger.info(f"保存草稿/发布文章请求体: {json_str}")
            except Exception as e:
                self.logger.error(f"请求体序列化时出错: {e}")
            
            # 检查content字段是否有效
            if not content:
                self.logger.warning("content字段为空")
            elif len(content) < 10:
                self.logger.warning(f"content字段过短: {content[:20]}...")
            
            # ========== 发送请求（修复response日志顺序，确保UTF-8编码） ==========
            self.logger.info(f"发送请求到: {url}")
            response = None  # 初始化response，避免未定义
            try:
                # 手动序列化JSON，确保UTF-8编码
                json_data = json.dumps(request_data, ensure_ascii=False).encode('utf-8')
                headers = {
                    'Content-Type': 'application/json; charset=utf-8'
                }
                response = requests.post(url, data=json_data, headers=headers, timeout=30)
                response.raise_for_status()  # 检查HTTP响应状态码
                
                # 打印请求头（修复：发送后再打印，此时response已定义）
                self.logger.info(f"请求头: {json.dumps(dict(response.request.headers), ensure_ascii=False)}")
                self.logger.info(f"响应状态码: {response.status_code}")
                self.logger.info(f"响应头: {json.dumps(dict(response.headers), ensure_ascii=False)}")
                
                result = response.json()
                self.logger.info(f"保存草稿/发布文章返回结果: {json.dumps(result, ensure_ascii=False)}")
                
                # 检查结果
                if "errcode" in result and result["errcode"] != 0:
                    errcode = result["errcode"]
                    errmsg = result["errmsg"]
                    self.logger.error(f"{action}失败 - 错误码: {errcode}, 错误信息: {errmsg}")
                    
                    # 特殊处理40007错误（无效media_id）
                    if errcode == 40007:
                        self.logger.error("无效的media_id，可能是因为封面图片上传失败或media_id已过期")
                        self.logger.info("尝试不使用封面图片重新提交...")
                        
                        # 创建不包含thumb_media_id的新请求
                        new_article_data = article_data.copy()
                        new_article_data.pop("thumb_media_id", None)  # 安全删除，避免KeyError
                        
                        new_request_data = {"articles": [new_article_data]}
                        self.logger.info(f"重新提交请求体: {json.dumps(new_request_data, ensure_ascii=False, indent=2)}")
                        
                        retry_response = requests.post(url, json=new_request_data, timeout=30)
                        retry_response.raise_for_status()
                        
                        retry_result = retry_response.json()
                        self.logger.info(f"重新提交返回结果: {json.dumps(retry_result, ensure_ascii=False)}")
                        
                        if "errcode" in retry_result and retry_result["errcode"] != 0:
                            raise Exception(f"{action}失败 (重试): {retry_result}")
                        else:
                            self.logger.info(f"{action}成功 (重试): {retry_result}")
                            return retry_result
                    
                    raise Exception(f"{action}失败: {result}")
                else:
                    # 不存在错误码，说明请求成功
                    self.logger.info(f"{action}成功: {result}")
                    return result
            
            except requests.exceptions.RequestException as e:
                self.logger.error(f"发送请求时出错: {e}")
                if response is not None and hasattr(response, 'text'):
                    self.logger.error(f"响应内容: {response.text}")
                raise
                
        except Exception as e:
            self.logger.error(f"{action}过程中出错: {e}")
            raise
    
    def _resize_image(self, image_path, target_width=900, target_height=383):
        """
        调整图片大小以符合微信公众号要求
        微信公众号封面图片要求：
        - 尺寸：900x383像素（或等比例，推荐使用标准尺寸）
        - 大小：不超过2MB
        - 格式：JPG、PNG等
        
        Args:
            image_path (str): 图片路径
            target_width (int): 目标宽度（默认900像素）
            target_height (int): 目标高度（默认383像素）
            
        Returns:
            str: 调整后的图片临时文件路径
        """
        try:
            # 打开图片
            with Image.open(image_path) as img:
                # 记录原始尺寸
                original_width, original_height = img.size
                self.logger.info(f"原始图片尺寸: {original_width}x{original_height}")
                
                # 直接调整为目标尺寸（微信推荐的标准封面尺寸）
                img = img.resize((target_width, target_height), Image.LANCZOS)
                self.logger.info(f"调整图片尺寸: {original_width}x{original_height} -> {target_width}x{target_height}")
                
                # 保存到临时文件
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_filename = os.path.join(temp_dir, f"temp_cover_{os.path.basename(image_path)}")
                temp_filename = temp_filename.replace(os.path.splitext(temp_filename)[1], '.jpg')
                
                # 保存为JPEG格式，确保质量和大小符合要求
                # 根据图片内容自动调整质量，确保文件大小不超过2MB
                quality = 85
                while True:
                    img.save(temp_filename, format='JPEG', quality=quality)
                    file_size = os.path.getsize(temp_filename)
                    if file_size <= 2 * 1024 * 1024 or quality <= 50:
                        break
                    quality -= 5
                
                # 检查临时文件大小
                temp_size = os.path.getsize(temp_filename)
                self.logger.info(f"调整后图片大小: {temp_size / 1024:.2f}KB")
                self.logger.info(f"调整后图片格式: JPEG，质量: {quality}")
                
                return temp_filename
                
        except Exception as e:
            self.logger.error(f"调整图片大小过程中出错: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise

    def _upload_image(self, image_path, is_cover=False):
        """
        上传图片到微信公众号
        
        Args:
            image_path (str): 图片路径
            is_cover (bool): 是否为封面图片
        
        Returns:
            str: 媒体ID或图片URL
        """
        self.logger.info(f"开始上传图片: {image_path}")
        
        try:
            if not os.path.exists(image_path):
                self.logger.error(f"图片不存在: {image_path}")
                raise FileNotFoundError(f"图片不存在: {image_path}")
            
            # 获取访问令牌
            if not self.access_token:
                self.get_access_token()
            
            # 重试配置
            max_retries = 3
            retry_delay = 2  # 初始延迟2秒
            
            for attempt in range(max_retries):
                try:
                    if is_cover:
                        # 上传封面图片，使用material/add_material接口上传永久素材
                        # 微信公众号封面图片应该使用永久素材，而不是临时素材
                        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={self.access_token}&type=image"
                        
                        # 调整图片大小以符合微信封面图片要求：900x383像素
                        temp_file_path = self._resize_image(image_path)
                        
                        try:
                            # 上传永久素材
                            with open(temp_file_path, "rb") as f:
                                data = {
                                    "description": json.dumps({"title": "封面图片"})
                                }
                                files = {
                                    "media": f
                                }
                                # 设置30秒超时，添加SSL错误处理
                                response = requests.post(url, data=data, files=files, timeout=30)
                            
                            result = response.json()
                            self.logger.info(f"上传封面图片返回完整结果: {json.dumps(result, ensure_ascii=False)}")
                            
                            if result.get("media_id"):
                                self.logger.info(f"封面图片上传成功，media_id: {result['media_id']}")
                                return result["media_id"]
                            else:
                                self.logger.error(f"封面图片上传失败: {result}")
                                raise Exception(f"封面图片上传失败: {result}")
                        finally:
                            # 删除临时文件
                            if os.path.exists(temp_file_path):
                                os.remove(temp_file_path)
                                self.logger.info(f"已删除临时文件: {temp_file_path}")
                    else:
                        # 上传正文图片，使用media/uploadimg接口
                        url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={self.access_token}"
                        
                        with open(image_path, "rb") as f:
                            files = {"media": f}
                            # 设置30秒超时，添加SSL错误处理
                            response = requests.post(url, files=files, timeout=30)
                        
                        result = response.json()
                        
                        if result.get("url"):
                            self.logger.info(f"正文图片上传成功，URL: {result['url']}")
                            return result["url"]
                        else:
                            self.logger.error(f"正文图片上传失败: {result}")
                            raise Exception(f"正文图片上传失败: {result}")
                
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    self.logger.warning(f"图片上传尝试 {attempt + 1}/{max_retries} 失败 (网络/SSL错误): {e}")
                    if attempt < max_retries - 1:
                        # 计算下一次重试的延迟时间（指数退避）
                        delay = retry_delay * (2 ** attempt)
                        self.logger.info(f"{delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        self.logger.error(f"图片上传所有重试尝试都失败了")
                        raise
                except Exception as e:
                    self.logger.error(f"图片上传尝试 {attempt + 1}/{max_retries} 失败 (其他错误): {e}")
                    raise
        
        except Exception as e:
            self.logger.error(f"图片上传过程中出错: {e}")
            raise

# 测试代码
if __name__ == "__main__":
    publisher = WeChatPublisher()
    
    # 示例内容
    test_content = """
# 深度学习入门

深度学习是机器学习的一个分支，它通过模拟人脑的神经网络结构来处理数据。

## 核心概念

- 神经网络
- 激活函数
- 损失函数
- 优化算法

## 应用领域

1. 计算机视觉
2. 自然语言处理
3. 语音识别

> 深度学习正在改变我们的生活方式。

深度学习的未来充满无限可能！
"""
    
    try:
        formatted_article = publisher.format_for_wechat(
            content=test_content,
            title="深度学习入门指南",
            author="AI研究社"
        )
        
        print("\n格式化后的文章：")
        print(f"标题: {formatted_article['title']}")
        print(f"作者: {formatted_article['author']}")
        print(f"摘要: {formatted_article['summary']}")
        print(f"内容: {formatted_article['content']}")
        
    except Exception as e:
        print(f"测试失败: {e}")