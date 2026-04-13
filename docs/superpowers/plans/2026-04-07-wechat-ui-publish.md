# WeChat UI Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Docker-based Playwright publishing stage that checks WeChat login two hours before publish time, sends a Bark QR-code alert through imgbb when login is required, and publishes the latest draft at the scheduled time.

**Architecture:** Keep the current API draft-save flow as the source of truth for article creation. Add separate web-publish utilities for login checking, QR upload, and UI publishing, then orchestrate them from the scheduler with explicit precheck and publish jobs.

**Tech Stack:** Python, Playwright, requests, schedule, Bark, imgbb, Docker, Xvfb, x11vnc, noVNC, unittest

---

### Task 1: Add configuration coverage for web publish and QR alerts

**Files:**
- Modify: `config/config.py.example`
- Modify: `config/config.py`
- Test: `tests/test_scheduler_web_publish_config.py`

- [ ] **Step 1: Write the failing test**

```python
def test_config_exposes_web_publish_settings():
    config = Config()
    assert config.PUBLISH_CONFIG["enable_web_publish"] is True
    assert config.PUBLISH_CONFIG["login_check_hours_before"] == 2
    assert config.IMGBB_EXPIRATION == 600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_scheduler_web_publish_config -v`
Expected: FAIL because the config keys do not exist yet

- [ ] **Step 3: Write minimal implementation**

Add these configuration fields:

```python
IMGBB_API_KEY = ""
IMGBB_EXPIRATION = 600

PUBLISH_CONFIG = {
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_scheduler_web_publish_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/config.py.example config/config.py tests/test_scheduler_web_publish_config.py
git commit -m "feat: add web publish config"
```

### Task 2: Add Bark QR-link and alert payload support

**Files:**
- Modify: `utils/bark_notifier.py`
- Create: `tests/test_bark_notifier.py`

- [ ] **Step 1: Write the failing test**

```python
def test_send_accepts_url_and_custom_icon():
    notifier = BarkNotifier()
    notifier.send("title", "body", url="https://example.com/qr.png", icon="https://example.com/icon.png")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bark_notifier -v`
Expected: FAIL because `send()` does not accept the new parameters yet

- [ ] **Step 3: Write minimal implementation**

Extend `send()` to accept optional `url`, `icon`, and `level` arguments and pass them through to Bark JSON payloads while preserving current behavior.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_bark_notifier -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/bark_notifier.py tests/test_bark_notifier.py
git commit -m "feat: support bark qr alerts"
```

### Task 3: Add imgbb uploader utility

**Files:**
- Create: `utils/imgbb_uploader.py`
- Create: `tests/test_imgbb_uploader.py`

- [ ] **Step 1: Write the failing test**

```python
def test_upload_uses_expiration_and_returns_display_url():
    uploader = ImgbbUploader(api_key="key", expiration=600)
    result = uploader.upload("tests/fixtures/qr.png")
    assert result["url"] == "https://i.ibb.co/example.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_imgbb_uploader -v`
Expected: FAIL because the uploader module does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement an uploader that:

- reads the local file,
- base64-encodes it or submits multipart form data per imgbb API requirements,
- sends `expiration=600`,
- returns the public display URL,
- raises a clear exception on non-success responses.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_imgbb_uploader -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/imgbb_uploader.py tests/test_imgbb_uploader.py
git commit -m "feat: add imgbb qr uploader"
```

### Task 4: Add WeChat web publisher abstraction

**Files:**
- Create: `utils/wechat_web_publisher.py`
- Create: `tests/test_wechat_web_publisher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_login_check_returns_false_when_login_button_present():
    publisher = WeChatWebPublisher(config)
    assert publisher.is_logged_in(page) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_wechat_web_publisher -v`
Expected: FAIL because the module and interface do not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement a focused class with methods for:

- launching a persistent browser context,
- checking login state,
- opening the draft list,
- publishing the latest draft,
- saving screenshots on failures.

Keep page selectors isolated in small helpers so future DOM updates are localized.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_wechat_web_publisher -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add utils/wechat_web_publisher.py tests/test_wechat_web_publisher.py
git commit -m "feat: add wechat web publisher"
```

### Task 5: Add scheduler timing and orchestration for precheck plus publish

**Files:**
- Modify: `scheduler_app.py`
- Create: `tests/test_scheduler_web_publish.py`

- [ ] **Step 1: Write the failing test**

```python
def test_login_check_runs_two_hours_before_publish_time():
    publish_time = "20:00"
    assert compute_precheck_time(publish_time, 2) == "18:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_scheduler_web_publish -v`
Expected: FAIL because the helper and orchestration do not exist yet

- [ ] **Step 3: Write minimal implementation**

Add:

- a helper to compute the precheck time,
- a login precheck job,
- a publish-latest-draft job,
- Bark fallback behavior when not logged in at publish time,
- three-attempt retry loop around UI publish.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_scheduler_web_publish -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scheduler_app.py tests/test_scheduler_web_publish.py
git commit -m "feat: orchestrate web publish schedule"
```

### Task 6: Add Docker runtime for browser automation and noVNC

**Files:**
- Modify: `Dockerfile`
- Create: `docker/start.sh`
- Modify: `README.md`

- [ ] **Step 1: Write the failing verification**

Document the expected runtime:

- container starts Python scheduler,
- container exposes noVNC on `6080`,
- browser profile persists under `/data/wechat-profile`.

- [ ] **Step 2: Run verification to show the current image is insufficient**

Run: `docker build -t wechat-ai-publisher:test .`
Expected: Build succeeds but runtime lacks Chromium/noVNC support

- [ ] **Step 3: Write minimal implementation**

Update the image to install:

- Playwright browser dependencies,
- Chromium,
- Xvfb,
- x11vnc,
- noVNC,
- a startup script that launches the display stack and then runs `scheduler_app.py`.

- [ ] **Step 4: Run verification to confirm the runtime starts**

Run:

```bash
docker build -t wechat-ai-publisher:test .
docker run --rm -p 6080:6080 wechat-ai-publisher:test
```

Expected:

- noVNC port opens,
- scheduler process starts,
- no immediate crash from missing browser/display dependencies.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker/start.sh README.md
git commit -m "feat: add docker web publish runtime"
```

### Task 7: Verify end-to-end regression safety

**Files:**
- Test: `tests/test_scheduler_web_publish_config.py`
- Test: `tests/test_bark_notifier.py`
- Test: `tests/test_imgbb_uploader.py`
- Test: `tests/test_wechat_web_publisher.py`
- Test: `tests/test_scheduler_web_publish.py`
- Test: `tests/test_dashscope_api.py`
- Test: `tests/test_wechat_template_rendering.py`
- Test: `tests/test_wechat_publish_article.py`

- [ ] **Step 1: Run targeted unit tests**

Run:

```bash
python -m unittest ^
  tests.test_scheduler_web_publish_config ^
  tests.test_bark_notifier ^
  tests.test_imgbb_uploader ^
  tests.test_wechat_web_publisher ^
  tests.test_scheduler_web_publish ^
  tests.test_dashscope_api ^
  tests.test_wechat_template_rendering ^
  tests.test_wechat_publish_article -v
```

Expected: PASS

- [ ] **Step 2: Run syntax verification**

Run:

```bash
python -m py_compile scheduler_app.py generate_promo.py utils\wechat_publisher.py utils\bark_notifier.py utils\imgbb_uploader.py utils\wechat_web_publisher.py
```

Expected: PASS

- [ ] **Step 3: Run Docker smoke verification**

Run:

```bash
docker build -t wechat-ai-publisher:test .
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "test: verify web publish integration"
```
