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
    "target_time": "20:00",
    "timezone": 8,
    "article_template": "wechat_default",
    "hot_topic_candidate_limit": 3,
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
