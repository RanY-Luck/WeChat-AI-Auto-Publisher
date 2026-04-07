import schedule
import time
import random
import os
import re
from html import unescape
import requests
from utils.promo_generator import PromoGenerator
from utils.wechat_publisher import WeChatPublisher
from utils.bark_notifier import BarkNotifier
from utils.logger import setup_logger
from config.config import Config
from PIL import Image

# 设置日志
logger = setup_logger("scheduler_app")

# 预设的随机主题库 (当网络热榜获取失败时回退)
RANDOM_TOPICS = [
    "深夜加班后的街头感悟", "一个人看电影的孤独与享受", "在此刻，想念一个很久不见的人",
    "二十岁时的梦想，现在还在坚持吗", "职场中那些瞬间长大的时刻", "在大城市漂泊的归属感",
    "旅行中遇到的陌生人善意", "读完一本书后的灵魂触动", "不得不说的再见：离别的意义",
    "关于自律：是自由还是束缚", "那些被我们忽略的微小幸福", "在这个快节奏时代慢下来",
    "成长的代价：我们通过失去学会珍惜", "独处，是成年人最好的奢侈品", "给未来的自己写一封信"
]


WEIBO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://s.weibo.com/top/summary?cate=realtimehot"
}


def extract_topics_from_weibo_html(html_text):
    """从微博热搜页面 HTML 提取话题列表"""
    matches = re.findall(r'<td class="td-02">[\s\S]*?<a[^>]*>([\s\S]*?)</a>', html_text)
    topics = []
    for match in matches:
        topic = re.sub(r"<.*?>", "", unescape(match)).strip()
        if topic and topic != "查看更多热搜":
            topics.append(topic)
    return topics


def get_topic_from_weibo_hot_search():
    """获取微博热搜话题，失败时返回 None"""
    try:
        response = requests.get(
            "https://weibo.com/ajax/side/hotSearch",
            headers=WEIBO_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        realtime_list = data.get("data", {}).get("realtime", [])

        topics = []
        for item in realtime_list:
            word = (item.get("word") or item.get("word_scheme") or "").strip()
            if word:
                topics.append(word)

        if topics:
            topic = random.choice(topics)
            logger.info(f"微博热搜接口获取成功，候选数量: {len(topics)}，选中话题: {topic}")
            return topic

        logger.warning("微博热搜接口返回为空，尝试页面抓取")
    except Exception as e:
        logger.warning(f"微博热搜接口获取失败: {e}，尝试页面抓取")

    try:
        response = requests.get(
            "https://s.weibo.com/top/summary?cate=socialevent",
            headers=WEIBO_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        topics = extract_topics_from_weibo_html(response.text)

        if not topics:
            logger.warning("微博热搜页面解析为空")
            return None

        topic = random.choice(topics)
        logger.info(f"微博热搜页面抓取成功，候选数量: {len(topics)}，选中话题: {topic}")
        return topic
    except Exception as e:
        logger.warning(f"微博热搜页面抓取失败: {e}")
        return None


def generate_default_cover():
    """生成默认封面 (复制自 generate_promo.py)"""
    try:
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        width, height = 900, 383
        color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
        img = Image.new('RGB', (width, height), color=color)
        filename = f"sched_cover_{int(time.time())}.jpg"
        filepath = os.path.join(temp_dir, filename)
        img.save(filepath)
        return filepath
    except Exception as e:
        logger.error(f"封面生成失败: {e}")
        return None


def job():
    """定时执行的任务"""
    config = Config()
    topic = get_topic_from_weibo_hot_search()
    if not topic:
        topic = random.choice(RANDOM_TOPICS)
        logger.info(f"微博热搜不可用，回退到预设主题: {topic}")

    logger.info(f"⏰ 开始执行定时任务，本次主题: {topic}")

    notifier = BarkNotifier()

    try:
        # 1. 生成文案
        generator = PromoGenerator()
        result = generator.generate_promo(topic)

        if not result:
            logger.error("文案生成失败")
            notifier.send(title="定时任务失败", content="文案生成失败，请检查日志")
            return

        logger.info(f"文案生成成功: {result.get('title')}")

        # 2. 准备发布
        publisher = WeChatPublisher()
        cover_path = generate_default_cover()

        if not cover_path:
            logger.error("封面生成失败")
            return

        # 3. 格式化
        article_template = (config.PUBLISH_CONFIG.get("article_template") or "").strip()
        content = result.get("content", "")
        if article_template:
            content_for_publish = content
        else:
            content_for_publish = f'<span style="font-size: 14px; font-weight: bold;">{content}</span>'

        formatted_article = publisher.format_for_wechat(
            content=content_for_publish,
            title=result.get('title'),
            author="Ran先生",
            summary=result.get('digest'),
            cover_image=cover_path,
            template_name=article_template,
        )

        # 4. 发布到草稿箱
        publish_result = publisher.publish_article(formatted_article, draft=True)

        if publish_result:
            msg = f"✅ 定时发布成功! Media ID: {publish_result.get('media_id')}"
            logger.info(msg)
            notifier.send(title="定时发布成功", content=f"主题: {topic}\n标题: {result.get('title')}")
        else:
            msg = "❌ 定时发布失败"
            logger.error(msg)
            notifier.send(title="定时发布失败", content=f"主题: {topic}\n请检查日志")

        # 清理
        if os.path.exists(cover_path):
            os.remove(cover_path)

    except Exception as e:
        logger.error(f"定时任务执行异常: {e}")
        notifier.send(title="定时任务异常", content=f"错误: {str(e)}")


def main():
    # 每天 20:00 执行
    scheduled_time = "14:30"
    schedule.every().day.at(scheduled_time).do(job)

    logger.info(f"🚀 发帖机器人已启动！将在每天 {scheduled_time} 自动运行。")
    logger.info("正在等待时间到达... (按 Ctrl+C 退出)")

    # 启动时先发个 Bark 确认存活
    BarkNotifier().send(title="服务启动", content=f"自动发文服务已在服务器启动\n每天 {scheduled_time} 执行")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
