# WeChat AI Auto Publisher

一个面向微信公众号的 AI 文案生成与发布工具。

项目使用阿里云百炼 DashScope 生成文案，支持本地命令行生成、随机选题、定时等待发布，以及独立的定时任务脚本。当前代码已经兼容旧版 `qwen-plus` / `qwen-max`，也兼容新版 `qwen3.6-plus`。

## 功能概览

- AI 生成公众号文案，输出标题、摘要、标签和正文
- 支持命令行直接生成，也支持随机主题生成
- 可将文章格式化后提交到微信公众号
- 发布时自动生成一张纯色封面图，满足微信素材要求
- 支持 Bark 推送，通知生成成功、发布成功或失败
- 提供独立定时任务脚本，优先抓取微博热搜，失败后回退到内置主题库

## 当前实际行为

为了避免 README 和代码不一致，下面描述的是仓库当前实现，而不是理想状态。

- `generate_promo.py`
  - 负责单次生成和可选发布
  - 支持手动输入主题、随机主题、命令行指定发布时间
  - 如果使用 `-p` 发布，会先生成封面、格式化正文，然后调用微信接口
- `scheduler_app.py`
  - 负责长期运行的自动任务
  - 优先从微博热搜接口和热搜页面抓话题
  - 如果抓取失败，会回退到内置主题库
- 微信发布逻辑
  - 会先保存草稿
  - 保存成功后，代码会继续尝试调用 `freepublish/submit` 自动发布
  - 如果账号权限不足，可能出现“草稿保存成功，但自动发布失败”的情况

## 项目结构

```text
.
├─ config/
│  └─ config.py.example
├─ templates/
│  └─ wechat_default.html
├─ utils/
│  ├─ dashscope_api.py
│  ├─ promo_generator.py
│  ├─ wechat_publisher.py
│  ├─ bark_notifier.py
│  └─ logger.py
├─ generate_promo.py
├─ scheduler_app.py
├─ requirements.txt
└─ README.md
```

## 安装

建议使用虚拟环境。

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` 当前包含：

- `requests`
- `dashscope`
- `Pillow`
- `colorlog`
- `schedule`

## 配置

先复制配置模板：

```bash
copy config\config.py.example config\config.py
```

然后编辑 `config/config.py`。

### 1. DashScope 配置

```python
DASHSCOPE_API_KEY = "你的百炼 API Key"
DASHSCOPE_MODEL = "qwen3.6-plus"
```

当前兼容的模型调用方式：

- `qwen-plus`
- `qwen-max`
- `qwen3.6-plus`

说明：

- `qwen-plus` / `qwen-max` 走旧版 `Generation.call(...)`
- `qwen3.6-plus` 走 `MultiModalConversation.call(...)`

### 2. 微信公众号配置

```python
WECHAT_CONFIG = {
    "app_id": "你的公众号 AppID",
    "app_secret": "你的公众号 AppSecret",
    # "proxy_url": "http://你的代理地址:端口"
}
```

说明：

- 如果服务器 IP 不在微信白名单内，可以配置 `proxy_url`
- 当前 `config.py.example` 里没有默认写出 `proxy_url`，但代码是支持的

### 3. Bark 通知

```python
BARK_KEY = "你的 Bark Key"
```

如果不配置，程序仍可运行，只是不会发送推送通知。

### 4. 发布时间配置

```python
PUBLISH_CONFIG = {
    "enable_schedule": False,
    "target_time": "20:00",
    "timezone": 8,
    "article_template": "wechat_default",
}
```

说明：

- 这部分配置主要被 `generate_promo.py -p` 使用
- 如果命令行没有传 `-t`，且 `enable_schedule=True`，程序会等待到 `target_time` 再执行发布
- `article_template` 为空字符串时，继续使用旧的正文格式化逻辑
- `article_template="wechat_default"` 时，会把 AI 正文塞进 `templates/wechat_default.html` 的 `{{content}}` 占位符

### 5. 路径配置

`config.py.example` 里的 `PROJECT_PATH` 和日志路径仍是旧的本地绝对路径示例，请务必改成你自己的环境。

否则程序可能会：

- 在错误的目录创建日志
- 在旧路径下创建 `temp`、`output` 等目录

## 快速开始

### 1. 只生成文案

```bash
python generate_promo.py "深夜加班后的感悟"
```

### 2. 随机选题生成

```bash
python generate_promo.py -r
```

### 3. 生成并发布

```bash
python generate_promo.py "深夜加班后的感悟" -p
```

### 4. 生成并在指定时间发布

```bash
python generate_promo.py "深夜加班后的感悟" -p -t 22:30
```

### 5. 使用配置文件中的发布时间

先在 `config/config.py` 中设置：

```python
PUBLISH_CONFIG = {
    "enable_schedule": True,
    "target_time": "22:30",
    "timezone": 8,
}
```

然后执行：

```bash
python generate_promo.py "深夜加班后的感悟" -p
```

## 输出内容说明

AI 当前会尝试生成以下字段：

- `keyword`
- `subtitle`
- `digest`
- `tags`
- `content`
- `title`

其中标题会被程序组装成固定格式：

```text
远方夜听 {keyword} | {subtitle}
```

如果模型返回的 JSON 不完整，程序会进行降级处理，尽量返回可用结果。

## 自动发布流程

当你执行带 `-p` 的命令时，实际流程如下：

1. 调用 DashScope 生成文案
2. 自动生成一张 900x383 的纯色封面图
3. 将正文包装成适合微信的 HTML 内容
4. 上传封面图到微信素材接口
5. 调用草稿接口保存文章
6. 草稿保存成功后，继续尝试自动提交发布
7. 发送 Bark 通知

这意味着“发布”并不只是保存草稿。当前代码会进一步尝试自动发布。

## 正文模板

当前仓库内置一个本地公众号正文模板：

- 模板文件：`templates/wechat_default.html`
- 正文插槽：`{{content}}`
- 渲染方式：保留模板头尾装饰，只把 AI 生成的正文插入到中间内容区

如果模板源码是从公众号编辑器里复制出来的，加载时会自动还原常见的 `+` 和 HTML 转义字符。

## 定时任务模式

运行：

```bash
python scheduler_app.py
```

当前逻辑：

1. 到达设定时间后执行任务
2. 优先请求微博热搜接口
3. 如果接口失败，再抓取微博热搜页面
4. 如果页面也失败，回退到内置主题库
5. 生成文案、封面、摘要和正文
6. 保存草稿并尝试自动发布
7. 发送 Bark 通知

### 重要说明

`scheduler_app.py` 当前的执行时间是写死在代码里的：

```python
scheduled_time = "10:25"
```

如果你要修改定时执行时间，需要直接编辑 `scheduler_app.py`，它不会读取 `PUBLISH_CONFIG`。

## 微信发布前置条件

为了让微信接口正常工作，你至少需要满足以下条件：

- 公众号 `app_id` / `app_secret` 配置正确
- 调用来源 IP 在微信白名单内，或者通过代理访问
- 封面图上传成功
- 账号具备对应接口权限

常见情况：

- 未配置代理时，可能遇到 IP 白名单错误
- 草稿保存成功，不代表自动发布一定成功
- 某些自动发布接口需要认证服务号权限

## 日志与排查

主要日志来源：

- `dashscope_api`
- `promo_generator`
- `generate_promo_cli`
- `scheduler_app`
- `WeChatPublisher`
- `bark_notifier`

如果生成失败，优先检查：

- DashScope API Key 是否可用
- 模型名是否填写正确
- 当前模型是否与调用方式兼容
- 返回内容是否为合法 JSON

如果发布失败，优先检查：

- 微信公众号配置是否完整
- 是否需要配置代理
- IP 白名单是否已添加
- 自动发布接口权限是否满足

## 已知限制

- 封面图目前是随机纯色占位图，不是 AI 绘图
- `scheduler_app.py` 的执行时间是硬编码，不读配置文件
- `config.py.example` 中仍保留了旧路径示例，需要手工修改
- 配置文件当前是明文存储密钥，不适合直接提交到公开仓库
- 仓库目前只有基础回归测试，没有完整端到端测试

## 安全建议

不要把真实密钥提交到仓库。

至少包括：

- DashScope API Key
- 微信公众号 `app_secret`
- Bark Key

更稳妥的方式是改成环境变量加载。

## 常见命令

```bash
# 仅生成
python generate_promo.py "今天想写点关于成长的内容"

