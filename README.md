# WeChat AI Auto Publisher

一个面向微信公众号的 AI 文案生成与发布工具。

项目使用阿里云百炼 DashScope 生成文案，支持命令行单次生成、定时生成草稿，以及基于 Docker + Playwright + noVNC 的 UI 自动化发布。

## 功能概览

- AI 生成公众号文案，输出标题、摘要、标签和正文
- 支持手动主题和随机主题生成
- 支持本地公众号正文模板，使用 `{{content}}` 插槽注入 AI 正文
- 自动生成封面图并通过微信接口保存草稿
- 草稿默认自动开启留言
- 支持 Bark 推送运行状态、失败信息、登录提醒
- 支持登录预检：在发布时间前若干小时检测登录态
- 支持上传登录二维码截图到 imgbb，再把链接通过 Bark 推送到手机
- 支持 Docker 内运行 `Xvfb + x11vnc + noVNC + scheduler_app.py`

## 当前实际行为

为了避免 README 和代码不一致，下面描述的是仓库当前实现。

- `generate_promo.py`
  - 负责单次生成和可选发布
  - 支持手动输入主题、随机主题、命令行指定发布时间
  - 使用 `-p` 时会走微信接口保存草稿
  - 草稿保存成功后，代码仍会尝试调用微信接口自动提交发布；若权限不足，通常表现为“草稿保存成功，但自动发布失败”
- `scheduler_app.py`
  - 负责长期运行的自动任务
  - 到 `PUBLISH_CONFIG["target_time"]` 时抓取微博热搜或回退主题并生成草稿
  - 若 `enable_web_publish=True`，会在 `publish_time` 之前 `login_check_hours_before` 小时执行登录预检
  - 若登录失效，会尝试截图并上传到 imgbb，然后通过 Bark 推送二维码链接和 noVNC 地址
  - 到 `publish_time` 时使用浏览器自动化发布“最新草稿”
- 微信发布逻辑
  - API 保存草稿阶段会自动开启留言
  - 原创声明目前没有自动化
  - UI 自动化发布依赖持久化浏览器目录 `/data/wechat-profile`

## 项目结构

```text
.
├─ config/
│  └─ config.py.example
├─ docker/
│  └─ start.sh
├─ templates/
│  └─ wechat_default.html
├─ tests/
├─ utils/
│  ├─ bark_notifier.py
│  ├─ dashscope_api.py
│  ├─ imgbb_uploader.py
│  ├─ promo_generator.py
│  ├─ wechat_publisher.py
│  ├─ wechat_web_publisher.py
│  └─ logger.py
├─ docker-compose.yml.example
├─ generate_promo.py
├─ scheduler_app.py
├─ Dockerfile
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

如果你要在本机直接跑 UI 自动化发布，还需要额外安装 Playwright：

```bash
pip install playwright
python -m playwright install chromium
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
- 若不走代理，请把服务器公网 IP 加入微信公众平台 IP 白名单

### 3. Bark 与 imgbb

```python
BARK_KEY = "你的 Bark Key"
IMGBB_API_KEY = "你的 imgbb API Key"
IMGBB_EXPIRATION = 86400
```

说明：

- 不配置 `BARK_KEY` 也能运行，只是不会发送推送
- 不配置 `IMGBB_API_KEY` 时，登录预检仍会推送提醒，但不会带二维码截图链接
- `IMGBB_EXPIRATION=86400` 表示二维码截图链接默认保留 24 小时

### 4. 发布配置

```python
PUBLISH_CONFIG = {
    "enable_schedule": False,
    "target_time": "20:00",
    "timezone": 8,
    "article_template": "wechat_default",
    "enable_web_publish": True,
    "publish_time": "20:00",
    "login_check_hours_before": 2,
    "max_publish_retries": 3,
}

WEB_PUBLISH_CONFIG = {
    "browser_profile_dir": "/data/wechat-profile",
    "novnc_port": 6080,
    "headless": False,
}
```

