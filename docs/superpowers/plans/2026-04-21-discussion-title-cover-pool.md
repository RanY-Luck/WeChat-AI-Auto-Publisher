# Discussion Title And Cover Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Force the final published title into a fixed discussion-driving pattern and replace hot-topic cover sourcing with a local operator-managed cover pool that renders a new publish cover for each run.

**Architecture:** Keep the change localized in `scheduler_app.py` by adding deterministic title-formatting helpers, local cover-pool helpers, and a render step that turns a randomly selected pool image into a temporary publish cover with title text applied. Reuse the existing content-generation and WeChat publish flow, but override the final title and cover path before publishing.

**Tech Stack:** Python, Pillow, `unittest`, Markdown docs

---

## File Structure

- Modify: `scheduler_app.py`
  Responsibility: own deterministic discussion-title formatting, local cover-pool discovery, publish-cover rendering, and job-flow wiring.
- Modify: `utils/promo_generator.py`
  Responsibility: stop treating the old `远方夜听 ... | ...` format as the final published title source when the scheduler needs a deterministic title.
- Modify: `config/config.py.example`
  Responsibility: document the new title and cover-pool config fields.
- Modify: `README.md`
  Responsibility: explain the new discussion title mode and local cover-pool behavior.
- Modify: `tests/test_hot_topic_cover.py`
  Responsibility: cover deterministic title formatting, local cover-pool selection, publish-cover rendering, and cleanup behavior.

### Task 1: Add failing tests for deterministic discussion title formatting

**Files:**
- Modify: `tests/test_hot_topic_cover.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Write the failing title-format test**

```python
def test_build_discussion_title_uses_fixed_prefix():
    title = scheduler_app.build_discussion_title("男女那些事")
    assert title == "发现中国有一个奇怪的现象：男女那些事"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_build_discussion_title_uses_fixed_prefix -v`
Expected: FAIL because `build_discussion_title` does not exist yet.

- [ ] **Step 3: Write the failing normalization test**

```python
def test_build_discussion_title_trims_trailing_punctuation():
    title = scheduler_app.build_discussion_title("家庭那些事!!! ")
    assert title == "发现中国有一个奇怪的现象：家庭那些事"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_build_discussion_title_trims_trailing_punctuation -v`
Expected: FAIL because deterministic normalization is not implemented yet.

### Task 2: Add failing tests for local cover-pool discovery and selection

**Files:**
- Modify: `tests/test_hot_topic_cover.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Write the failing cover-pool discovery test**

```python
def test_list_cover_pool_images_returns_supported_images_only():
    with TemporaryDirectory() as temp_dir:
        Path(temp_dir, "a.jpg").write_bytes(b"jpg")
        Path(temp_dir, "b.png").write_bytes(b"png")
        Path(temp_dir, "note.txt").write_text("ignore", encoding="utf-8")

        images = scheduler_app.list_cover_pool_images(temp_dir)

    assert [Path(path).name for path in images] == ["a.jpg", "b.png"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_list_cover_pool_images_returns_supported_images_only -v`
Expected: FAIL because cover-pool discovery does not exist yet.

- [ ] **Step 3: Write the failing random-selection test**

```python
def test_choose_cover_pool_image_uses_random_choice():
    images = ["a.jpg", "b.jpg"]

    class FakeRandom:
        def choice(self, values):
            assert values == images
            return "b.jpg"

    chosen = scheduler_app.choose_cover_pool_image(images, random_module=FakeRandom())
    assert chosen == "b.jpg"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_choose_cover_pool_image_uses_random_choice -v`
Expected: FAIL because the selection helper does not exist yet.

### Task 3: Add failing tests for render-time cover generation

**Files:**
- Modify: `tests/test_hot_topic_cover.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Write the failing render test**

```python
def test_render_cover_from_pool_asset_creates_new_output_file():
    with TemporaryDirectory() as temp_dir:
        source = Path(temp_dir, "source.jpg")
        Image.new("RGB", (1200, 800), color=(40, 50, 60)).save(source)

        output = scheduler_app.render_cover_from_pool_asset(
            base_image_path=str(source),
            title="发现中国有一个奇怪的现象：男女那些事",
        )

        assert output != str(source)
        assert Path(output).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_render_cover_from_pool_asset_creates_new_output_file -v`
Expected: FAIL because render-time cover creation does not exist yet.

- [ ] **Step 3: Write the failing missing-pool test**

```python
def test_resolve_cover_path_from_pool_returns_none_when_pool_is_empty():
    with TemporaryDirectory() as temp_dir:
        cover_path = scheduler_app.resolve_cover_path_from_pool(
            cover_pool_dir=temp_dir,
            title="发现中国有一个奇怪的现象：家庭那些事",
        )

    assert cover_path is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_resolve_cover_path_from_pool_returns_none_when_pool_is_empty -v`
Expected: FAIL because pool-based cover resolution does not exist yet.

### Task 4: Implement minimal discussion title and cover-pool helpers

**Files:**
- Modify: `scheduler_app.py`
- Test: `tests/test_hot_topic_cover.py`

- [ ] **Step 1: Implement the smallest title and pool helpers**

```python
def build_discussion_title(topic_text):
    topic_text = re.sub(r"[!,.，。！？:：;；、\\s]+$", "", (topic_text or "").strip())
    return f"发现中国有一个奇怪的现象：{topic_text}" if topic_text else "发现中国有一个奇怪的现象：今天的关系难题"


