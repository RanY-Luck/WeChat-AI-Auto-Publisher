# WeChat AI Auto Publisher

一个用于微信公众号文案生成、草稿保存和自动发布的工具。

当前推荐用法很简单：

1. 本地准备配置文件
2. 执行 `build_release.bat` 生成 `release.zip`
3. 执行 `upload_and_deploy.bat` 上传并部署到服务器
4. 首次通过 noVNC 扫码登录公众号后台

下面只保留这条主线。

## 部署前准备

本地环境需要：

- Windows
- Python
- Docker
- `ssh` / `scp`

服务器环境需要：

- Linux
- Docker
- `docker compose` 或 `docker-compose`
- `unzip`

## 第一步：准备配置文件

先准备这几个文件：

- `.env`
- `docker-compose.yml`
- `config/config.py`

如果没有模板文件，先复制：

```powershell
Copy-Item .\docker-compose.yml.example .\docker-compose.yml
Copy-Item .\config\config.py.example .\config\config.py
```

### `config/config.py`

至少确认以下配置：

```python
DASHSCOPE_API_KEY = "你的百炼 API Key"
DASHSCOPE_MODEL = "qwen3.6-plus"

WECHAT_CONFIG = {
    "app_id": "你的公众号 AppID",
    "app_secret": "你的公众号 AppSecret",
}

BARK_KEY = "你的 Bark Key"
IMGBB_API_KEY = "你的 imgbb API Key"

PUBLISH_CONFIG = {
    "enable_schedule": True,
    "target_time": "19:50",
    "timezone": 8,
    "article_template": "wechat_default",
    "hot_topic_candidate_limit": 3,
    "random_daily_schedule_enabled": True,
    "daily_random_runs_min": 5,
    "daily_random_runs_max": 5,
    "enable_web_publish": True,
    "publish_time": "20:00",
    "login_check_hours_before": 3,
    "max_publish_retries": 3,
}

WEB_PUBLISH_CONFIG = {
    "browser_profile_dir": "/data/wechat-profile",
    "novnc_port": 6080,
    "headless": False,
}
```

### `.env`

至少确认这些字段：

```env
COMPOSE_PROJECT_NAME=wechat-account-a
CONTAINER_NAME=wechat-publisher-account-a
IMAGE_NAME=wechat-ai-publisher:account-a
HOST_NOVNC_PORT=6080
HOST_VNC_PORT=5900
WECHAT_PROFILE_VOLUME=wechat-profile-account-a
VNC_PASSWORD=replace-with-a-strong-password
AUTO_OPEN_BROWSER=true
```

`hot_topic_candidate_limit` 表示只从微博热点前 N 条里挑选本次主题，默认建议填 `3`。

如果你想走“引发讨论”的标题方向，可以额外配置：

```python
PUBLISH_CONFIG = {
    "discussion_title_enabled": True,
    "discussion_cover_pool_dir": "/app/cover_pool",
}
```

这两个字段启用后：

- 最终发布标题会固定成 `发现中国有一个奇怪的现象：xxx`
- `xxx` 会直接基于本次主题生成，不再沿用原来的 `远方夜听 ... | ...` 标题格式
- 封面不再优先取微博热点图，而是从你上传到素材池目录里的图片中随机选一张
- 程序会基于选中的素材图重新生成一张发布封面，并把本次标题叠加到封面上
- 如果素材池目录不存在、为空或图片不可用，本次任务会直接失败并提示检查素材池

如果你用 Docker 部署，直接把封面图放到项目根目录的 `cover_pool/` 目录即可。
`docker-compose.yml` 默认会把它挂载到容器内的 `/app/cover_pool`，所以 `discussion_cover_pool_dir` 保持 `/app/cover_pool` 就行。

当前推荐模式支持“每天随机发 min~max 次完整流程”，如果你把 `min=max`，那就是固定条数：

```python
PUBLISH_CONFIG = {
    "enable_schedule": True,
    "random_daily_schedule_enabled": True,
    "daily_random_runs_min": 5,
    "daily_random_runs_max": 5,
    "hot_topic_candidate_limit": 3,
    "enable_web_publish": True,
}
```