说明：

- `target_time`：生成并保存草稿的时间
- `enable_web_publish`：是否启用后续 UI 自动化发布
- `publish_time`：UI 自动化发布“最新草稿”的时间
- `login_check_hours_before`：提前多少小时做登录检测
- `article_template="wechat_default"` 时，会把 AI 正文塞进 `templates/wechat_default.html` 的 `{{content}}`
- `browser_profile_dir` 需要与 Docker 挂载目录对应，才能保留微信登录态

### 5. 路径配置

`config.py.example` 里的 `PROJECT_PATH` 和日志路径仍是旧的绝对路径示例，请改成你自己的环境。

否则程序可能会：

- 在错误目录写日志
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

### 3. 生成并保存草稿

```bash
python generate_promo.py "深夜加班后的感悟" -p
```

说明：

- 这里的 `-p` 最终会调用微信草稿接口
- 草稿保存成功后，代码仍会继续尝试微信接口自动发布
- 对无自动发布权限的账号，通常会得到“草稿保留成功，发布提交失败”的结果

### 4. 生成并在指定时间执行保存草稿

```bash
python generate_promo.py "深夜加班后的感悟" -p -t 22:30
```

### 5. 使用配置文件中的时间

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

## 正文模板

当前仓库内置一个本地公众号正文模板：

- 模板文件：`templates/wechat_default.html`
- 正文插槽：`{{content}}`
- 渲染方式：保留模板头尾装饰，只把 AI 生成的正文插入到中间内容区

如果模板源码是从公众号编辑器里复制出来的，加载时会自动还原常见的 `+` 和 HTML 转义字符。

## 自动发布流程

### `generate_promo.py -p`

1. 调用 DashScope 生成文案
2. 自动生成一张 900x383 的纯色封面图
3. 将正文包装成适合微信的 HTML 内容
4. 上传封面图到微信素材接口
5. 调用草稿接口保存文章
6. 自动开启留言
7. 尝试调用微信接口自动提交发布
8. 发送 Bark 通知

### `scheduler_app.py`

1. 到 `target_time` 执行定时任务
2. 优先请求微博热搜接口
3. 如果接口失败，再抓取微博热搜页面
4. 如果页面也失败，回退到内置主题库
5. 生成文案、封面、摘要和正文
6. 调用微信接口保存草稿
7. 若启用 `enable_web_publish`，则在 `publish_time - login_check_hours_before` 做登录预检
8. 若未登录，推送 Bark 提醒；配置 imgbb 时附带二维码截图链接
9. 到 `publish_time` 时用 Playwright 打开公众号后台并发布最新草稿

## 定时任务模式

运行：

```bash
python scheduler_app.py
```

当前调度读取 `config/config.py` 中的 `PUBLISH_CONFIG`，不再是硬编码时间。

调度逻辑：

- `target_time`：生成并保存草稿
- `publish_time`：UI 自动化发布最新草稿
- `login_check_hours_before`：提前做登录状态检测
- `max_publish_retries`：UI 自动化发布失败后的重试次数

## 微信发布前置条件

为了让微信接口和 UI 自动化同时正常工作，你至少需要满足以下条件：

- 公众号 `app_id` / `app_secret` 配置正确
- 调用来源 IP 在微信白名单内，或者通过代理访问
- 封面图上传成功
- 服务器能访问 `mp.weixin.qq.com`
- 浏览器登录态目录可持久化保存

常见情况：

- 未配置代理时，可能遇到 IP 白名单错误
- 草稿保存成功，不代表微信接口自动发布一定成功
- UI 自动化发布依赖页面选择器，微信后台改版后可能需要调整
- “发布最新草稿”策略要求你确认草稿箱中最新一篇就是本次待发文章

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
- Bark 是否能正常收到登录提醒
- `/data/wechat-profile` 是否真的持久化
- noVNC 页面能否正常打开并完成扫码

## 常见命令