def list_cover_pool_images(cover_pool_dir):
    if not cover_pool_dir or not os.path.isdir(cover_pool_dir):
        return []
    supported = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted(
        str(path) for path in Path(cover_pool_dir).iterdir()
        if path.is_file() and path.suffix.lower() in supported
    )


def choose_cover_pool_image(images, random_module=None):
    random_module = random_module or random
    return random_module.choice(images) if images else None
```

- [ ] **Step 2: Run the new helper tests**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_build_discussion_title_uses_fixed_prefix tests.test_hot_topic_cover.HotTopicCoverTests.test_build_discussion_title_trims_trailing_punctuation tests.test_hot_topic_cover.HotTopicCoverTests.test_list_cover_pool_images_returns_supported_images_only tests.test_hot_topic_cover.HotTopicCoverTests.test_choose_cover_pool_image_uses_random_choice -v`
Expected: PASS

- [ ] **Step 3: Implement minimal render and pool-resolution helpers**

```python
def render_cover_from_pool_asset(base_image_path, title):
    image = Image.open(base_image_path).convert("RGB")
    image = _resize_cover_image(image, target_size=(900, 383))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 250, 900, 383), fill=(10, 18, 28))
    ...
    image.save(output_path, quality=92)
    return output_path


def resolve_cover_path_from_pool(cover_pool_dir, title, random_module=None):
    images = list_cover_pool_images(cover_pool_dir)
    chosen = choose_cover_pool_image(images, random_module=random_module)
    if not chosen:
        return None
    return render_cover_from_pool_asset(chosen, title=title)
```

- [ ] **Step 4: Run the render and pool-resolution tests**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_render_cover_from_pool_asset_creates_new_output_file tests.test_hot_topic_cover.HotTopicCoverTests.test_resolve_cover_path_from_pool_returns_none_when_pool_is_empty -v`
Expected: PASS

### Task 5: Add failing job-integration test for final title and local cover usage

**Files:**
- Modify: `tests/test_hot_topic_cover.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Write the failing integration test**

```python
def test_job_uses_discussion_title_and_pool_cover_for_publish():
    fake_generator.generate_promo.return_value = {
        "title": "旧标题",
        "content": "正文内容",
        "digest": "摘要",
    }
    ...
    fake_config = SimpleNamespace(PUBLISH_CONFIG={
        "discussion_title_enabled": True,
        "discussion_cover_pool_dir": "F:/pool",
    })

    scheduler_app.job()

    fake_publisher.format_for_wechat.assert_called_once()
    assert fake_publisher.format_for_wechat.call_args.kwargs["title"] == "发现中国有一个奇怪的现象：男女那些事"
    assert fake_publisher.format_for_wechat.call_args.kwargs["cover_image"] == "temp/rendered-cover.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_job_uses_discussion_title_and_pool_cover_for_publish -v`
Expected: FAIL because `job()` still uses the generator title and current cover resolution path.

### Task 6: Wire the scheduler job to the deterministic title and local cover pool

**Files:**
- Modify: `scheduler_app.py`
- Modify: `utils/promo_generator.py`
- Test: `tests/test_hot_topic_cover.py`

- [ ] **Step 1: Update `job()` to compute the final title before publishing**

```python
final_title = (
    build_discussion_title(topic)
    if publish_config.get("discussion_title_enabled")
    else result.get("title")
)
```

- [ ] **Step 2: Update cover resolution to prefer the configured local cover pool**

```python
cover_pool_dir = (publish_config.get("discussion_cover_pool_dir") or "").strip()
if cover_pool_dir:
    cover_path = resolve_cover_path_from_pool(cover_pool_dir, title=final_title)
else:
    cover_path = resolve_cover_path(topic_info=topic_info, title_hint=final_title)
```

- [ ] **Step 3: Pass the deterministic title into `format_for_wechat`**

```python
formatted_article = publisher.format_for_wechat(
    content=content_for_publish,
    title=final_title,
    ...
    cover_image=cover_path,
)
```

- [ ] **Step 4: Run the job-integration test**

Run: `python -m unittest tests.test_hot_topic_cover.HotTopicCoverTests.test_job_uses_discussion_title_and_pool_cover_for_publish -v`
Expected: PASS

### Task 7: Document config and behavior, then run verification

**Files:**
- Modify: `config/config.py.example`
- Modify: `README.md`
- Test: `tests/test_hot_topic_cover.py`

- [ ] **Step 1: Add config documentation**

```python
PUBLISH_CONFIG = {
    ...
    "discussion_title_enabled": True,
    "discussion_cover_pool_dir": "/app/cover_pool",
}
```

- [ ] **Step 2: Explain the behavior in `README.md`**

```markdown
- 最终标题固定为 `发现中国有一个奇怪的现象：xxx`
- 封面从本地素材池随机选图，再叠加本次标题生成发布封面
```

- [ ] **Step 3: Run focused verification**

Run: `python -m unittest tests.test_hot_topic_cover tests.test_weibo_topic_limit tests.test_wechat_web_publisher_close -v`
Expected: PASS

- [ ] **Step 4: Run broader regression verification**

Run: `python -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS
