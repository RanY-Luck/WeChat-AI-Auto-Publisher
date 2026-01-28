import argparse
import sys
import os
import time
import random
import datetime
from utils.promo_generator import PromoGenerator
from utils.wechat_publisher import WeChatPublisher
from utils.bark_notifier import BarkNotifier
from config.config import Config
from utils.logger import setup_logger

logger = setup_logger("generate_promo_cli")

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from PIL import Image, ImageDraw
except ImportError:
    logger.warning("Warning: PIL (Pillow) not installed. Cover image generation may fail.")


def generate_default_cover():
    """生成默认封面图片（纯色背景）"""
    try:
        # 创建临时目录
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)

        width, height = 900, 383
        # 随机颜色
        color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
        img = Image.new('RGB', (width, height), color=color)

        filename = f"promo_cover_{int(time.time())}.jpg"
        filepath = os.path.join(temp_dir, filename)
        img.save(filepath)
        return filepath
    except Exception as e:
        logger.error(f"封面生成失败: {e}")
        return None


def wait_for_schedule(target_time_str):
    """
    等待直到指定时间
    :param target_time_str: "HH:MM" 格式的时间字符串
    """
    try:
        now = datetime.datetime.now()
        target_time = datetime.datetime.strptime(target_time_str, "%H:%M").time()
        
        target_datetime = datetime.datetime.combine(now.date(), target_time)
        
        # 如果目标时间已过，推迟到明天
        if now.time() > target_time:
            target_datetime += datetime.timedelta(days=1)
            
        wait_seconds = (target_datetime - now).total_seconds()
        
        logger.info(f"⏰ 已开启定时发布，将在 {target_datetime.strftime('%Y-%m-%d %H:%M:%S')} 发布")
        logger.info(f"⏳ 需等待约 {int(wait_seconds / 60)} 分钟...")
        
        # 倒计时循环
        while wait_seconds > 0:
            # 每一小时或更短时间打印一次状态
            sleep_interval = min(wait_seconds, 60) # 每分钟检查一次
            time.sleep(sleep_interval)
            
            # 重新计算剩余时间
            now = datetime.datetime.now()
            wait_seconds = (target_datetime - now).total_seconds()
            
            if wait_seconds > 60:
                 # 只有剩余超过1分钟才打印，避免刷屏
                 pass
                 
        logger.info("⚡ 时间到！开始发布...")
        return True
        
    except ValueError:
        logger.error("❌ 时间格式错误，请使用 HH:MM 格式 (例如 20:00)")
        return False


def main():
    config = Config()
    notifier = BarkNotifier()
    
    parser = argparse.ArgumentParser(description="AI 情感文案生成器")
    parser.add_argument("text", nargs="?", help="输入主题、草稿或描述 (如果不填且使用 -r，则随机生成)")
    parser.add_argument("-p", "--publish", action="store_true", help="直接发布到微信公众号草稿箱")
    parser.add_argument("-t", "--time", help="定时发布时间 (HH:MM)，例如 20:00")
    parser.add_argument("-r", "--random", action="store_true", help="随机生成一个情感/成长类主题")
    
    args = parser.parse_args()

    # 预设的随机主题库
    random_topics = [
        "深夜加班后的街头感悟", "一个人看电影的孤独与享受", "在此刻，想念一个很久不见的人",
        "二十岁时的梦想，现在还在坚持吗", "职场中那些瞬间长大的时刻", "在大城市漂泊的归属感",
        "旅行中遇到的陌生人善意", "读完一本书后的灵魂触动", "不得不说的再见：离别的意义",
        "关于自律：是自由还是束缚", "那些被我们忽略的微小幸福", "在这个快节奏时代慢下来",
        "成长的代价：我们通过失去学会珍惜", "独处，是成年人最好的奢侈品", "给未来的自己写一封信"
    ]

    selected_topic = args.text
    
    if args.random:
        selected_topic = random.choice(random_topics)
        logger.info(f"🎲 已随机选择主题: 【{selected_topic}】")
    
    if not selected_topic:
        # 如果既没填文字，也没加 -r，提示错误
        logger.error("错误: 请输入文本内容，或使用 -r 参数随机生成")
        logger.info("示例: python generate_promo.py -r")
        sys.exit(1)

    logger.info(f"正在为 '{selected_topic}' 生成文案，请稍候...")

    generator = PromoGenerator()
    result = generator.generate_promo(selected_topic)

    if result:
        logger.info("=" * 40)
        logger.info(f"🔥 标题: {result.get('title')}")
        logger.info("-" * 40)
        logger.info(f"🏷️  标签: {result.get('tags')}")
        logger.info("-" * 40)
        logger.info(f"📝 内容:\n{result.get('content')}")
        logger.info("=" * 40)

        if args.publish:
            # 检查是否有定时设置
            publish_time = args.time
            
            # 如果命令行没指定，检查配置文件的默认设置
            if not publish_time and config.PUBLISH_CONFIG.get("enable_schedule"):
                publish_time = config.PUBLISH_CONFIG.get("target_time")
                
            if publish_time:
                # 进入定时等待模式
                if not wait_for_schedule(publish_time):
                    logger.error("❌ 定时设置无效，取消发布")
                    return

            logger.info("正在发布到微信公众号...")
            try:
                publisher = WeChatPublisher()

                # 1. 准备封面图 (必填)
                cover_path = generate_default_cover()
                if not cover_path:
                    logger.error("❌ 无法生成封面图，取消发布。")
                    return

                # 2. 格式化文章
                # 组合内容和标签
                # content_with_tags = f"{result.get('content')}"
                # 用户要求：字号 14px，加粗
                content_with_tags = f'<span style="font-size: 14px; font-weight: bold;">{result.get("content")}</span>'

                formatted_article = publisher.format_for_wechat(
                    content=content_with_tags,
                    title=result.get('title'),
                    author="Ran先生",
                    summary=result.get('digest'),  # 使用AI生成的专用摘要
                    cover_image=cover_path
                )

                # 3. 发布
                publish_result = publisher.publish_article(formatted_article, draft=True)

                if publish_result:
                    msg = f"✅ 发布成功! Media ID: {publish_result.get('media_id')}"
                    logger.info(msg)
                    notifier.send(title="公众号发布成功", content=f"标题: {result.get('title')}")
                else:
                    msg = "❌ 发布失败，请检查日志"
                    logger.error(msg)
                    notifier.send(title="公众号发布失败", content=f"标题: {result.get('title')}")

                # 清理封面
                if os.path.exists(cover_path):
                    os.remove(cover_path)

            except Exception as e:
                logger.error(f"❌ 发布过程中出错: {e}")
                notifier.send(title="公众号发布异常", content=f"错误信息: {str(e)}")
        else:
             # 仅生成不发布，也发个通知知会一声
             notifier.send(title="文案生成完成", content=f"标题: {result.get('title')}\n(未执行发布操作)")
             
    else:
        logger.error("❌ 生成失败，请查看日志。")
        notifier.send(title="文案生成失败", content="请检查日志文件")

if __name__ == "__main__":
    main()
