import os
import logging
import requests
import json
import time
import re
from html import unescape
from PIL import Image
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
            self.proxy_url = self.config.WECHAT_CONFIG.get("proxy_url", "")  # 新增:代理服务器
            self.access_token = None
            self.access_token_expire_time = 0

            # 配置代理
            if self.proxy_url:
                self.proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                self.logger.info(f"✅ 已配置微信API代理: {self.proxy_url}")
            else:
                self.proxies = None
                self.logger.warning("⚠️ 未配置代理,可能遇到IP白名单问题")

        except AttributeError as e:
            self.logger.warning(f"未找到微信公众号配置: {str(e)}")
            self.app_id = ""
            self.app_secret = ""
            self.proxy_url = ""
            self.proxies = None
            self.access_token = None
            self.access_token_expire_time = 0

        self.logger.info("WeChatPublisher initialized successfully")

    def _make_request(self, method, url, **kwargs):
        """
        统一的请求方法,自动添加代理和重试逻辑

        Args:
            method: 请求方法 'GET' 或 'POST'
            url: 请求URL
            **kwargs: requests库的其他参数

        Returns:
            requests.Response对象
        """
        # 添加代理配置
        if self.proxies:
            kwargs['proxies'] = self.proxies

        # 设置默认超时
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30

        # 重试配置
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, **kwargs)
                elif method.upper() == 'POST':
                    response = requests.post(url, **kwargs)
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")

                response.raise_for_status()
                return response

            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                self.logger.warning(
                    f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    self.logger.info(f"{delay}秒后重试...")
                    time.sleep(delay)
                else:
                    self.logger.error("所有重试都失败了")
                    raise
            except Exception as e:
                self.logger.error(f"请求异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                raise

    def format_for_wechat(self, content, title, author="", cover_image="", summary="", template_name=""):
        """
        格式化内容以适应微信公众号的排版要求

        Args:
            content (str): 文章内容
            title (str): 文章标题
            author (str, optional): 作者
            cover_image (str, optional): 封面图片路径
            summary (str, optional): 文章摘要
            template_name (str, optional): 模板文件名(不含扩展名)

        Returns:
            dict: 包含格式化后内容的字典
        """
        self.logger.info("开始格式化微信公众号文章")

        try:
            # 格式化标题
            formatted_title = self._format_title(title)

            # 格式化内容
            if template_name:
                formatted_content = self._render_template_content(template_name, content)
            else:
                formatted_content = self._format_content(content)

            # 格式化作者
            formatted_author = self._format_author(author)

            # 格式化摘要（微信公众号摘要限制为不超过120个字符）
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
        """格式化微信公众号标题"""
        MAX_TITLE_LENGTH = 32

        if len(title) > MAX_TITLE_LENGTH:
            self.logger.warning(f"标题过长({len(title)}字符)，自动截断至{MAX_TITLE_LENGTH}字符")
            title = title[:MAX_TITLE_LENGTH].strip()

        return title

    def _render_template_content(self, template_name, content):
        """将正文渲染到完整模板中"""
        template_html = self._load_template(template_name)
        if "{{content}}" not in template_html:
            raise ValueError(f"模板缺少 {{content}} 占位符: {template_name}")

        body_html = self._format_content(content)
        return template_html.replace("{{content}}", body_html, 1)

    def _load_template(self, template_name):
        """加载并标准化模板文件"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(project_root, "templates", f"{template_name}.html")

        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        with open(template_path, "r", encoding="utf-8") as template_file:
            return self._normalize_template_html(template_file.read())

    def _normalize_template_html(self, template_html):
        """把公众号编辑器复制出的源码还原成正常 HTML"""
        normalized = unescape(template_html or "")
        normalized = normalized.replace("+", " ")
        return normalized

    def _format_content(self, content):
        """格式化微信公众号文章内容"""
        blocks = re.split(r"\n\s*\n", (content or "").strip())
        rendered_blocks = []

        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue

            if len(lines) == 1 and lines[0].startswith("### "):
                rendered_blocks.append(f"<h4>{lines[0][4:]}</h4>")
                continue

            if len(lines) == 1 and lines[0].startswith("## "):
                rendered_blocks.append(f"<h3>{lines[0][3:]}</h3>")
                continue

            if len(lines) == 1 and lines[0].startswith("# "):
                rendered_blocks.append(f"<h2>{lines[0][2:]}</h2>")
                continue

            if all(line.startswith("- ") for line in lines):
                items = "".join(f"<li>{line[2:]}</li>" for line in lines)
                rendered_blocks.append(f"<ul>{items}</ul>")
                continue

            if all(re.match(r"^\d+\.\s+", line) for line in lines):
                items = []
                for line in lines:
                    item_text = re.sub(r"^\d+\.\s+", "", line)
                    items.append(f"<li>{item_text}</li>")
                items = "".join(items)
                rendered_blocks.append(f"<ol>{items}</ol>")
                continue

            if all(line.startswith("> ") for line in lines):
                quote_html = "<br/>".join(line[2:] for line in lines)
                rendered_blocks.append(f"<blockquote>{quote_html}</blockquote>")
                continue

            paragraph_html = "<br/>".join(lines)
            rendered_blocks.append(f"<p>{paragraph_html}</p>")

        return "".join(rendered_blocks)

    def _format_headings(self, content):
        """格式化标题"""
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
        """格式化列表"""
        content = content.replace("- ", "<li>")
        content = content.replace("\n- ", "</li><li>")

        import re
        content = re.sub(r'\n(\d+)\. ', r'</p><ol><li>', content, count=1)
        content = re.sub(r'\n(\d+)\. ', r'</li><li>', content)
        content = content.replace("</p>", "</li></ol></p>")

        return content

    def _format_quotes(self, content):
        """格式化引用"""
        content = content.replace("> ", "<blockquote>")
        content = content.replace("\n> ", "</blockquote><blockquote>")
        content = content.replace("</p>", "</blockquote></p>")
        return content

    def _format_author(self, author):
        """格式化作者信息"""
        return author or "未知作者"

    def _generate_summary(self, content):
        """生成文章摘要"""
        import re
        plain_text = re.sub(r'<[^>]+>', '', content)
        plain_text = plain_text.replace("\n", " ")
        summary = plain_text[:100] + "..." if len(plain_text) > 100 else plain_text
        return summary

    def get_access_token(self):
        """
        获取微信公众号的访问令牌
        实现缓存机制,避免重复请求

        Returns:
            str: 访问令牌
        """
        if not self.app_id or not self.app_secret:
            self.logger.error("微信公众号AppID和AppSecret未配置")
            raise ValueError("微信公众号AppID和AppSecret未配置")

        # 检查access_token是否有效
        current_time = time.time()
        if self.access_token and (current_time + 200) < self.access_token_expire_time:
            self.logger.info("使用缓存的access_token")
            return self.access_token

        try:
            url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"

            # 使用统一的请求方法(自动添加代理)
            response = self._make_request('GET', url)
            data = response.json()

            if "access_token" in data and "expires_in" in data:
                self.access_token = data["access_token"]
                self.access_token_expire_time = current_time + data["expires_in"]
                self.logger.info(
                    f"✅ 获取微信公众号访问令牌成功，有效期至: "
                    f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.access_token_expire_time))}"
                )
                return self.access_token
            else:
                # 特殊处理IP白名单错误
                if data.get("errcode") == 40164:
                    self.logger.error(
                        f"❌ IP白名单错误: {data.get('errmsg')}\n"
                        f"💡 解决方案:\n"
                        f"   1. 登录微信公众平台 -> 开发 -> 基本配置 -> IP白名单\n"
                        f"   2. 添加您的服务器IP到白名单\n"
                        f"   3. 或者配置一个固定IP的代理服务器"
                    )

                self.logger.error(f"获取访问令牌失败: {data}")
                raise Exception(f"获取访问令牌失败: {data}")

        except Exception as e:
            self.logger.error(f"获取访问令牌过程中出错: {e}")
            raise

    def publish_article(self, article, draft=False, thumb_media_id=None):
        """
        发布文章到微信公众号

        Args:
            article (dict): 格式化后的文章
            draft (bool): 是否保存为草稿
            thumb_media_id (str, optional): 封面图片的media_id

        Returns:
            dict: 发布结果
        """
        self.logger.info("开始发布文章到微信公众号")

        action = "保存草稿" if draft else "发布文章"

        # 微信字段长度限制
        MAX_TITLE_LENGTH = 64
        MAX_AUTHOR_LENGTH = 20
        MAX_DIGEST_LENGTH = 120

        try:
            # 检查配置
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

            # 上传封面图片
            cover_media_id = thumb_media_id
            if not cover_media_id and article.get("cover_image"):
                cover_media_id = self._upload_image(article["cover_image"], is_cover=True)

            # 处理字段
            title = article.get("title", "").strip()
            title = re.sub(r'\s+', ' ', title)[:MAX_TITLE_LENGTH]

            author = article.get("author", "").strip()
            author = re.sub(r'\s+', ' ', author)[:MAX_AUTHOR_LENGTH]

            digest = article.get("summary", "").strip()
            digest = re.sub(r'[\n\t\s]+', ' ', digest)[:MAX_DIGEST_LENGTH]

            content = article.get("content", "")

            self.logger.info(f"标题: {title} (长度:{len(title)})")
            self.logger.info(f"作者: {author} (长度:{len(author)})")
            self.logger.info(f"摘要: {digest} (长度:{len(digest)})")

            # 组装文章数据
            article_data = {
                "title": title,
                "author": author,
                "digest": digest,
                "content": content,
                "content_source_url": "",
                "need_open_comment": 1,
                "only_fans_can_comment": 0
            }

            if cover_media_id:
                article_data["thumb_media_id"] = cover_media_id

            # 选择接口
            if draft:
                url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={self.access_token}"
            else:
                url = f"https://api.weixin.qq.com/cgi-bin/material/add_news?access_token={self.access_token}"

            request_data = {"articles": [article_data]}

            # 发送请求(使用统一方法,自动添加代理)
            json_data = json.dumps(request_data, ensure_ascii=False).encode('utf-8')
            headers = {'Content-Type': 'application/json; charset=utf-8'}

            response = self._make_request('POST', url, data=json_data, headers=headers)
            result = response.json()

            self.logger.info(f"发布返回: {json.dumps(result, ensure_ascii=False)}")

            if "errcode" in result and result["errcode"] != 0:
                errcode = result["errcode"]
                errmsg = result["errmsg"]
                self.logger.error(f"{action}失败 - 错误码: {errcode}, 错误信息: {errmsg}")

                # 处理40007错误(无效media_id)
                if errcode == 40007:
                    self.logger.info("尝试不使用封面图片重新提交...")
                    new_article_data = article_data.copy()
                    new_article_data.pop("thumb_media_id", None)
                    new_request_data = {"articles": [new_article_data]}

                    retry_response = self._make_request(
                        'POST', url,
                        data=json.dumps(new_request_data, ensure_ascii=False).encode('utf-8'),
                        headers=headers
                    )
                    retry_result = retry_response.json()

                    if "errcode" in retry_result and retry_result["errcode"] != 0:
                        raise Exception(f"{action}失败(重试): {retry_result}")
                    else:
                        self.logger.info(f"{action}成功(重试): {retry_result}")
                        return retry_result

                raise Exception(f"{action}失败: {result}")
            else:
                self.logger.info(f"✅ {action}成功: {result}")

                # 自动发布
                if draft and result.get("media_id"):
                    media_id = result["media_id"]
                    self.logger.info(f"草稿保存成功,开始自动发布,media_id: {media_id}")

                    try:
                        publish_result = self._submit_publish(media_id)
                        result["publish_result"] = publish_result
                        self.logger.info(f"文章自动发布成功: {publish_result}")
                    except Exception as publish_error:
                        self.logger.error(f"自动发布失败(草稿已保存): {publish_error}")
                        result["publish_error"] = str(publish_error)

                return result

        except Exception as e:
            self.logger.error(f"{action}过程中出错: {e}")
            raise

    def _submit_publish(self, media_id):
        """提交发布文章(群发)"""
        self.logger.info(f"开始提交发布,media_id: {media_id}")

        try:
            if not self.access_token:
                self.get_access_token()

            url = f"https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token={self.access_token}"
            data = {"media_id": media_id}

            # 使用统一请求方法
            response = self._make_request(
                'POST', url,
                data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json; charset=utf-8'}
            )

            result = response.json()
            self.logger.info(f"发布接口返回: {json.dumps(result, ensure_ascii=False)}")

            if "errcode" in result and result["errcode"] != 0:
                errcode = result["errcode"]
                errmsg = result.get("errmsg", "未知错误")

                if errcode == 48001:
                    self.logger.warning("⚠️ 自动发布需要认证服务号权限")
                    return {
                        "errcode": errcode,
                        "errmsg": errmsg,
                        "hint": "自动发布需要认证服务号权限,请手动发布草稿"
                    }

                raise Exception(f"发布失败: {result}")

            publish_id = result.get("publish_id")
            if publish_id:
                self.logger.info(f"✅ 文章发布任务提交成功,publish_id: {publish_id}")

            return result

        except Exception as e:
            self.logger.error(f"提交发布过程中出错: {e}")
            raise

    def _resize_image(self, image_path, target_width=900, target_height=383):
        """调整图片大小以符合微信公众号要求"""
        try:
            with Image.open(image_path) as img:
                original_width, original_height = img.size
                self.logger.info(f"原始图片尺寸: {original_width}x{original_height}")

                img = img.resize((target_width, target_height), Image.LANCZOS)
                self.logger.info(f"调整图片尺寸: {original_width}x{original_height} -> {target_width}x{target_height}")

                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_filename = os.path.join(temp_dir, f"temp_cover_{os.path.basename(image_path)}")
                temp_filename = temp_filename.replace(os.path.splitext(temp_filename)[1], '.jpg')

                quality = 85
                while True:
                    img.save(temp_filename, format='JPEG', quality=quality)
                    file_size = os.path.getsize(temp_filename)
                    if file_size <= 2 * 1024 * 1024 or quality <= 50:
                        break
                    quality -= 5

                temp_size = os.path.getsize(temp_filename)
                self.logger.info(f"调整后图片大小: {temp_size / 1024:.2f}KB,质量: {quality}")

                return temp_filename

        except Exception as e:
            self.logger.error(f"调整图片大小过程中出错: {e}")
            raise

    def _upload_image(self, image_path, is_cover=False):
        """上传图片到微信公众号"""
        self.logger.info(f"开始上传图片: {image_path}")

        try:
            if not os.path.exists(image_path):
                self.logger.error(f"图片不存在: {image_path}")
                raise FileNotFoundError(f"图片不存在: {image_path}")

            if not self.access_token:
                self.get_access_token()

            if is_cover:
                url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={self.access_token}&type=image"
                temp_file_path = self._resize_image(image_path)

                try:
                    with open(temp_file_path, "rb") as f:
                        data = {"description": json.dumps({"title": "封面图片"})}
                        files = {"media": f}

                        # 使用统一请求方法
                        response = self._make_request('POST', url, data=data, files=files)

                    result = response.json()
                    self.logger.info(f"上传封面返回: {json.dumps(result, ensure_ascii=False)}")

                    if result.get("media_id"):
                        self.logger.info(f"✅ 封面图片上传成功,media_id: {result['media_id']}")
                        return result["media_id"]
                    else:
                        self.logger.error(f"封面图片上传失败: {result}")
                        raise Exception(f"封面图片上传失败: {result}")
                finally:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
            else:
                url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={self.access_token}"

                with open(image_path, "rb") as f:
                    files = {"media": f}
                    response = self._make_request('POST', url, files=files)

                result = response.json()

                if result.get("url"):
                    self.logger.info(f"✅ 正文图片上传成功,URL: {result['url']}")
                    return result["url"]
                else:
                    self.logger.error(f"正文图片上传失败: {result}")
                    raise Exception(f"正文图片上传失败: {result}")

        except Exception as e:
            self.logger.error(f"图片上传过程中出错: {e}")
            raise