# 随机主题
python generate_promo.py -r

# 生成并发布
python generate_promo.py "今天想写点关于成长的内容" -p

# 指定发布时间
python generate_promo.py "今天想写点关于成长的内容" -p -t 21:00

# 启动定时任务
python scheduler_app.py
```

## 🐳 服务器/Docker 部署

如果您想让程序在服务器上**每天自动发文**，请使用 `scheduler_app.py` 或 Docker 部署。

定时任务当前逻辑如下：
1. 优先请求微博热搜接口并随机选择一个热搜话题；
2. 如果微博热搜获取失败，则自动回退到内置预设主题；
3. 生成文案后自动排版，并发布到微信公众号草稿箱。

### 1. 直接运行 (Linux/Windows 服务器)
```bash
# 后台挂起运行
nohup python scheduler_app.py > logs/scheduler.out 2>&1 &
```

### 2 Docker 部署 (推荐)

**构建镜像：**
```bash
# 构建
docker build -t wechat-ai-publisher:latest .
# 导出
docker save -o wechat-ai-publisher.tar wechat-ai-publisher:latest
# 导入
docker load -i wechat-ai-publisher.tar
```

**启动容器 (后台运行)：**
```bash
docker run -d \
  --name wechat-publisher \
  --restart always \
  -v /root/wechat-publisher/logs:/app/logs \
  wechat-ai-publisher:latest
```

**检查挂载是否生效：**
```bash
# 进入容器检查
docker exec -it wechat-publisher bash

# 在容器内检查
ls -la /app/config/
cat /app/config/config.py

# 检查Python能否导入
python3 -c "from config.config import DASHSCOPE_API_KEY; print('OK')"

# 退出容器
exit
```

*注：挂载 `logs` 目录是为了查看日志，挂载 `config` 是为了方便随时修改配置且重启生效。*

注：复制服务器的公网IP，添加到微信公众平台白名单 
登录 https://mp.weixin.qq.com
开发 -> 基本配置 -> IP白名单
添加你服务器的IP

## 后续建议

如果你准备继续维护这个项目，下一步最值得做的是：

1. 把 `config.py` 改成环境变量加载
2. 让 `scheduler_app.py` 读取配置文件，而不是硬编码时间
3. 增加一个“仅保存草稿，不自动发布”的显式开关
4. 为微信发布流程补充更多回归测试
