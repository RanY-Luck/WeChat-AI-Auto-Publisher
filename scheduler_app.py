import schedule
import time
import random
import os
from utils.promo_generator import PromoGenerator
from utils.wechat_publisher import WeChatPublisher
from utils.bark_notifier import BarkNotifier
from utils.logger import setup_logger
from PIL import Image

# 设置日志
logger = setup_logger("scheduler_app")

# 预设的随机主题库 (可以扩展或替换为从网络热榜获取)
RANDOM_TOPICS = [
    "深夜加班后的街头感悟", "一个人看电影的孤独与享受", "在此刻，想念一个很久不见的人",
    "二十岁时的梦想，现在还在坚持吗", "职场中那些瞬间长大的时刻", "在大城市漂泊的归属感",
    "旅行中遇到的陌生人善意", "读完一本书后的灵魂触动", "不得不说的再见：离别的意义",
    "关于自律：是自由还是束缚", "那些被我们忽略的微小幸福", "在这个快节奏时代慢下来",
    "成长的代价：我们通过失去学会珍惜", "独处，是成年人最好的奢侈品", "给未来的自己写一封信"
]


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
    topic = random.choice(RANDOM_TOPICS)
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
        content_with_tags = f'<span style="font-size: 14px; font-weight: bold;">{result.get("content")}</span>'
        formatted_article = publisher.format_for_wechat(
            content=content_with_tags,
            title=result.get('title'),
            author="Ran先生",
            summary=result.get('digest'),
            cover_image=cover_path
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
    scheduled_time = "20:00"
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