```bash
# 仅生成
python generate_promo.py "今天想写点关于成长的内容"

# 随机主题
python generate_promo.py -r

# 生成并保存草稿
python generate_promo.py "今天想写点关于成长的内容" -p

# 指定草稿生成时间
python generate_promo.py "今天想写点关于成长的内容" -p -t 21:00

# 启动定时任务
python scheduler_app.py
```

## Docker 部署

如果你准备把服务挂在腾讯云服务器上，建议直接使用 Docker。

容器启动后会同时运行：

- `Xvfb`
- `x11vnc`
- `noVNC`
- `python scheduler_app.py`

其中浏览器登录态目录固定为 `/data/wechat-profile`，必须持久化挂载。

当前 `docker-compose.yml` 已默认使用 Docker named volume `wechat-profile-data` 持久化这个目录。

### `wechat-profile` 是什么

`/data/wechat-profile` 是 Chromium 的用户数据目录，会保存：

- 微信公众平台登录 Cookie / Session
- 浏览器本地授权状态
- 与当前账号相关的部分缓存数据

对本项目来说，它的核心作用只有一个：保留公众号后台登录态。

如果你不保留这个目录，会出现：

- 容器重启后需要重新扫码登录
- 定时发布时可能因为未登录而失败
- `18:00` 登录预检频繁触发 Bark 提醒

结论：

- Linux 服务器部署时，推荐直接使用 Docker volume 持久化，不需要手动准备 `wechat-profile/`
- Windows 本地 Docker Desktop 调试时，浏览器 profile bind mount 可能不稳定，建议只把它当调试环境
- 服务器首次启动后登录一次，并持续保留 Docker volume 中的 profile 数据

### 1. 本地准备 release 包

```bash
cp docker-compose.yml.example docker-compose.yml
cp .env.example .env
mkdir -p logs
```

然后准备好下面这些文件：

- `.env`
- `docker-compose.yml`
- `config/config.py`

其中：

- 编辑 `.env`，至少填好 `VNC_PASSWORD`
- 直接使用仓库里的 `config/config.py`，写入你的真实业务配置

示例：

```env
VNC_PASSWORD=replace-with-a-strong-password
AUTO_OPEN_BROWSER=true
```

### 2. 本地构建镜像并导出

```bash
win系统运行:
.\build_release.bat
```

```bash
docker build -t wechat-ai-publisher:latest .
docker save -o wechat-ai-publisher.tar wechat-ai-publisher:latest
```

### 3. 组装 release 目录并上传服务器

推荐把下面这些文件放进同一个目录：

```text
release/
├─ wechat-ai-publisher.tar
├─ docker-compose.yml
├─ .env
└─ config/
   └─ config.py
```

然后把整个 ` release.zip 或 release/` 上传到服务器。

说明：

- `logs/` 如果不存在，`docker compose up -d` 时会自动创建
- 当前镜像不会包含你的真实 `config.py`，所以 `config/config.py` 必须跟 release 包一起上传
- 登录态默认保存在 Docker volume `wechat-profile-data` 中，不需要把 `wechat-profile/` 目录打包上传
- 如果你确实想迁移本地登录态到服务器，需要额外改 compose，把 volume 改回 bind mount；这不是默认推荐路径

### 4. 服务器上直接 load + up

```bash
# 一键命令
chmod +x deploy_centos7.sh
./deploy_centos7.sh
```

```bash
cd release
docker load -i wechat-ai-publisher.tar
docker compose up -d
```

说明：

- `AUTO_OPEN_BROWSER=true` 时，容器启动后会自动在 noVNC 里打开公众号登录页
- 首次扫码登录完成后，请把这个 Chromium 窗口关闭，避免后续 Playwright 发布时遇到 profile lock
- 后续不要删除 Docker volume `wechat-profile-data`，否则服务器会丢失登录态

### 5. 如果你更习惯 `docker run`

