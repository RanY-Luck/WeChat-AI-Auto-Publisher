import argparse
import schedule
import time
import random
import os
import re
import shutil
import requests
from datetime import datetime, timedelta
from html import unescape
from io import BytesIO
from pathlib import Path
from utils.promo_generator import PromoGenerator
from utils.wechat_publisher import WeChatPublisher
from utils.bark_notifier import BarkNotifier
from utils.imgbb_uploader import ImgbbUploader
from utils.logger import setup_logger
from utils.wechat_web_publisher import WeChatWebPublisher
from config.config import Config
from PIL import Image, ImageDraw, ImageFont

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
    "Referer": "https://s.weibo.com/top/summary?cate=socialevent"
}
WEIBO_SOCIALEVENT_URL = "https://s.weibo.com/top/summary?cate=socialevent"


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


def _is_weibo_visitor_response(html_text, response_url=""):
    html_text = html_text or ""
    response_url = response_url or ""
    return (
        "passport.weibo.com/visitor/visitor" in response_url
        or "Sina Visitor System" in html_text
        or "passport.weibo.com/visitor/visitor" in html_text
    )


def _detect_chromium_executable():
    for command in ("chromium", "chromium-browser"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return None


def fetch_weibo_socialevent_html_via_browser(timeout_ms=15000, wait_after_load_ms=5000):
    runtime = None
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        runtime = sync_playwright().start()
        launch_kwargs = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        executable_path = _detect_chromium_executable()
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        browser = runtime.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.goto(WEIBO_SOCIALEVENT_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(wait_after_load_ms)
        return page.content()
    except Exception as e:
        logger.warning(f"微博社会事件浏览器抓取失败: {e}")
        return ""
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if runtime is not None:
            try:
                runtime.stop()
            except Exception:
                pass


def extract_hot_topic_cover_url(item):
    """从热点对象里提取可直接使用的封面图 URL。"""
    if not isinstance(item, dict):
        return None

    candidate_keys = [
        "cover_image_url",
        "cover",
        "image_url",
        "image",
        "pic_url",
        "pic",
        "thumbnail_url",
        "thumbnail",
        "large_url",
        "large",
    ]

    for key in candidate_keys:
        candidate = (item.get(key) or "").strip()
        if not candidate:
            continue
        if "moter/flags" in candidate or "flags/" in candidate:
            continue
        return candidate

    icon_url = (item.get("icon") or "").strip()
    icon_width = _safe_int(item.get("icon_width"), default=0, minimum=0)
    icon_height = _safe_int(item.get("icon_height"), default=0, minimum=0)
    if (
        icon_url
        and "moter/flags" not in icon_url
        and icon_width >= 200
        and icon_height >= 120
    ):
        return icon_url

    return None


def _build_topic_info(topic_text, cover_image_url=None, source="weibo"):
    topic_text = (topic_text or "").strip()
    if not topic_text:
        return None
    return {
        "title": topic_text,
        "cover_image_url": (cover_image_url or "").strip() or None,
        "source": source,
    }


def _normalize_cover_image_url(image_url):
    image_url = (image_url or "").strip()
    if image_url.startswith("//"):
        return f"https:{image_url}"
    return image_url


def build_discussion_title(topic_text):
    topic_text = re.sub(r"[!！?？,，.。:：;；、\s]+$", "", (topic_text or "").strip())
    if not topic_text:
        topic_text = "今天的关系难题"
    return f"发现中国有一个奇怪的现象：{topic_text}"


def get_hot_topic_from_weibo_hot_search():
    """获取微博社会事件话题详情，失败时返回 None。"""
    config = Config()
    topic_candidate_limit = get_topic_candidate_limit(config)

    try:
        response = requests.get(
            WEIBO_SOCIALEVENT_URL,
            headers=WEIBO_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        html_text = response.text
        if _is_weibo_visitor_response(html_text, getattr(response, "url", "")):
            logger.info("微博社会事件请求命中 visitor 页面，改用浏览器抓取")
            html_text = fetch_weibo_socialevent_html_via_browser()

        topics = extract_topics_from_weibo_html(html_text)
        topic_candidates = [
            _build_topic_info(topic_text=topic, source="weibo_html")
            for topic in topics
        ]
        topic_candidates = [item for item in topic_candidates if item][:topic_candidate_limit]

        if not topic_candidates:
            logger.warning("微博社会事件页面解析为空")
            return None

        topic_info = random.choice(topic_candidates)
        logger.info(
            f"微博社会事件页面抓取成功，候选数量: {len(topic_candidates)}，选中话题: {topic_info['title']}"
        )
        return topic_info
    except Exception as e:
        logger.warning(f"微博社会事件页面抓取失败: {e}")
        return None


def get_topic_from_weibo_hot_search():
    """兼容旧调用，仅返回热点标题。"""
    topic_info = get_hot_topic_from_weibo_hot_search()
    if not topic_info:
        return None
    return topic_info["title"]


def _get_cover_font(size):
    font_candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in font_candidates:
        if not os.path.exists(font_path):
            continue
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_cover_text(text, line_length=12, max_lines=2):
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    while text and len(chunks) < max_lines:
        chunks.append(text[:line_length])
        text = text[line_length:]
    if text and chunks:
        chunks[-1] = chunks[-1][:-1] + "…"
    return chunks


def _resize_image_to_cover(image, target_size=(900, 383)):
    src_w, src_h = image.size
    target_ratio = target_size[0] / target_size[1]
    source_ratio = src_w / max(src_h, 1)

    if source_ratio > target_ratio:
        crop_w = int(src_h * target_ratio)
        crop_x = max((src_w - crop_w) // 2, 0)
        box = (crop_x, 0, crop_x + crop_w, src_h)
    else:
        crop_h = int(src_w / target_ratio)
        crop_y = max((src_h - crop_h) // 3, 0)
        box = (0, crop_y, src_w, min(crop_y + crop_h, src_h))

    return image.crop(box).resize(target_size, Image.Resampling.LANCZOS)


def list_cover_pool_images(cover_pool_dir):
    cover_pool_dir = (cover_pool_dir or "").strip()
    if not cover_pool_dir or not os.path.isdir(cover_pool_dir):
        return []

    supported_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    images = []
    for path in sorted(Path(cover_pool_dir).iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in supported_suffixes:
            continue
        images.append(str(path))
    return images


def choose_cover_pool_image(images, random_module=None):
    random_module = random_module or random
    if not images:
        return None
    return random_module.choice(images)


def render_cover_from_pool_asset(base_image_path, title):
    try:
        image = Image.open(base_image_path).convert("RGB")
        image = _resize_image_to_cover(image, target_size=(900, 383))
        draw = ImageDraw.Draw(image)
        overlay_top = 226
        draw.rectangle((0, overlay_top, 900, 383), fill=(10, 18, 28))
        draw.rounded_rectangle((28, 26, 872, 355), radius=24, outline=(255, 255, 255), width=2)

        title_lines = _wrap_cover_text(title, line_length=14, max_lines=2)
        title_font = _get_cover_font(36)
        text_y = 246
        for line in title_lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            draw.text(
                ((900 - text_width) / 2, text_y),
                line,
                fill=(255, 255, 255),
                font=title_font,
            )
            text_y += (bbox[3] - bbox[1]) + 10

        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, f"pool_cover_{int(time.time())}.jpg")
        image.save(filepath, quality=92)
        return filepath
    except Exception as e:
        logger.error(f"素材池封面生成失败: {e}")
        return None


def resolve_cover_path_from_pool(cover_pool_dir, title, random_module=None):
    images = list_cover_pool_images(cover_pool_dir)
    chosen_image = choose_cover_pool_image(images, random_module=random_module)
    if not chosen_image:
        return None
    return render_cover_from_pool_asset(chosen_image, title=title)


def generate_default_cover(title_hint=None):
    """生成兜底封面图。"""
    try:
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        width, height = 900, 383
        base_color = (
            random.randint(30, 90),
            random.randint(90, 160),
            random.randint(140, 220),
        )
        img = Image.new("RGB", (width, height), color=base_color)
        draw = ImageDraw.Draw(img)

        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = (
                min(255, int(base_color[0] + 90 * ratio)),
                min(255, int(base_color[1] + 50 * ratio)),
                min(255, int(base_color[2] - 40 * ratio)),
            )
            draw.line((0, y, width, y), fill=color)

        draw.rounded_rectangle(
            (36, 32, width - 36, height - 32),
            radius=28,
            outline=(255, 255, 255, 80),
            width=3,
        )
        draw.rectangle((0, height - 110, width, height), fill=(12, 22, 34))

        title_lines = _wrap_cover_text(title_hint or "今日热点速览")
        if title_lines:
            title_font = _get_cover_font(44)
            line_gap = 14
            text_y = 78
            for line in title_lines:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                draw.text(
                    ((width - text_width) / 2, text_y),
                    line,
                    fill=(255, 255, 255),
                    font=title_font,
                )
                text_y += (bbox[3] - bbox[1]) + line_gap

        tag_font = _get_cover_font(22)
        draw.text((52, height - 78), "WECHAT AUTO PUBLISHER", fill=(255, 255, 255), font=tag_font)
        draw.text((52, height - 48), datetime.now().strftime("%Y-%m-%d"), fill=(184, 206, 223), font=tag_font)

        filename = f"sched_cover_{int(time.time())}.jpg"
        filepath = os.path.join(temp_dir, filename)
        img.save(filepath, quality=92)
        return filepath
    except Exception as e:
        logger.error(f"封面生成失败: {e}")
        return None


def download_cover_image(image_url, title_hint=None):
    """下载热点封面图并裁剪到微信封面比例。"""
    image_url = _normalize_cover_image_url(image_url)
    if not image_url:
        return None

    try:
        response = requests.get(
            image_url,
            headers={"User-Agent": WEIBO_HEADERS["User-Agent"]},
            timeout=15,
        )
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
        image = _resize_image_to_cover(image, target_size=(900, 383))
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"topic_cover_{int(time.time())}.jpg"
        filepath = os.path.join(temp_dir, filename)
        image.save(filepath, quality=92)
        logger.info(f"热点封面下载成功: {title_hint or image_url}")
        return filepath
    except Exception as e:
        logger.warning(f"热点封面下载失败: {e}")
        return None


def resolve_cover_path(topic_info=None, title_hint=None):
    topic_info = topic_info or {}
    cover_url = _normalize_cover_image_url(topic_info.get("cover_image_url"))
    topic_title = (topic_info.get("title") or "").strip()

    if cover_url:
        cover_path = download_cover_image(cover_url, title_hint=topic_title or title_hint)
        if cover_path:
            return cover_path
        logger.info("热点封面不可用，回退本地封面")

    return generate_default_cover(title_hint or topic_title)


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


def _resolve_random_daily_run_bounds(daily_random_runs_min=None, daily_random_runs_max=None):
    min_runs = _safe_int(daily_random_runs_min, default=1, minimum=1)
    max_runs = _safe_int(daily_random_runs_max, default=min_runs, minimum=1)
    max_runs = max(max_runs, min_runs)
    return min_runs, max_runs


def generate_random_daily_times(
    daily_random_runs_min=None,
    daily_random_runs_max=None,
    random_module=None,
):
    random_module = random_module or random
    min_runs, max_runs = _resolve_random_daily_run_bounds(
        daily_random_runs_min=daily_random_runs_min,
        daily_random_runs_max=daily_random_runs_max,
    )
    run_count = random_module.randint(min_runs, max_runs)
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


def _clear_login_wait_state(state):
    wait_session = state.get("login_wait_session") or {}
    web_publisher = wait_session.get("web_publisher")
    if web_publisher is not None:
        try:
            web_publisher.close()
        except Exception as close_error:
            logger.warning(f"关闭等待登录浏览器失败: {close_error}")
    state["waiting_for_login"] = False
    state["login_wait_session"] = None


def ensure_logged_in_or_start_wait(
    state,
    config=None,
    notifier=None,
    web_publisher_factory=None,
    uploader_factory=None,
):
    config = config or Config()
    notifier = notifier or BarkNotifier()
    web_publisher_factory = web_publisher_factory or create_web_publisher
    uploader_factory = uploader_factory or create_imgbb_uploader

    wait_session = state.get("login_wait_session")
    if wait_session:
        web_publisher = wait_session["web_publisher"]
        page = wait_session["page"]
        if web_publisher.is_logged_in(page):
            logger.info("检测到公众号已登录，结束等待状态")
            _clear_login_wait_state(state)
            return True
        return None

    web_publisher = web_publisher_factory(config)
    uploader = uploader_factory(config)
    try:
        context = web_publisher.launch_persistent_context()
        page = _resolve_page(context)
        _open_login_page(page, web_publisher)

        if web_publisher.is_logged_in(page):
            web_publisher.close()
            return True

        _notify_login_required(
            config=config,
            notifier=notifier,
            web_publisher=web_publisher,
            page=page,
            uploader=uploader,
        )
        state["waiting_for_login"] = True
        state["login_wait_session"] = {
            "web_publisher": web_publisher,
            "page": page,
        }
        logger.info("公众号未登录，当前随机任务进入等待登录状态")
        return None
    except Exception as e:
        if _is_profile_in_use_error(e):
            logger.warning(f"等待登录时检测到浏览器 profile 占用: {e}")
            return _notify_profile_in_use(config, notifier, "等待登录")
        logger.error(f"等待登录任务异常: {e}")
        notifier.send(title="微信登录等待异常", content=f"错误: {e}")
        try:
            web_publisher.close()
        except Exception:
            pass
        return False


def refresh_random_daily_plan(
    state,
    scheduler_module,
    draft_job_callable,
    daily_random_runs_max,
    daily_random_runs_min=None,
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
        daily_random_runs_min=daily_random_runs_min,
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
    publish_config = getattr(config, "PUBLISH_CONFIG", {}) or {}
    topic_info = get_hot_topic_from_weibo_hot_search()
    if not topic_info:
        topic_info = _build_topic_info(
            topic_text=random.choice(RANDOM_TOPICS),
            source="fallback_random",
        )
        logger.info(f"微博社会事件不可用，回退到预设主题: {topic_info['title']}")

    topic = topic_info["title"]

    logger.info(f"开始执行定时任务，本次主题: {topic}")

    notifier = BarkNotifier()
    cover_path = None

    try:
        # 1. 生成文案
        generator = PromoGenerator()
        result = generator.generate_promo(topic)

        if not result:
            logger.error("文案生成失败")
            notifier.send(title="定时任务失败", content="文案生成失败，请检查日志")
            return False

        final_title = result.get("title")
        if publish_config.get("discussion_title_enabled"):
            final_title = build_discussion_title(topic)

        logger.info(f"文案生成成功: {final_title}")

        # 2. 准备发布
        publisher = WeChatPublisher()
        cover_pool_dir = (publish_config.get("discussion_cover_pool_dir") or "").strip()
        if cover_pool_dir:
            cover_path = resolve_cover_path_from_pool(
                cover_pool_dir,
                title=final_title or topic,
            )
        else:
            cover_path = resolve_cover_path(
                topic_info=topic_info,
                title_hint=final_title or topic,
            )

        if not cover_path:
            logger.error("封面生成失败")
            notifier.send(title="定时任务失败", content="封面生成失败，请检查素材池或日志")
            return False

        # 3. 格式化
        article_template = (publish_config.get("article_template") or "").strip()
        content = result.get("content", "")
        if article_template:
            content_for_publish = content
        else:
            content_for_publish = f'<span style="font-size: 14px; font-weight: bold;">{content}</span>'

        formatted_article = publisher.format_for_wechat(
            content=content_for_publish,
            title=final_title,
            author="Ran先生",
            summary=result.get('digest'),
            cover_image=cover_path,
            template_name=article_template,
        )

        # 4. 发布到草稿箱
        publish_result = publisher.publish_article(formatted_article, draft=True)

        success = bool(publish_result)
        if success:
            msg = f"定时发布成功! Media ID: {publish_result.get('media_id')}"
            logger.info(msg)
            notifier.send(title="定时发布成功", content=f"主题: {topic}\n标题: {final_title}")
        else:
            msg = "定时发布失败"
            logger.error(msg)
            notifier.send(title="定时发布失败", content=f"主题: {topic}\n请检查日志")

        return success

    except Exception as e:
        logger.error(f"定时任务执行异常: {e}")
        notifier.send(title="定时任务异常", content=f"错误: {str(e)}")
        return False
    finally:
        if cover_path and os.path.exists(cover_path):
            try:
                os.remove(cover_path)
            except OSError as cleanup_error:
                logger.warning(f"清理封面文件失败: {cleanup_error}")


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

        def execute_random_full_workflow(notifier):
            draft_success = draft_job_callable()
            if not draft_success:
                return False
            if not publish_config.get("enable_web_publish"):
                return True
            return publish_latest_draft_job_callable(
                config=config,
                notifier=notifier,
                web_publisher_factory=web_publisher_factory,
                uploader_factory=uploader_factory,
            )

        def run_random_full_workflow():
            if random_schedule_state.get("waiting_for_login"):
                logger.info("随机任务到达，但当前仍在等待登录，跳过本次任务")
                return False

            notifier = notifier_factory() if notifier_factory else BarkNotifier()
            if publish_config.get("enable_web_publish"):
                login_ready = ensure_logged_in_or_start_wait(
                    state=random_schedule_state,
                    config=config,
                    notifier=notifier,
                    web_publisher_factory=web_publisher_factory,
                    uploader_factory=uploader_factory,
                )
                if login_ready is not True:
                    return False

            return execute_random_full_workflow(notifier)

        def resume_waiting_random_full_workflow():
            if not random_schedule_state.get("waiting_for_login"):
                return None

            notifier = notifier_factory() if notifier_factory else BarkNotifier()
            login_ready = ensure_logged_in_or_start_wait(
                state=random_schedule_state,
                config=config,
                notifier=notifier,
                web_publisher_factory=web_publisher_factory,
                uploader_factory=uploader_factory,
            )
            if login_ready is True:
                logger.info("检测到公众号已登录，继续执行挂起的随机任务")
                return execute_random_full_workflow(notifier)
            return False

        refresh_random_daily_plan(
            state=random_schedule_state,
            scheduler_module=scheduler_module,
            draft_job_callable=run_random_full_workflow,
            daily_random_runs_min=publish_config.get("daily_random_runs_min"),
            daily_random_runs_max=publish_config.get("daily_random_runs_max"),
            now_provider=now_provider,
            random_module=random_module,
        )

        def ensure_random_daily_plan():
            return refresh_random_daily_plan(
                state=random_schedule_state,
                scheduler_module=scheduler_module,
                draft_job_callable=run_random_full_workflow,
                daily_random_runs_min=publish_config.get("daily_random_runs_min"),
                daily_random_runs_max=publish_config.get("daily_random_runs_max"),
                now_provider=now_provider,
                random_module=random_module,
            )

        scheduler_module.every(1).minutes.do(resume_waiting_random_full_workflow)
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
            f"发帖机器人已启动！今天随机计划执行 {len(target_times)} 次: "
            f"{', '.join(target_times) or '今天无剩余时段'}"
        )
        if schedule_info["web_publish_enabled"]:
            logger.info("微信 UI 发布已启用，随机模式下每次任务生成草稿后会立即尝试自动发布。")
    else:
        logger.info(f"发帖机器人已启动！将在每天 {target_time} 自动生成并保存草稿。")
    if schedule_info["web_publish_enabled"] and schedule_info.get("schedule_mode") != "random_daily":
        logger.info(
            f"微信 UI 发布已启用，登录预检查时间: {schedule_info['precheck_time']}，"
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

