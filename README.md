# WeChat AI Auto-Publisher (微信公众号 AI 自动化发布工具)

这是一个基于 Python 的微信公众号自动化运营工具集，集成 **阿里云百炼 (DashScope/Qwen)** 大模型能力，支持 AI 情感文案生成、自动排版、一键发布草稿以及本地定时发布功能。

## ✨ 主要功能

### 1. ✍️ AI 情感文案生成器 (`generate_promo.py`)
输入一个简单的灵感或主题（如“深夜加班”），AI 会自动为您创作：
- **爆款标题**：格式固定为 `远方岛屿 {关键词} | {唯美副标题}`。
- **热门话题**：自动生成 8+ 个带 `#` 前缀的标签。
- **情感导语**：约 150 字的走心文案，已预设排版（14px, 加粗）。
- **自动配图**：自动生成纯色封面图（满足微信发布要求）。
- **自动发布**：一键同步到微信公众号后台“草稿箱”。
- **定时发布**：支持设置本地倒计时，自动在指定时间提交。

- **自动发布**：一键同步到微信公众号后台“草稿箱”。
- **定时发布**：支持设置本地倒计时，自动在指定时间提交。

---

## 🛠️ 环境配置

### 1. 安装依赖
请确保安装了以下 Python 库：
```bash
pip install requests dashscope beautifulsoup4 pillow
```

### 2. 配置文件 (`config/config.py`)
请在 `config/config.py` 中填入您的 API 密钥和公众号信息：

```python
# 阿里云百炼 (DashScope) 配置
DASHSCOPE_API_KEY = "sk-xxxxxxxx"  # 您的阿里云 API Key
DASHSCOPE_MODEL = "qwen-plus"      # 模型选择 (推荐 qwen-plus)

# 微信公众号配置
WECHAT_CONFIG = {
    "app_id": "wx********",        # 您的公众号 AppID
    "app_secret": "xxxxxxxx"       # 您的公众号 AppSecret
}

# 发布配置
PUBLISH_CONFIG = {
    "enable_schedule": True,       # 是否启用定时发布功能
    "target_time": "20:00",        # 默认自动发布时间
    "timezone": 8
}
```

---

## 🚀 使用指南

### 场景一：不想写文案，只想给个主题让 AI 帮我写并发布

**基本用法（生成文案预览）：**
```bash
python generate_promo.py "深夜加班的感悟"
```

**一键生成并发布到草稿箱：**
```bash
python generate_promo.py "深夜加班的感悟" -p
```
*程序会自动生成封面、排版内容，并上传到微信后台。*

**指定时间定时发布（例如今晚 22:30）：**
```bash
python generate_promo.py "深夜加班的感悟" -p -t 22:30
```
*程序会进入倒计时模式，保持运行，直到指定时间自动提交。*

### 场景三：🌟 随机灵感（抽盲盒）

**不知写什么？让 AI 随机选一个情感/成长主题：**
```bash
python generate_promo.py -r
```

**随机生成并直接发布：**
```bash
python generate_promo.py -r -p
```
*内置 15+ 个治愈系主题，一键生成情感大片。*

---

## 🐳 服务器/Docker 部署

如果您想让程序在服务器上**每天晚上 20:00 自动发文**，请使用 `scheduler_app.py` 或 Docker 部署。

### 1. 直接运行 (Linux/Windows 服务器)
```bash
# 后台挂起运行
nohup python scheduler_app.py > logs/scheduler.out 2>&1 &
```

### 2. Docker 部署 (推荐)

**构建镜像：**
```bash
docker build -t wechat-ai-publisher .
```

**启动容器 (后台运行)：**
```bash
docker run -d \
  --name wechat-publisher \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  wechat-ai-publisher
```
*注：挂载 `logs` 目录是为了查看日志，挂载 `config` 是为了方便随时修改配置且重启生效。*

## ❓ 常见问题

**Q: 定时发布是全自动的吗？**
A: 是的，但它是**本地定时**。这意味着您的电脑和脚本需要保持运行状态，直到设定的时间到达。微信公众号接口本身不支持服务器端定时发布功能。

**Q: 为什么生成的图片是纯色的？**
A: 微信接口强制要求“保存草稿”必须有一张封面图。为保证发布成功且不侵权，工具目前自动生成随机颜色的纯色图片作为占位封面。您可以在后台手动更换。

**Q: 为什么生成的标题总是有“远方岛屿”？**
A: 这是根据您的定制需求预设的品牌词。如需修改，请调整 `utils/promo_generator.py` 中的代码。