```bash
docker run -d \
  --name wechat-publisher \
  --restart unless-stopped \
  --shm-size=1g \
  -e VNC_PASSWORD='replace-with-a-strong-password' \
  -e AUTO_OPEN_BROWSER='true' \
  -p 6080:6080 \
  -p 5900:5900 \
  -v $(pwd)/config/config.py:/app/config/config.py:ro \
  -v $(pwd)/logs:/app/logs \
  -v wechat-profile-data:/data/wechat-profile \
  wechat-ai-publisher:latest
```

如果你使用 `docker run`，请先创建 volume：

```bash
docker volume create wechat-profile-data
```

### 6. 首次登录

1. 打开 `http://<server-ip>:6080/vnc.html`
2. 输入 `VNC_PASSWORD`
3. 若开启了 `AUTO_OPEN_BROWSER=true`，会自动看到公众号登录页；否则手动启动浏览器访问 `https://mp.weixin.qq.com`
4. 在 noVNC 里的浏览器中扫码登录公众号后台
5. 登录成功后关闭这个 Chromium 窗口
6. 确认 `/data/wechat-profile` 目录已写入持久化数据

之后定时任务会复用这个登录态。

如果你是“本地打包 -> 上传服务器 -> 服务器直接运行”的模式，有两种可选方式：

- 方式 A：默认推荐。直接使用 Docker volume，服务器首次启动后通过 noVNC 或 Bark 二维码登录一次。
- 方式 B：如果你非常需要迁移本地登录态，再额外改 compose 为 bind mount，把本地 `wechat-profile/` 一起上传。

两种方式都可以，但无论哪种，都要长期保留服务器上的 profile 数据。

### 7. 登录预检与 Bark 提醒

当以下配置生效时：

```python
PUBLISH_CONFIG = {
    "enable_web_publish": True,
    "publish_time": "20:00",
    "login_check_hours_before": 2,
}
```

系统会在 `18:00` 先检查是否已登录。

如果未登录：

- 会推送 Bark 提醒
- 若配置了 `IMGBB_API_KEY`，会把二维码截图上传到 imgbb
- Bark 消息会带上二维码截图链接和 noVNC 提示地址

### 8. 运行时端口

- `6080`：noVNC Web 页面，示例 `http://<server-ip>:6080/vnc.html`
- `5900`：原生 VNC 端口，可选

`6080` 和 `5900` 都不要直接裸露到公网。至少应放在防火墙白名单、VPN、堡垒机或反向代理访问控制之后。

### 9. 常用排查命令

```bash
docker compose logs -f
docker exec -it wechat-publisher bash
ls -la /data/wechat-profile
```

### 10. 微信白名单

把服务器公网 IP 加到微信公众平台白名单：

1. 打开 `https://mp.weixin.qq.com`
2. 进入“开发 -> 基本配置 -> IP 白名单”
3. 添加你的服务器公网 IP

## 已知限制

- 封面图目前是随机纯色占位图，不是 AI 绘图
- `config.py.example` 中仍保留了旧路径示例，需要手工修改
- 配置文件当前是明文存储密钥，不适合直接提交到公开仓库
- UI 自动化依赖微信后台 DOM 结构，页面改版后可能需要调整选择器
- “发布最新草稿”策略在草稿箱存在人工新建草稿时有误发风险
- 目前只有回归测试，没有真实公众号后台的端到端验收

## 安全建议

不要把真实密钥提交到仓库。

至少包括：

- DashScope API Key
- 微信公众号 `app_secret`
- Bark Key
- imgbb API Key
- `VNC_PASSWORD`

更稳妥的方式是改成环境变量加载，并把 noVNC 放到受控网络环境中。

## 后续建议

如果你准备继续维护这个项目，下一步最值得做的是：

1. 把 `config.py` 改成环境变量加载
2. 为 UI 自动化发布增加真实页面验收和选择器巡检
3. 增加“仅保存草稿，不尝试微信接口自动发布”的显式开关
4. 为微信发布流程补充更多回归测试
