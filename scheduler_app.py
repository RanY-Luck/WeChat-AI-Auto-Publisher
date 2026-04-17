import argparse
import schedule
import time
import random
import os
import re
import requests
from datetime import datetime, timedelta
from html import unescape
from utils.promo_generator import PromoGenerator
from utils.wechat_publisher import WeChatPublisher
from utils.bark_notifier import BarkNotifier
from utils.imgbb_uploader import ImgbbUploader
from utils.logger import setup_logger
from utils.wechat_web_publisher import WeChatWebPublisher
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


def get_topic_candidate_limit(config):
    publish_config = getattr(config, "PUBLISH_CONFIG", {}) or {}
    topic_candidate_limit = _safe_int(
        publish_config.get("hot_topic_candidate_limit"),
        default=3,
        minimum=1,
    )
    return topic_candidate_limit


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
    config = Config()
    topic_candidate_limit = get_topic_candidate_limit(config)

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

        topics = topics[:topic_candidate_limit]

        if topics:
            topic = random.choice(topics)
            logger.info(f"微博热搜接口获取成功，候选数量: {len(topics)}，选中话题: {topic}")
            return topic

        logger.warning("微博热搜接口返回为空，尝试页面抓取")
    except Exception as e:
        logger.warning(f"微博热搜接口获取失败: {e}，尝试页面抓取")

    try:
        response = requests.get(
            "https://s.weibo.com/top/summary?cate=entrank",
            headers=WEIBO_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        topics = extract_topics_from_weibo_html(response.text)
        topics = topics[:topic_candidate_limit]

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


def compute_precheck_time(publish_time, hours_before):
    # Daily schedule contract: if subtraction crosses midnight, return previous-day wall clock (e.g. 01:00 - 2h => 23:00).
    publish_datetime = datetime.strptime(publish_time, "%H:%M")
    precheck_datetime = publish_datetime - timedelta(hours=hours_before)
    return precheck_datetime.strftime("%H:%M")


def create_web_publisher(config):
    web_config = getattr(config, "WEB_PUBLISH_CONFIG", {}) or {}
    return WeChatWebPublisher(
        profile_dir=web_config.get("browser_profile_dir", "/data/wechat-profile"),
        headless=web_config.get("headless", False),
        force_release_profile=web_config.get("force_release_profile"),
    )


def create_imgbb_uploader(config):
    api_key = (getattr(config, "IMGBB_API_KEY", "") or "").strip()
    if not api_key:
        return None
    expiration = getattr(config, "IMGBB_EXPIRATION", 600)
    return ImgbbUploader(api_key=api_key, expiration=expiration)


def _resolve_page(context):
    pages = getattr(context, "pages", None)
    if pages:
        return pages[0]
    if hasattr(context, "new_page"):
        return context.new_page()
    raise RuntimeError("无法从浏览器上下文获取页面对象")


def _novnc_hint(config):
    web_config = getattr(config, "WEB_PUBLISH_CONFIG", {}) or {}
    novnc_port = web_config.get("novnc_port", 6080)
    return f"请打开 noVNC 完成登录: http://<server-ip>:{novnc_port}/vnc.html"


def send_qr_debug_notification(image_url, notifier=None):
    notifier = notifier or BarkNotifier()
    return notifier.send_image(
        title="微信扫码登录",
        image_url=image_url,
    )


def _open_login_page(page, web_publisher):
    base_url = getattr(web_publisher, "base_url", "https://mp.weixin.qq.com")
    timeout_ms = getattr(web_publisher, "timeout_ms", 15000)
    page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)