启用后，系统会在 `00:00-23:59` 之间每天随机生成 `min~max` 个执行时间点；每次都会走完整流程：选题、生成内容、存草稿、自动发布。热点规则仍然是“微博前 N 个热点里随机选 1 个”，这里的 `N` 由 `hot_topic_candidate_limit` 控制。

封面规则补充：

- 程序会优先尝试使用热点数据里自带的可用封面图
- 微博公开热搜接口大多数时候只返回“新/热”小角标，不会稳定提供大图封面
- 如果当前热点拿不到可用原图，系统会自动回退到本地生成的封面图，不会因为封面缺失中断发文流程
- 回退封面已经不是纯色底图，会带标题信息，点击感会比之前更强一些

登录行为补充：

- 如果随机任务开始时检测到公众号后台未登录，程序会保留登录页并进入等待状态，不会立刻放弃当前任务
- Bark 只提醒 1 次，后续静默等待你扫码登录
- 你扫码成功后，程序会继续执行当前这一次挂起的随机任务
- 等待登录期间如果新的随机任务时间到了，新的那次会直接跳过，不排队补跑

如果你想退回旧的固定时刻模式，把这几个字段改掉：

```python
PUBLISH_CONFIG = {
    "random_daily_schedule_enabled": False,
    "target_time": "19:50",
    "publish_time": "20:00",
}
```

补充说明：

- `daily_random_runs_min=3`、`daily_random_runs_max=5` 表示系统每天会随机执行 `3~5` 次
- `daily_random_runs_min=5`、`daily_random_runs_max=5` 表示系统每天固定执行 `5` 次
- `target_time` 和 `publish_time` 在随机模式下不会作为当天固定触发时刻使用，只保留给兼容旧模式
- `login_check_hours_before` 也只在固定时刻模式下有意义
- `enable_web_publish=True` 时，每次随机任务生成草稿后会立即继续自动发布
- 如果当前正处于“等待扫码登录”状态，新的随机任务会直接跳过

## 第二步：本地打包

执行：

```powershell
.\build_release.bat
```

脚本会自动：

1. 检查必要文件
2. 构建 Docker 镜像
3. 导出镜像 tar
4. 组装 `release/`
5. 生成 `release.zip`

最终用于部署的是根目录下的 `release.zip`。

## 第三步：上传并部署到服务器

先打开 [upload_and_deploy.bat](/F:/gitpush/WeChat-AI-Auto-Publisher/upload_and_deploy.bat)，按你的服务器修改这几个变量：

- `REMOTE_USER`
- `REMOTE_HOST`
- `REMOTE_DIR`

然后执行：

```powershell
.\upload_and_deploy.bat
```

它会自动：

1. 上传 `release.zip`
2. 在服务器解压
3. 执行 `chmod +x deploy_centos7.sh`
4. 执行 `./deploy_centos7.sh`
5. 输出容器状态和最近日志

## 第四步：首次扫码登录

部署成功后，第一次需要手动登录公众号后台。

打开：

```text
http://<服务器IP>:<HOST_NOVNC_PORT>/vnc.html
```

然后：

1. 输入 `.env` 中的 `VNC_PASSWORD`
2. 扫码登录公众号后台
3. 登录成功后关闭 noVNC 里的 Chromium 窗口

后续系统会复用 `/data/wechat-profile` 中的登录态。

## 启动后的行为

服务启动后，日志和 Bark 通知会直接输出“今天随机计划执行几次、对应时间点是什么”。每天跨日后，系统会自动生成新一天的随机计划，不需要重启容器。


如果服务器上临时处理：

```bash
sed -i 's/\r$//' deploy_centos7.sh
chmod +x deploy_centos7.sh
./deploy_centos7.sh
```

###  PowerShell 提示 `ssh` 或 `scp` 不是命令

先检查系统是否有 OpenSSH：

```powershell
ssh -V
scp -V
```

## 安全提示

不要把真实密钥提交到仓库，包括：

- DashScope API Key
- 微信公众号 `app_secret`
- Bark Key
- imgbb API Key
- `VNC_PASSWORD`