def _safe_int(value, default, minimum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _minute_to_hhmm(minute_of_day):
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def generate_random_daily_times(daily_random_runs_max, random_module=None):
    random_module = random_module or random
    max_runs = _safe_int(daily_random_runs_max, default=1, minimum=1)
    run_count = random_module.randint(1, max_runs)
    minutes = sorted(random_module.sample(range(24 * 60), run_count))
    return [_minute_to_hhmm(minute_of_day) for minute_of_day in minutes]


def filter_future_times_for_today(plan_date, times, now=None):
    now = now or datetime.now()
    if plan_date != now.date():
        return list(times)
    current_time = now.strftime("%H:%M")
    return [time_text for time_text in times if time_text > current_time]


def _cancel_scheduled_job(scheduler_module, job_ref):
    if job_ref is None:
        return
    cancel_job = getattr(scheduler_module, "cancel_job", None)
    if callable(cancel_job):
        cancel_job(job_ref)
        return
    if hasattr(job_ref, "cancel"):
        job_ref.cancel()


def register_random_daily_jobs(scheduler_module, times, draft_job_callable):
    registered_jobs = []
    for target_time in times:
        job_ref = scheduler_module.every().day.at(target_time).do(draft_job_callable)
        registered_jobs.append(job_ref)
    return registered_jobs


def refresh_random_daily_plan(
    state,
    scheduler_module,
    draft_job_callable,
    daily_random_runs_max,
    now_provider=None,
    random_module=None,
):
    now_provider = now_provider or datetime.now
    now = now_provider()
    current_date = now.date()

    if state.get("plan_date") == current_date:
        return state

    for job_ref in state.get("registered_job_refs", []):
        _cancel_scheduled_job(scheduler_module, job_ref)

    generated_times = generate_random_daily_times(
        daily_random_runs_max=daily_random_runs_max,
        random_module=random_module,
    )
    target_times = filter_future_times_for_today(
        plan_date=current_date,
        times=generated_times,
        now=now,
    )
    registered_job_refs = register_random_daily_jobs(
        scheduler_module=scheduler_module,
        times=target_times,
        draft_job_callable=draft_job_callable,
    )
    state["plan_date"] = current_date
    state["times"] = target_times
    state["registered_job_refs"] = registered_job_refs
    logger.info(f"随机日计划已刷新 {current_date}: {', '.join(target_times) or '今天无剩余时段'}")
    return state


def _is_profile_in_use_error(error):
    error_text = str(error or "")
    return "ProcessSingleton" in error_text or "profile directory" in error_text


def _notify_profile_in_use(config, notifier, action_text):
    notifier.send(
        title="微信登录窗口占用中",
        content=(
            f"检测到公众号登录页已打开，当前先不执行{action_text}。"
            f"请扫码完成登录并关闭登录窗口后重试。{_novnc_hint(config)}"
        ),
    )
    return False


def login_precheck_job(
    config=None,
    notifier=None,
    web_publisher=None,
    uploader=None,
    web_publisher_factory=None,
    uploader_factory=None,
):
    config = config or Config()
    notifier = notifier or BarkNotifier()
    web_publisher_factory = web_publisher_factory or create_web_publisher
    uploader_factory = uploader_factory or create_imgbb_uploader
    web_publisher = web_publisher or web_publisher_factory(config)
    uploader = uploader if uploader is not None else uploader_factory(config)

    try:
        context = web_publisher.launch_persistent_context()
        page = _resolve_page(context)
        _open_login_page(page, web_publisher)

        if web_publisher.is_logged_in(page):
            logger.info("登录预检查通过，当前已登录微信公众平台")
            return True

        _notify_login_required(
            config=config,
            notifier=notifier,
            web_publisher=web_publisher,
            page=page,
            uploader=uploader,
        )
        return False
    except Exception as e:
        if _is_profile_in_use_error(e):
            logger.warning(f"登录预检查检测到浏览器 profile 占用: {e}")
            return _notify_profile_in_use(config, notifier, "登录预检查")
        logger.error(f"登录预检查任务异常: {e}")
        notifier.send(title="微信登录预检查异常", content=f"错误: {e}")
        return False
    finally:
        try:
            web_publisher.close()
        except Exception as close_error:
            logger.warning(f"登录预检查关闭浏览器失败: {close_error}")


def publish_latest_draft_job(
    config=None,
    notifier=None,
    web_publisher=None,
    uploader=None,
    web_publisher_factory=None,
    uploader_factory=None,
):
    config = config or Config()
    notifier = notifier or BarkNotifier()
    web_publisher_factory = web_publisher_factory or create_web_publisher
    uploader_factory = uploader_factory or create_imgbb_uploader
    web_publisher = web_publisher or web_publisher_factory(config)
    uploader = uploader if uploader is not None else uploader_factory(config)
    publish_config = getattr(config, "PUBLISH_CONFIG", {}) or {}
    max_retries = _safe_int(publish_config.get("max_publish_retries"), default=3, minimum=1)

    try:
        context = web_publisher.launch_persistent_context()
        page = _resolve_page(context)
        _open_login_page(page, web_publisher)

        if not web_publisher.is_logged_in(page):
            _notify_login_required(
                config=config,
                notifier=notifier,
                web_publisher=web_publisher,
                page=page,
                uploader=uploader,
            )
            return False

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                web_publisher.publish_latest_draft(page)
                notifier.send(title="微信发布成功", content=f"草稿已成功发布（第 {attempt} 次尝试）")
                return True
            except Exception as publish_error:
                last_error = publish_error
                logger.warning(f"UI 发布第 {attempt}/{max_retries} 次失败: {publish_error}")

        notifier.send(
            title="微信发布失败",
            content=f"草稿发布失败，已重试 {max_retries} 次。最后错误: {last_error}",
        )
        return False
    except Exception as e:
        if _is_profile_in_use_error(e):
            logger.warning(f"发布任务检测到浏览器 profile 占用: {e}")
            return _notify_profile_in_use(config, notifier, "自动发布")
        logger.error(f"发布草稿任务异常: {e}")
        notifier.send(title="微信发布异常", content=f"错误: {e}")
        return False
    finally:
        try:
            web_publisher.close()
        except Exception as close_error:
            logger.warning(f"发布任务关闭浏览器失败: {close_error}")


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
            return False

        logger.info(f"文案生成成功: {result.get('title')}")

        # 2. 准备发布
        publisher = WeChatPublisher()
        cover_path = generate_default_cover()

        if not cover_path:
            logger.error("封面生成失败")
            return False

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

        success = bool(publish_result)
        if success:
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
        return success

    except Exception as e:
        logger.error(f"定时任务执行异常: {e}")
        notifier.send(title="定时任务异常", content=f"错误: {str(e)}")
        return False


def _notify_login_required(config, notifier, web_publisher, page, uploader=None):
    try:
        screenshot_path = web_publisher.save_login_qr_screenshot(page, prefix="login-qr")
    except Exception as qr_error:
        logger.warning(f"登录二维码截图失败，回退整页截图: {qr_error}")
        screenshot_path = web_publisher.save_failure_screenshot(page, prefix="login-precheck")

    uploaded_url = None
    if uploader is not None:
        try:
            uploaded_url = uploader.upload(screenshot_path)
        except Exception as upload_error:
            logger.warning(f"登录预检查截图上传失败: {upload_error}")

    if uploaded_url:
        notifier.send_image(
            title="微信扫码登录",
            image_url=uploaded_url,
        )
        return False

    notifier.send(
        title="微信登录预检查提醒",
        content=f"检测到公众号后台未登录。{_novnc_hint(config)}",
    )
    return False


def run_startup_login_precheck(
    config=None,
    notifier_factory=None,
    login_precheck_job_callable=None,
    web_publisher_factory=None,
    uploader_factory=None,
):
    config = config or Config()
    publish_config = getattr(config, "PUBLISH_CONFIG", {}) or {}
    if not publish_config.get("enable_web_publish"):
        return None
    if os.environ.get("AUTO_OPEN_BROWSER", "").lower() == "true":
        logger.info("AUTO_OPEN_BROWSER=true，跳过启动阶段登录预检查，避免浏览器 profile 冲突")
        return None

    notifier = notifier_factory() if notifier_factory else None
    login_precheck_job_callable = login_precheck_job_callable or login_precheck_job
    return login_precheck_job_callable(
        config=config,
        notifier=notifier,
        web_publisher_factory=web_publisher_factory,
        uploader_factory=uploader_factory,
    )


def schedule_jobs(
    config=None,
    scheduler_module=schedule,
    draft_job_callable=None,
    login_precheck_job_callable=None,
    publish_latest_draft_job_callable=None,
    notifier_factory=None,
    web_publisher_factory=None,
    uploader_factory=None,
    now_provider=None,
    random_module=None,
):
    config = config or Config()
    publish_config = config.PUBLISH_CONFIG or {}
    draft_job_callable = draft_job_callable or job
    login_precheck_job_callable = login_precheck_job_callable or login_precheck_job
    publish_latest_draft_job_callable = (
        publish_latest_draft_job_callable or publish_latest_draft_job
    )
    now_provider = now_provider or datetime.now

    if publish_config.get("random_daily_schedule_enabled"):
        random_schedule_state = {}

        def run_random_full_workflow():
            draft_success = draft_job_callable()
            if not draft_success:
                return False
            if not publish_config.get("enable_web_publish"):
                return True
            notifier = notifier_factory() if notifier_factory else None
            return publish_latest_draft_job_callable(
                config=config,
                notifier=notifier,
                web_publisher_factory=web_publisher_factory,
                uploader_factory=uploader_factory,
            )

        refresh_random_daily_plan(
            state=random_schedule_state,
            scheduler_module=scheduler_module,
            draft_job_callable=run_random_full_workflow,
            daily_random_runs_max=publish_config.get("daily_random_runs_max"),
            now_provider=now_provider,
            random_module=random_module,
        )

        def ensure_random_daily_plan():
            return refresh_random_daily_plan(
                state=random_schedule_state,
                scheduler_module=scheduler_module,
                draft_job_callable=run_random_full_workflow,
                daily_random_runs_max=publish_config.get("daily_random_runs_max"),
                now_provider=now_provider,
                random_module=random_module,
            )

        scheduler_module.every(10).minutes.do(ensure_random_daily_plan)
        return {
            "schedule_mode": "random_daily",
            "target_time": None,
            "target_times": random_schedule_state.get("times", []),
            "web_publish_enabled": bool(publish_config.get("enable_web_publish")),
            "publish_time": None,
            "precheck_time": None,
        }

    target_time = (publish_config.get("target_time") or "14:30").strip()
    scheduler_module.every().day.at(target_time).do(draft_job_callable)

    schedule_info = {
        "schedule_mode": "fixed",
        "target_time": target_time,
        "target_times": [target_time],
        "web_publish_enabled": bool(publish_config.get("enable_web_publish")),
        "publish_time": None,
        "precheck_time": None,
    }

    if publish_config.get("enable_web_publish"):
        publish_time = (publish_config.get("publish_time") or target_time).strip()
        login_check_hours_before = _safe_int(
            publish_config.get("login_check_hours_before"),
            default=2,
            minimum=0,
        )
        precheck_time = compute_precheck_time(publish_time, login_check_hours_before)

        def run_login_precheck():
            notifier = notifier_factory() if notifier_factory else None
            return login_precheck_job_callable(
                config=config,
                notifier=notifier,
                web_publisher_factory=web_publisher_factory,
                uploader_factory=uploader_factory,
            )

        def run_publish_latest_draft():
            notifier = notifier_factory() if notifier_factory else None
            return publish_latest_draft_job_callable(
                config=config,
                notifier=notifier,
                web_publisher_factory=web_publisher_factory,
                uploader_factory=uploader_factory,
            )

        scheduler_module.every().day.at(precheck_time).do(run_login_precheck)
        scheduler_module.every().day.at(publish_time).do(run_publish_latest_draft)

        schedule_info["publish_time"] = publish_time
        schedule_info["precheck_time"] = precheck_time

    return schedule_info


def main(argv=None):
    parser = argparse.ArgumentParser(description="微信公众号自动发布调度器")
    parser.add_argument(
        "--debug-bark-icon-url",
        dest="debug_bark_icon_url",
        help="立即发送一条只带 Bark icon 的扫码通知，用于调试手表/手机展示效果",
    )
    args = parser.parse_args(argv)

    if args.debug_bark_icon_url:
        send_qr_debug_notification(image_url=args.debug_bark_icon_url)
        return 0

    config = Config()
    schedule_info = schedule_jobs(config=config)
    target_time = schedule_info["target_time"]

    if schedule_info.get("schedule_mode") == "random_daily":
        target_times = schedule_info.get("target_times", [])
        logger.info(
            f"🚀 发帖机器人已启动！今天随机计划执行 {len(target_times)} 次: "
            f"{', '.join(target_times) or '今天无剩余时段'}"
        )
        if schedule_info["web_publish_enabled"]:
            logger.info("🌐 微信 UI 发布已启用，随机模式下每次任务生成草稿后会立即尝试自动发布。")
    else:
        logger.info(f"🚀 发帖机器人已启动！将在每天 {target_time} 自动生成并保存草稿。")
    if schedule_info["web_publish_enabled"] and schedule_info.get("schedule_mode") != "random_daily":
        logger.info(
            f"🌐 微信 UI 发布已启用，登录预检查时间: {schedule_info['precheck_time']}，"
            f"发布时间: {schedule_info['publish_time']}"
        )
    logger.info("正在等待时间到达... (按 Ctrl+C 退出)")

    # 启动时先发个 Bark 确认存活
    if schedule_info.get("schedule_mode") == "random_daily":
        BarkNotifier().send(
            title="服务启动",
            content=(
                "自动发文服务已在服务器启动\n"
                f"今天随机计划: {', '.join(schedule_info.get('target_times', [])) or '今天无剩余时段'}"
            ),
        )
    else:
        BarkNotifier().send(title="服务启动", content=f"自动发文服务已在服务器启动\n每天 {target_time} 生成草稿")
    run_startup_login_precheck(config=config)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
